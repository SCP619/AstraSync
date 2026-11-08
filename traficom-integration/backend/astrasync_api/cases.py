"""Case workflow. Clients can read results and record decisions; they can never write results.

Every read goes through the source entitlement rules used by the source library. Drafts stay
unapproved until a reviewer records a decision, and nothing here ever sends correspondence.
"""

import json
import logging
import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import Request
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .analysis import snapshot_hash
from .authz import not_found
from .case_tables import (
    AnalysisRunRow,
    CaseRow,
    CriterionCheckRow,
    DraftRow,
    EvidenceLinkRow,
    FinlandRelevanceRow,
    MethodRunRow,
    ReferenceDocumentRow,
    ReviewEventRow,
)
from .contract.enums import (
    AnalysisStatus,
    CaseDomain,
    CaseSort,
    ChangeType,
    CriterionApplicability,
    DomainEventKind,
    DraftStatus,
    DraftType,
    ErrorCode,
    FindingStatus,
    JobType,
    MethodExecution,
    ReviewAction,
    ReviewStatus,
    UsageClassification,
)
from .contract.interfaces import EvidenceDraftAgent
from .contract.models import (
    AgentDraftResponse,
    AnalyseRequest,
    AnalysisAccepted,
    AnalysisRun,
    CaseAnswer,
    CaseCandidate,
    CaseDetail,
    CaseList,
    CaseQuestionRequest,
    CaseSummary,
    ComparisonGroup,
    CriterionCheck,
    Draft,
    DraftCreated,
    DraftCreateRequest,
    DraftList,
    DraftUpdateRequest,
    EvidenceLink,
    EvidencePack,
    LeadMetric,
    MethodMatrix,
    MethodRun,
    MethodSummary,
    ReferenceDocument,
    ReferenceList,
    RelevanceGates,
    ReviewCreateRequest,
    ReviewEvent,
    ReviewEventList,
)
from .drafting import DeterministicDraftAgent, deterministic_answer
from .errors import ApiError
from .identity import Principal
from .jobs import LANE_ANALYSIS, emit_event, enqueue, utc_now
from .library import (
    LibraryRuntime,
    _cursor_decode,
    _cursor_encode,
    _envelope,
    _page,
    _require_source_right,
    session_factory_of,
)
from .library_tables import SourceConnectorRow, SourceRecordLocationRow
from .record_store import ParquetRecordStore, dataset_for_record

RIGHT_READ = "READ"
RIGHT_EXPORT = "EXPORT"
AI_DISABLED_BY_DEFAULT = frozenset(
    {
        UsageClassification.RESTRICTED,
        UsageClassification.CONFIDENTIAL_PARTNER,
        UsageClassification.UNVERIFIED,
    }
)
_FINISHED = frozenset(
    {
        AnalysisStatus.READY.value,
        AnalysisStatus.BLOCKED_BY_INPUTS.value,
        AnalysisStatus.NOT_APPLICABLE.value,
        AnalysisStatus.FAILED.value,
        AnalysisStatus.VERIFIED_RESULT.value,
    }
)
_REVIEW_STATUS = {
    ReviewAction.ACCEPT_FINDING: ReviewStatus.ACCEPTED,
    ReviewAction.REJECT_FINDING: ReviewStatus.REJECTED,
    ReviewAction.NEEDS_MORE_DATA: ReviewStatus.NEEDS_MORE_DATA,
    ReviewAction.FOLLOW_UP: ReviewStatus.IN_REVIEW,
    ReviewAction.CLOSE_NO_CONCERN: ReviewStatus.CLOSED,
}
# Claims the docs forbid without an approved finding. They trigger a warning for the reviewer.
_UNSUPPORTED_CLAIMS = re.compile(
    r"\b(violation|breach|harmful interference|illegal|non-?compliant)\b", re.IGNORECASE
)
_SORT_COLUMNS: Mapping[CaseSort, Any] = {
    CaseSort.CASE_ID: CaseRow.case_id,
    CaseSort.FREQUENCY_START: CaseRow.frequency_start_mhz,
    CaseSort.UPDATED_AT: CaseRow.updated_at_utc,
    CaseSort.PRIORITY: func.coalesce(CaseRow.priority, ""),
}

logger = logging.getLogger(__name__)


# --- Candidate creation, called by the relevance pipeline ------------------------------------


def upsert_candidate(
    sessions: sessionmaker[Session],
    tenant_id: str,
    candidate: CaseCandidate,
    records: ParquetRecordStore | None = None,
) -> str:
    """Creates one case per notice version. A frequency match alone never exceeds a candidate."""
    with sessions() as session:
        existing = session.scalar(
            select(CaseRow.case_id).where(
                CaseRow.tenant_id == tenant_id, CaseRow.notice_uid == candidate.notice_uid
            )
        )
        if existing is not None:
            return existing
        connector = session.get(SourceConnectorRow, candidate.source_id)
        if connector is None or connector.tenant_id != tenant_id:
            raise ValueError("The source is not registered for this tenant")
        now = utc_now()
        relevance_id = uuid4().hex
        gates = candidate.relevance
        session.add(
            FinlandRelevanceRow(
                relevance_id=relevance_id,
                tenant_id=tenant_id,
                notice_uid=candidate.notice_uid,
                label=gates.label,
                reason_codes=gates.reason_codes,
                rule_version=gates.rule_version,
                overlap_start_mhz=gates.overlap_start_mhz,
                overlap_end_mhz=gates.overlap_end_mhz,
                frequency_match=gates.frequency_match,
                service_match=gates.service_match,
                geometry_match=gates.geometry_match,
                technical_data_ready=gates.technical_data_ready,
                criterion_available=gates.criterion_available,
            )
        )
        session.flush()
        case_id = candidate.case_id or uuid4().hex
        session.add(
            CaseRow(
                case_id=case_id,
                tenant_id=tenant_id,
                source_id=candidate.source_id,
                source_issue_id=candidate.source_issue_id,
                notice_uid=candidate.notice_uid,
                notice_id=candidate.notice_id,
                administration=candidate.administration,
                domain=candidate.domain.value,
                change_type=candidate.change_type.value,
                frequency_start_mhz=candidate.frequency_start_mhz,
                frequency_end_mhz=candidate.frequency_end_mhz,
                usage_classification=connector.usage_classification,
                is_synthetic=connector.is_synthetic,
                relevance_id=relevance_id,
                scenario_id=candidate.scenario_id,
                scenario=candidate.scenario,
                finding_status=FindingStatus.INSUFFICIENT_DATA.value,
                review_status=ReviewStatus.NEW.value,
                methods_succeeded=0,
                methods_candidates=0,
                created_at_utc=now,
                updated_at_utc=now,
            )
        )
        session.flush()
        if candidate.source_record_id is not None:
            location = _source_location(session, candidate.source_record_id, tenant_id, records)
            if location is None or location.tenant_id != tenant_id:
                raise ValueError("The source record is not in this tenant")
            session.add(
                EvidenceLinkRow(
                    evidence_id=f"{case_id}-record",
                    case_id=case_id,
                    label="Original source record",
                    entity_type="source_record",
                    entity_id=location.source_record_id,
                    source_issue_id=candidate.source_issue_id,
                    source_locator=(
                        f"{location.source_table_or_sheet or '-'}!"
                        f"{location.source_row_or_key or '-'}"
                    ),
                    sha256=location.raw_record_sha256,
                )
            )
        emit_event(
            session,
            tenant_id=tenant_id,
            event_kind=DomainEventKind.CANDIDATE_SCREENED.value,
            resource_type="case",
            resource_id=case_id,
            dedupe_key=f"candidate:{candidate.notice_uid}",
            correlation_id=case_id,
        )
        session.commit()
        return case_id


# --- Reads ------------------------------------------------------------------------------------


def _source_location(
    session: Session,
    source_record_id: str,
    tenant_id: str,
    records: ParquetRecordStore | None,
) -> SourceRecordLocationRow | None:
    if records is None:
        return session.get(SourceRecordLocationRow, source_record_id)
    found = dataset_for_record(session, source_record_id, tenant_id)
    record = records.record(*found) if found is not None else None
    return record[0] if record is not None else None


def _summary_fields(row: CaseRow) -> dict[str, Any]:
    return {
        "case_id": row.case_id,
        "is_synthetic": row.is_synthetic,
        "domain": row.domain,
        "notice_id": row.notice_id,
        "source_issue_id": row.source_issue_id,
        "administration": row.administration,
        "change_type": row.change_type,
        "frequency_start_mhz": row.frequency_start_mhz,
        "frequency_end_mhz": row.frequency_end_mhz,
        "relevance_label": _relevance_label(row),
        "method_summary": MethodSummary(
            succeeded=row.methods_succeeded, candidates=row.methods_candidates
        ),
        "lead_metric": LeadMetric(
            metric_kind=row.lead_metric_kind,
            numeric_value=row.lead_numeric_value,
            unit=row.lead_unit,
        ),
        "margin_db": row.margin_db,
        "criterion_status": row.criterion_status,
        "finding_status": row.finding_status,
        "review_status": row.review_status,
    }


def _relevance_label(row: CaseRow) -> str:
    label = getattr(row, "_relevance_label", None)
    if label is None:
        raise RuntimeError("relevance label was not loaded")
    return str(label)


def _with_labels(session: Session, rows: list[CaseRow]) -> list[CaseRow]:
    ids = [row.relevance_id for row in rows]
    labels = dict(
        session.execute(
            select(FinlandRelevanceRow.relevance_id, FinlandRelevanceRow.label).where(
                FinlandRelevanceRow.relevance_id.in_(ids)
            )
        ).all()
    )
    for row in rows:
        row._relevance_label = labels[row.relevance_id]  # type: ignore[attr-defined]
    return rows


def _case_cursor(value: Any, case_id: str) -> str:
    rendered = value.isoformat() if isinstance(value, datetime) else value
    return _cursor_encode(json.dumps([rendered, case_id]))


def list_cases(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    domain: CaseDomain | None,
    source_issue_id: str | None,
    change_type: ChangeType | None,
    finding_status: FindingStatus | None,
    review_status: ReviewStatus | None,
    query_text: str | None,
    sort: CaseSort,
    limit: int,
    cursor: str | None,
) -> CaseList:
    table = CaseRow
    query = select(table).where(
        runtime.policy.readable_clause(
            principal,
            RIGHT_READ,
            tenant_column=table.tenant_id,
            source_column=table.source_id,
            classification_column=table.usage_classification,
            synthetic_column=table.is_synthetic,
        )
    )
    if domain is not None:
        query = query.where(table.domain == domain.value)
    if source_issue_id is not None:
        query = query.where(table.source_issue_id == source_issue_id)
    if change_type is not None:
        query = query.where(table.change_type == change_type.value)
    if finding_status is not None:
        query = query.where(table.finding_status == finding_status.value)
    if review_status is not None:
        query = query.where(table.review_status == review_status.value)
    if query_text:
        needle = query_text.strip()
        query = query.where(
            or_(
                table.case_id.icontains(needle, autoescape=True),
                table.notice_id.icontains(needle, autoescape=True),
                table.source_issue_id.icontains(needle, autoescape=True),
                table.administration.icontains(needle, autoescape=True),
            )
        )

    column = _SORT_COLUMNS[sort]
    decoded = _cursor_decode(cursor)
    if decoded is not None:
        value, case_id = _parse_case_cursor(decoded, sort)
        query = query.where(or_(column > value, (column == value) & (table.case_id > case_id)))
    rows = list(session.scalars(query.order_by(column, table.case_id).limit(limit + 1)))
    kept = _with_labels(session, rows[:limit])
    next_cursor = None
    if len(rows) > limit:
        last = kept[-1]
        sort_value = {
            CaseSort.CASE_ID: last.case_id,
            CaseSort.FREQUENCY_START: last.frequency_start_mhz,
            CaseSort.UPDATED_AT: last.updated_at_utc,
            CaseSort.PRIORITY: last.priority or "",
        }[sort]
        next_cursor = _case_cursor(sort_value, last.case_id)
    return CaseList(
        **_envelope(),
        items=[CaseSummary(**_summary_fields(row)) for row in kept],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def _parse_case_cursor(decoded: str, sort: CaseSort) -> tuple[Any, str]:
    try:
        value, case_id = json.loads(decoded)
        if not isinstance(case_id, str):
            raise ValueError
        if sort is CaseSort.UPDATED_AT:
            value = datetime.fromisoformat(value)
        elif sort is CaseSort.FREQUENCY_START:
            value = float(value)
        elif not isinstance(value, str):
            raise ValueError
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Invalid cursor.") from exc
    return value, case_id


def readable_case(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    right: str = RIGHT_READ,
) -> CaseRow:
    row = session.get(CaseRow, case_id)
    if row is None or row.tenant_id != principal.tenant_id:
        raise not_found()
    _require_source_right(
        runtime,
        request,
        principal,
        source_id=row.source_id,
        classification=row.usage_classification,
        is_synthetic=row.is_synthetic,
        right=right,
        tenant_id=row.tenant_id,
    )
    return row


def _evidence_view(row: EvidenceLinkRow) -> EvidenceLink:
    return EvidenceLink(
        evidence_id=row.evidence_id,
        label=row.label,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        source_issue_id=row.source_issue_id,
        reference_id=row.reference_id,
        source_locator=row.source_locator,
        sha256=row.sha256,
        verified_at_utc=row.verified_at_utc,
        note=row.note,
    )


def _evidence_of(session: Session, case_id: str) -> list[EvidenceLink]:
    rows = session.scalars(
        select(EvidenceLinkRow)
        .where(EvidenceLinkRow.case_id == case_id)
        .order_by(EvidenceLinkRow.evidence_id)
    )
    return [_evidence_view(row) for row in rows]


def record_screening(
    sessions: sessionmaker[Session], case_id: str, screening: dict[str, Any] | None
) -> None:
    """Keep the latest IFIC screening result with the case (updated on re-analysis)."""
    with sessions() as session:
        row = session.get(CaseRow, case_id)
        if row is None:
            return
        scenario = dict(row.scenario or {})
        if screening is None:
            scenario.pop("ific_screening", None)
        else:
            scenario["ific_screening"] = screening
        row.scenario = scenario
        session.commit()


def get_case(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
) -> CaseDetail:
    row = readable_case(runtime, request, session, principal, case_id)
    _with_labels(session, [row])
    gates = session.get_one(FinlandRelevanceRow, row.relevance_id)
    return CaseDetail(
        **_envelope(),
        **_summary_fields(row),
        relevance=RelevanceGates(
            label=gates.label,
            reason_codes=gates.reason_codes,
            rule_version=gates.rule_version,
            overlap_start_mhz=gates.overlap_start_mhz,
            overlap_end_mhz=gates.overlap_end_mhz,
            frequency_match=gates.frequency_match,
            service_match=gates.service_match,
            geometry_match=gates.geometry_match,
            technical_data_ready=gates.technical_data_ready,
            criterion_available=gates.criterion_available,
        ),
        evidence=_evidence_of(session, case_id),
        screening=(row.scenario or {}).get("ific_screening"),
        latest_analysis_run_id=row.latest_analysis_run_id,
        priority=row.priority,
        priority_reason=row.priority_reason,
        owner=row.owner,
        reviewer_decision=row.reviewer_decision,
        created_at_utc=row.created_at_utc,
        updated_at_utc=row.updated_at_utc,
    )


def _method_runs(session: Session, run_id: str) -> list[MethodRun]:
    rows = session.scalars(
        select(MethodRunRow)
        .where(MethodRunRow.analysis_run_id == run_id)
        .order_by(MethodRunRow.ordinal)
    )
    return [MethodRun.model_validate(row.result) for row in rows]


def _criterion_checks(session: Session, run_id: str) -> list[CriterionCheck]:
    rows = session.scalars(
        select(CriterionCheckRow)
        .where(CriterionCheckRow.analysis_run_id == run_id)
        .order_by(CriterionCheckRow.ordinal)
    )
    return [CriterionCheck.model_validate(row.result) for row in rows]


def _analysis_view(session: Session, run: AnalysisRunRow, is_synthetic: bool) -> AnalysisRun:
    return AnalysisRun(
        **_envelope(),
        analysis_run_id=run.analysis_run_id,
        case_id=run.case_id,
        scenario_id=run.scenario_id,
        is_synthetic=is_synthetic,
        run_created_at_utc=run.run_created_at_utc,
        input_snapshot_sha256=run.input_snapshot_sha256,
        software_commit_sha=run.software_commit_sha,
        method_registry_version=run.method_registry_version,
        reference_snapshot_sha256=run.reference_snapshot_sha256,
        analysis_status=run.analysis_status,
        created_by=run.created_by,
        method_runs=_method_runs(session, run.analysis_run_id),
        criterion_checks=_criterion_checks(session, run.analysis_run_id),
    )


def _readable_run(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    run_id: str,
) -> tuple[AnalysisRunRow, CaseRow]:
    run = session.get(AnalysisRunRow, run_id)
    if run is None or run.tenant_id != principal.tenant_id:
        raise not_found()
    return run, readable_case(runtime, request, session, principal, run.case_id)


def get_analysis(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    run_id: str,
) -> AnalysisRun:
    run, case = _readable_run(runtime, request, session, principal, run_id)
    return _analysis_view(session, run, case.is_synthetic)


def comparison_groups(method_runs: list[MethodRun]) -> list[ComparisonGroup]:
    """Groups only results with the same metric, unit, bandwidth, statistics and receiver."""
    grouped: dict[tuple[Any, ...], list[MethodRun]] = defaultdict(list)
    for run in method_runs:
        if run.execution_status is MethodExecution.SUCCEEDED:
            grouped[
                (
                    run.metric_kind,
                    run.scenario_id,
                    run.unit,
                    run.reference_bandwidth_hz,
                    run.time_percentage,
                    run.location_percentage,
                    run.receiver_site_id,
                )
            ].append(run)
    return [
        ComparisonGroup(
            group_id=f"group-{index}",
            metric_kind=members[0].metric_kind,
            method_run_ids=[member.method_run_id for member in members],
            preferred_method_run_id=None,
            preferred_reason=None,
        )
        for index, members in enumerate(grouped.values())
        if len(members) >= 2
    ]


def get_method_matrix(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    run_id: str,
) -> MethodMatrix:
    run, case = _readable_run(runtime, request, session, principal, run_id)
    method_runs = _method_runs(session, run_id)
    return MethodMatrix(
        **_envelope(),
        analysis_run_id=run.analysis_run_id,
        is_synthetic=case.is_synthetic,
        method_runs=method_runs,
        comparison_groups=comparison_groups(method_runs),
    )


def list_references(
    session: Session, principal: Principal, limit: int, cursor: str | None
) -> ReferenceList:
    table = ReferenceDocumentRow
    open_levels = (UsageClassification.PUBLIC.value, UsageClassification.INTERNAL.value)
    query = select(table).where(
        table.tenant_id == principal.tenant_id, table.usage_classification.in_(open_levels)
    )
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(table.reference_id > after)
    rows = list(session.scalars(query.order_by(table.reference_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "reference_id")
    return ReferenceList(
        **_envelope(),
        items=[
            ReferenceDocument(
                reference_id=row.reference_id,
                authority=row.authority,
                document_title=row.document_title,
                edition=row.edition,
                publication_date=row.publication_date,
                effective_date=row.effective_date,
                source_url=row.source_url,
                snapshot_sha256=row.snapshot_sha256,
                section_id=row.section_id,
                reviewed_by=row.reviewed_by,
                last_verified_at_utc=row.last_verified_at_utc,
                usage_classification=row.usage_classification,
            )
            for row in kept
        ],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


# --- Analysis requests ------------------------------------------------------------------------


def request_analysis(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    body: AnalyseRequest,
    idempotency_key: str,
) -> AnalysisAccepted:
    case = readable_case(runtime, request, session, principal, case_id)
    if body.scenario_id is not None and body.scenario_id != case.scenario_id:
        raise ApiError(409, ErrorCode.CONFLICT, "This scenario does not belong to this case.")
    existing = session.scalar(
        select(AnalysisRunRow).where(
            AnalysisRunRow.case_id == case_id,
            AnalysisRunRow.idempotency_key == idempotency_key,
        )
    )
    if existing is not None and existing.job_id is not None:
        return AnalysisAccepted(
            **_envelope(), analysis_run_id=existing.analysis_run_id, job_id=existing.job_id
        )
    run = existing or AnalysisRunRow(
        analysis_run_id=uuid4().hex,
        tenant_id=case.tenant_id,
        case_id=case_id,
        scenario_id=case.scenario_id,
        scenario_snapshot=case.scenario,
        input_snapshot_sha256=snapshot_hash(case.scenario),
        # The worker that runs the plugins records these two when it starts.
        software_commit_sha="pending",
        method_registry_version="pending",
        analysis_status=AnalysisStatus.QUEUED.value,
        created_by=principal.user_id,
        idempotency_key=idempotency_key,
        run_created_at_utc=utc_now(),
    )
    if existing is None:
        session.add(run)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return request_analysis(
                runtime,
                request,
                session,
                principal,
                case_id,
                body,
                idempotency_key,
            )
    job = enqueue(
        session_factory_of(session),
        tenant_id=case.tenant_id,
        job_type=JobType.RF,
        lane=LANE_ANALYSIS,
        idempotency_key=f"analysis:{run.analysis_run_id}",
        requested_by=principal.user_id,
        resource_id=run.analysis_run_id,
        payload={"analysis_run_id": run.analysis_run_id},
    )
    run.job_id = job.job_id
    session.commit()
    return AnalysisAccepted(**_envelope(), analysis_run_id=run.analysis_run_id, job_id=job.job_id)


# --- Drafts -----------------------------------------------------------------------------------


def _draft_fields(row: DraftRow) -> dict[str, Any]:
    return {
        "draft_id": row.draft_id,
        "case_id": row.case_id,
        "draft_type": row.draft_type,
        "source_analysis_run_id": row.source_analysis_run_id,
        "content_markdown": row.content_markdown,
        "citations": row.citations,
        "warnings": row.warnings,
        "ai_model_id": row.ai_model_id,
        "generation_provenance": row.generation_provenance,
        "status": row.status,
        "requires_human_review": True,
        "created_at_utc": row.created_at_utc,
    }


def build_case_evidence(session: Session, case: CaseRow, run: AnalysisRunRow) -> dict[str, Any]:
    """The only facts an agent receives: stored, cited and immutable."""
    return {
        "case_id": case.case_id,
        "notice_id": case.notice_id,
        "administration": case.administration,
        "change_type": case.change_type,
        "source_issue_id": case.source_issue_id,
        "domain": case.domain,
        "frequency_start_mhz": case.frequency_start_mhz,
        "frequency_end_mhz": case.frequency_end_mhz,
        "finding_status": case.finding_status,
        "analysis_run_id": run.analysis_run_id,
        "evidence": [item.model_dump(mode="json") for item in _evidence_of(session, case.case_id)],
        "method_runs": [
            item.model_dump(mode="json") for item in _method_runs(session, run.analysis_run_id)
        ],
        "criterion_checks": [
            item.model_dump(mode="json") for item in _criterion_checks(session, run.analysis_run_id)
        ],
    }


def _agent_draft(
    agent: EvidenceDraftAgent, evidence: dict[str, Any], draft_type: DraftType, run_id: str
) -> AgentDraftResponse:
    """Agent output is checked like any untrusted input before anything is stored."""
    unusable = ApiError(
        503, ErrorCode.AI_UNAVAILABLE, "The drafting service did not return a usable draft."
    )
    try:
        draft = AgentDraftResponse.model_validate(agent.create_draft(evidence, draft_type.value))
    except ValidationError as exc:
        logger.warning("draft_refused case=%s reason=invalid_structure", evidence.get("case_id"))
        raise unusable from exc
    except Exception as exc:
        # The reason names the failed check (citation, number, claim, transport); no prompt,
        # evidence or secret is logged.
        logger.warning(
            "draft_refused case=%s reason=%s: %s",
            evidence.get("case_id"),
            type(exc).__name__,
            str(exc)[:200],
        )
        raise ApiError(
            503, ErrorCode.AI_UNAVAILABLE, "The drafting service is unavailable."
        ) from exc
    known = {item["evidence_id"] for item in evidence["evidence"]}
    if (
        draft.draft_type is not draft_type
        or draft.analysis_run_id != run_id
        or not set(draft.cited_evidence_ids) <= known
    ):
        raise unusable
    return draft


def create_draft(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    body: DraftCreateRequest,
    *,
    agent: EvidenceDraftAgent | None,
    ai_classifications: frozenset[UsageClassification],
) -> DraftCreated:
    case = readable_case(runtime, request, session, principal, case_id)
    run = session.get(AnalysisRunRow, body.analysis_run_id)
    if run is None or run.case_id != case_id:
        raise not_found()
    if run.analysis_status not in _FINISHED:
        raise ApiError(409, ErrorCode.CONFLICT, "This analysis has not finished.")
    if UsageClassification(case.usage_classification) not in ai_classifications:
        raise ApiError(
            403,
            ErrorCode.SOURCE_RESTRICTED,
            "AI drafting is not approved for this data classification.",
        )
    if agent is None:
        raise ApiError(
            503,
            ErrorCode.AI_UNAVAILABLE,
            "AI drafting is not available. Analysis, evidence and review still work.",
        )

    evidence = build_case_evidence(session, case, run)
    provenance, model_id = "evidence-bound-agent", getattr(agent, "model_id", None)
    fallback_warning: list[str] = []
    try:
        draft = _agent_draft(agent, evidence, body.draft_type, run.analysis_run_id)
    except ApiError:
        if not getattr(agent, "fallback_to_deterministic", False):
            raise
        deterministic = DeterministicDraftAgent()
        draft = _agent_draft(deterministic, evidence, body.draft_type, run.analysis_run_id)
        provenance, model_id = "deterministic-fallback", deterministic.model_id
        fallback_warning = [
            "The local model's draft was refused by the evidence checks; this draft uses fixed "
            "wording composed from the evidence."
        ]
    warnings = fallback_warning + [f"Uncertain: {item}" for item in draft.uncertainties]
    if not draft.cited_evidence_ids:
        warnings.append("This draft cites no evidence.")
    for claim in sorted(
        {m.group(0).lower() for m in _UNSUPPORTED_CLAIMS.finditer(draft.draft_markdown)}
    ):
        warnings.append(f'Contains "{claim}". Only an approved finding can support that wording.')

    row = DraftRow(
        draft_id=uuid4().hex,
        case_id=case_id,
        draft_type=body.draft_type.value,
        source_analysis_run_id=run.analysis_run_id,
        content_markdown=draft.draft_markdown,
        citations=draft.cited_evidence_ids,
        warnings=warnings,
        ai_model_id=model_id,
        generation_provenance=provenance,
        status=DraftStatus.DRAFT.value,
        created_by=principal.user_id,
        created_at_utc=utc_now(),
    )
    session.add(row)
    session.commit()
    return DraftCreated(**_envelope(), **_draft_fields(row))


def answer_question(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    body: CaseQuestionRequest,
    *,
    agent: Any,
    ai_classifications: frozenset[UsageClassification],
) -> CaseAnswer:
    """Same gates as drafting: case access, finished run, AI classification, a grounded agent."""
    case = readable_case(runtime, request, session, principal, case_id)
    run = session.get(AnalysisRunRow, body.analysis_run_id)
    if run is None or run.case_id != case_id:
        raise not_found()
    if run.analysis_status not in _FINISHED:
        raise ApiError(409, ErrorCode.CONFLICT, "This analysis has not finished.")
    if UsageClassification(case.usage_classification) not in ai_classifications:
        raise ApiError(
            403,
            ErrorCode.SOURCE_RESTRICTED,
            "AI answers are not approved for this data classification.",
        )
    answer = getattr(agent, "answer_question", None)
    if answer is None:
        raise ApiError(
            503,
            ErrorCode.AI_UNAVAILABLE,
            "AI answers are not available. Analysis, evidence and review still work.",
        )
    evidence = build_case_evidence(session, case, run)
    known = {item["evidence_id"] for item in evidence["evidence"]}
    generation: Literal["MODEL", "DETERMINISTIC_FALLBACK"] = "MODEL"
    refused: str | None = None
    cited: list[str] = []
    text = ""
    result: dict[str, Any] = {}
    try:
        result = answer(evidence, body.question)
        cited = [str(c) for c in result["cited_evidence_ids"]]
        text = str(result["answer_markdown"])
        if not cited or not set(cited) <= known or _UNSUPPORTED_CLAIMS.search(text):
            refused = "server_check"
    except Exception as exc:
        refused = f"{type(exc).__name__}: {str(exc)[:200]}"
    if refused is not None:
        logger.warning("answer_refused case=%s reason=%s", case_id, refused)
        unusable = ApiError(
            503, ErrorCode.AI_UNAVAILABLE, "The assistant did not return a usable answer."
        )
        if not getattr(agent, "fallback_to_deterministic", False):
            raise unusable
        try:
            result = deterministic_answer(evidence)
        except ValueError:
            raise unusable from None
        cited = result["cited_evidence_ids"]
        text = result["answer_markdown"]
        generation = "DETERMINISTIC_FALLBACK"
    return CaseAnswer(
        **_envelope(),
        case_id=case_id,
        analysis_run_id=run.analysis_run_id,
        answer_markdown=text,
        uncertainties=[str(u) for u in result.get("uncertainties", [])][:20],
        cited_evidence_ids=cited,
        ai_model_id=getattr(agent, "model_id", None) if generation == "MODEL" else None,
        requires_human_review=True,
        generation=generation,
    )


def list_drafts(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    limit: int,
    cursor: str | None,
) -> DraftList:
    readable_case(runtime, request, session, principal, case_id)
    query = select(DraftRow).where(DraftRow.case_id == case_id)
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(DraftRow.draft_id > after)
    rows = list(session.scalars(query.order_by(DraftRow.draft_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "draft_id")
    return DraftList(
        **_envelope(),
        items=[Draft(**_envelope(), **_draft_fields(row)) for row in kept],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def update_draft(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    draft_id: str,
    body: DraftUpdateRequest,
) -> Draft:
    """Text only. Status and citations cannot be set here, so an edit can never approve."""
    readable_case(runtime, request, session, principal, case_id)
    row = session.get(DraftRow, draft_id)
    if row is None or row.case_id != case_id:
        raise not_found()
    if row.status not in (DraftStatus.DRAFT.value, DraftStatus.EDITED.value):
        raise ApiError(409, ErrorCode.CONFLICT, "A decided draft cannot be edited.")
    row.content_markdown = body.content_markdown
    row.status = DraftStatus.EDITED.value
    session.commit()
    return Draft(**_envelope(), **_draft_fields(row))


# --- Reviews ----------------------------------------------------------------------------------


def _review_view(row: ReviewEventRow) -> ReviewEvent:
    return ReviewEvent(
        **_envelope(),
        review_event_id=row.review_event_id,
        case_id=row.case_id,
        actor_id=row.actor_id,
        action=row.action,
        decision_reason=row.decision_reason,
        analysis_run_id=row.analysis_run_id,
        draft_id=row.draft_id,
        occurred_at_utc=row.occurred_at_utc,
    )


def _has_verified_criterion(session: Session, run_id: str) -> bool:
    return any(
        check.applicable is CriterionApplicability.VERIFIED
        for check in _criterion_checks(session, run_id)
    )


def create_review(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    body: ReviewCreateRequest,
    idempotency_key: str,
) -> ReviewEvent:
    case = readable_case(runtime, request, session, principal, case_id)
    existing = session.scalar(
        select(ReviewEventRow).where(
            ReviewEventRow.case_id == case_id,
            ReviewEventRow.actor_id == principal.user_id,
            ReviewEventRow.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return _review_view(existing)

    if body.analysis_run_id is not None:
        run = session.get(AnalysisRunRow, body.analysis_run_id)
        if run is None or run.case_id != case_id:
            raise not_found()
    if body.action is ReviewAction.ACCEPT_FINDING and (
        case.latest_analysis_run_id is None or body.analysis_run_id is None
    ):
        raise ApiError(409, ErrorCode.CONFLICT, "A finding can only be accepted from an analysis.")

    draft: DraftRow | None = None
    if body.draft_id is not None:
        draft = session.get(DraftRow, body.draft_id)
        if draft is None or draft.case_id != case_id:
            raise not_found()
    if draft is not None and body.action in (ReviewAction.APPROVE_DRAFT, ReviewAction.REJECT_DRAFT):
        if draft.status not in (DraftStatus.DRAFT.value, DraftStatus.EDITED.value):
            raise ApiError(409, ErrorCode.CONFLICT, "This draft has already been decided.")
        if (
            body.action is ReviewAction.APPROVE_DRAFT
            and draft.draft_type == DraftType.DRAFT_OBJECTION.value
            and not _has_verified_criterion(session, draft.source_analysis_run_id)
        ):
            raise ApiError(
                409,
                ErrorCode.CONFLICT,
                "An objection cannot be approved without a verified applicable criterion.",
            )
        draft.status = (
            DraftStatus.APPROVED
            if body.action is ReviewAction.APPROVE_DRAFT
            else DraftStatus.REJECTED
        ).value

    now = utc_now()
    row = ReviewEventRow(
        review_event_id=uuid4().hex,
        case_id=case_id,
        actor_id=principal.user_id,
        action=body.action.value,
        decision_reason=body.decision_reason,
        analysis_run_id=body.analysis_run_id,
        draft_id=body.draft_id,
        idempotency_key=idempotency_key,
        occurred_at_utc=now,
    )
    session.add(row)
    session.flush()
    if body.action is ReviewAction.ESCALATE:
        emit_event(
            session,
            tenant_id=case.tenant_id,
            event_kind=DomainEventKind.CASE_ESCALATED.value,
            resource_type="case",
            resource_id=case_id,
            dedupe_key=f"escalated:{row.review_event_id}",
            correlation_id=row.review_event_id,
            payload={"review_event_id": row.review_event_id},
        )
    next_status = _REVIEW_STATUS.get(body.action)
    if next_status is not None:
        case.review_status = next_status.value
        case.reviewer_decision = body.action.value
    elif case.review_status == ReviewStatus.NEW.value:
        case.review_status = ReviewStatus.IN_REVIEW.value
    case.updated_at_utc = now
    emit_event(
        session,
        tenant_id=case.tenant_id,
        event_kind=DomainEventKind.CASE_REVIEWED.value,
        resource_type="case",
        resource_id=case_id,
        dedupe_key=f"review:{row.review_event_id}",
        correlation_id=row.review_event_id,
    )
    session.commit()
    return _review_view(row)


def list_reviews(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
    limit: int,
    cursor: str | None,
) -> ReviewEventList:
    readable_case(runtime, request, session, principal, case_id)
    query = select(ReviewEventRow).where(ReviewEventRow.case_id == case_id)
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(ReviewEventRow.review_event_id > after)
    rows = list(session.scalars(query.order_by(ReviewEventRow.review_event_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "review_event_id")
    items = sorted(kept, key=lambda row: row.occurred_at_utc)
    return ReviewEventList(
        **_envelope(),
        items=[_review_view(row) for row in items],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def export_case(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    case_id: str,
) -> EvidencePack:
    """A portable record for the reviewer. AstraSync sends nothing to anyone."""
    case = readable_case(runtime, request, session, principal, case_id, right=RIGHT_EXPORT)
    runs = session.scalars(
        select(AnalysisRunRow)
        .where(AnalysisRunRow.case_id == case_id)
        .order_by(AnalysisRunRow.run_created_at_utc)
    ).all()
    drafts = session.scalars(
        select(DraftRow).where(DraftRow.case_id == case_id).order_by(DraftRow.created_at_utc)
    ).all()
    reviews = session.scalars(
        select(ReviewEventRow)
        .where(ReviewEventRow.case_id == case_id)
        .order_by(ReviewEventRow.occurred_at_utc)
    ).all()
    return EvidencePack(
        **_envelope(),
        case_id=case_id,
        is_synthetic=case.is_synthetic,
        evidence=_evidence_of(session, case_id),
        analysis_runs=[_analysis_view(session, run, case.is_synthetic) for run in runs],
        drafts=[Draft(**_envelope(), **_draft_fields(row)) for row in drafts],
        review_events=[_review_view(row) for row in reviews],
    )
