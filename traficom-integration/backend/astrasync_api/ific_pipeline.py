"""IFIC issue analysis in the worker: the RELEVANCE job (DECISIONS G27).

After an IFIC artifact is indexed, ``enqueue_relevance`` queues one RELEVANCE job. The job:

1. Re-reads the verified master with the registered (isolated) adapter. The adapter is
   deterministic, so record ordinals equal the stored ``source_record_id`` ordinals.
2. Reads the newest indexed M4 table and special-interest workbook of the same tenant the same
   way, and the previous indexed issue of the same source, if any.
3. Runs ``astrasync_data.ific_analysis`` with the registered RF methods (TERR_P1546,
   SPACE_PFD_FREE_SPACE when configured).
4. Stores every finding as a compressed JSON object in the object store, with its SHA-256, and
   one ``ific_analyses`` row with the summary.
5. Opens a case for each HIGH finding (``cases.upsert_candidate``, idempotent per
   notice version), carrying the relevance gates and the calculation scenario.

No step decides a regulatory outcome; cases start as ``INSUFFICIENT_DATA`` and are reviewed.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections.abc import Iterable
from importlib import import_module
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from . import cases
from .contract.enums import (
    ArtifactStatus,
    CaseDomain,
    ChangeType,
    ErrorCode,
    JobType,
    PipelineStatus,
    SourceType,
)
from .contract.interfaces import RFMethod
from .contract.models import CaseCandidate, RelevanceGates
from .ific_tables import IficAnalysisRow
from .ingest import PipelineContext
from .jobs import LANE_ANALYSIS, PermanentJobError, enqueue, utc_now
from .library_tables import SourceArtifactRow, SourceConnectorRow

IFIC_TYPES = (SourceType.SPACE_IFIC.value, SourceType.TERRESTRIAL_IFIC.value)
# Cases are opened for HIGH findings only; all findings stay reviewable on the IFIC screen.
CASE_TIERS = ("HIGH",)
_INDEXED = (ArtifactStatus.INDEXED.value, ArtifactStatus.INDEXED_WITH_WARNINGS.value)
SYSTEM_ACTOR = "system:ific-pipeline"


def enqueue_relevance(
    sessions: sessionmaker[Session], tenant_id: str, artifact_id: str, requested_by: str
) -> str:
    job = enqueue(
        sessions,
        tenant_id=tenant_id,
        job_type=JobType.RELEVANCE,
        lane=LANE_ANALYSIS,
        idempotency_key=f"relevance:{artifact_id}",
        requested_by=requested_by,
        resource_id=artifact_id,
        payload={"artifact_id": artifact_id},
    )
    return job.job_id


def _records(context: PipelineContext, source_type: str, object_key: str) -> list[dict[str, Any]]:
    adapter = context.adapters.get(source_type)
    if adapter is None:
        raise PermanentJobError(
            ErrorCode.PARSER_UNAVAILABLE,
            f"No parser is registered for {source_type}.",
            PipelineStatus.FAILED,
        )
    path = context.store.local_path(object_key)
    return [r for batch in adapter.iter_record_batches(path, batch_rows=5000) for r in batch]


def _newest(session: Session, tenant_id: str, source_types: Iterable[str]) -> list[Any]:
    found = []
    for connector in session.scalars(
        select(SourceConnectorRow).where(
            SourceConnectorRow.tenant_id == tenant_id,
            SourceConnectorRow.source_type.in_(list(source_types)),
        )
    ):
        artifact = session.scalars(
            select(SourceArtifactRow)
            .where(
                SourceArtifactRow.source_id == connector.source_id,
                SourceArtifactRow.status.in_(_INDEXED),
            )
            .order_by(SourceArtifactRow.revision.desc())
        ).first()
        if artifact is not None:
            found.append((connector, artifact))
    return found


def _previous(session: Session, artifact: SourceArtifactRow) -> SourceArtifactRow | None:
    """The newest other indexed artifact of the same source published before this one."""
    query = select(SourceArtifactRow).where(
        SourceArtifactRow.source_id == artifact.source_id,
        SourceArtifactRow.artifact_id != artifact.artifact_id,
        SourceArtifactRow.status.in_(_INDEXED),
        SourceArtifactRow.revision < artifact.revision,
    )
    return session.scalars(query.order_by(SourceArtifactRow.revision.desc())).first()


def run_relevance(
    context: PipelineContext,
    methods: dict[str, RFMethod],
    job_id: str,
    artifact_id: str,
) -> PipelineStatus:
    # The analysis lives in astrasync-core (the RF/data track); it is loaded by name, as plugins
    # are, so the API package does not depend on it at import time.
    analysis: Any = import_module("astrasync_data.ific_analysis")

    with context.sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        connector = session.get_one(SourceConnectorRow, artifact.source_id)
        if connector.source_type not in IFIC_TYPES:
            raise PermanentJobError(
                ErrorCode.VALIDATION_ERROR, "Not an IFIC source.", PipelineStatus.FAILED
            )
        if artifact.status not in _INDEXED:
            raise PermanentJobError(
                ErrorCode.CONFLICT, "The artifact is not indexed.", PipelineStatus.FAILED
            )
        existing = session.scalar(
            select(IficAnalysisRow).where(IficAnalysisRow.artifact_id == artifact_id)
        )
        if existing is not None:
            return PipelineStatus.READY
        tenant_id = connector.tenant_id
        kind = connector.source_type
        m4 = _newest(session, tenant_id, (SourceType.M4_ALLOCATION.value,))
        stations = _newest(
            session,
            tenant_id,
            (
                SourceType.CHALLENGE_SYNTHETIC_REFERENCE.value,
                SourceType.FINLAND_FREQUENCY_INTEREST.value,
            ),
        )
        previous = _previous(session, artifact)
        object_key = artifact.object_key
        # Only references indexed by the parser now registered for their type are re-read; others
        # (for example demo files of the same source type) are skipped and listed.
        reference_inputs = []
        skipped_references = []
        for c, a in m4 + stations:
            adapter = context.adapters.get(c.source_type)
            if adapter is not None and a.parser_version == adapter.parser_version:
                reference_inputs.append((c.source_type, a.object_key, a.artifact_id, c.source_id))
            else:
                skipped_references.append(a.artifact_id)
        previous_key = previous.object_key if previous else None
        previous_id = previous.artifact_id if previous else None

    records = _records(context, kind, object_key)
    m4_records: list[dict[str, Any]] = []
    station_records: list[dict[str, Any]] = []
    for source_type, key, _, _ in reference_inputs:
        target = m4_records if source_type == SourceType.M4_ALLOCATION.value else station_records
        target.extend(_records(context, source_type, key))
    refs = analysis.References(
        analysis.IntervalIndex(analysis.m4_references(m4_records)),
        analysis.IntervalIndex(analysis.station_references(station_records)),
        {
            "reference_artifacts": [a for _, _, a, _ in reference_inputs],
            # Readers of this analysis need READ on each of these sources too (ific_api).
            "reference_sources": sorted({s for _, _, _, s in reference_inputs}),
            "skipped_reference_artifacts": skipped_references,
        },
    )
    previous_records = _records(context, kind, previous_key) if previous_key else None
    if kind == SourceType.TERRESTRIAL_IFIC.value:
        result = analysis.analyse_terrestrial(
            records, refs, previous_records, p1546_method=methods.get("TERR_P1546")
        )
        domain = CaseDomain.TERRESTRIAL
    else:
        previous_ids = {r["notice_id"] for r in previous_records} if previous_records else None
        result = analysis.analyse_space(
            records, refs, previous_ids, pfd_method=methods.get("SPACE_PFD_FREE_SPACE")
        )
        domain = CaseDomain.SPACE
    findings = result["findings"]
    issue = int(records[0]["issue_key"]) if records and records[0]["issue_key"] else 0

    # Record ids for evidence: the ordinal of the first record of each notice.
    first_ordinal: dict[str, int] = {}
    for ordinal, record in enumerate(records):
        if record["notice_id"] is not None:
            first_ordinal.setdefault(record["notice_id"], ordinal)

    payload = json.dumps(
        {"issue": issue, "kind": kind, "findings": findings}, ensure_ascii=False, default=str
    ).encode("utf-8")
    staged = context.store.new_staging_path()
    staged.write_bytes(gzip.compress(payload, compresslevel=9, mtime=0))
    analysis_id = uuid4().hex
    findings_key = context.store.promote(staged, ["ific-analyses", tenant_id, analysis_id])

    created = 0
    for finding in findings:
        if finding["priority"]["tier"] not in CASE_TIERS:
            continue
        candidate = _candidate(
            finding,
            domain,
            connector.source_id,
            artifact_id,
            issue,
            first_ordinal.get(finding["notice_id"]),
        )
        if candidate is None:
            continue
        cases.upsert_candidate(context.sessions, tenant_id, candidate, context.records)
        created += 1

    tiers: dict[str, int] = {}
    statuses: dict[str, int] = {}
    changes: dict[str, int] = {}
    concerns: dict[str, int] = {}
    administrations: dict[str, int] = {}
    for f in findings:
        concern = (f.get("concern") or {}).get("classification")
        if concern:
            concerns[concern] = concerns.get(concern, 0) + 1
        adm = f.get("administration") or "Unknown"
        administrations[adm] = administrations.get(adm, 0) + 1
        tiers[f["priority"]["tier"]] = tiers.get(f["priority"]["tier"], 0) + 1
        statuses[f["finding_status"]] = statuses.get(f["finding_status"], 0) + 1
        changes[f["change"]["change_type"]] = changes.get(f["change"]["change_type"], 0) + 1
    with context.sessions() as session:
        session.add(
            IficAnalysisRow(
                analysis_id=analysis_id,
                tenant_id=tenant_id,
                source_id=connector.source_id,
                artifact_id=artifact_id,
                previous_artifact_id=previous_id,
                kind=kind,
                issue=issue,
                publication_date=None,
                rule_version=analysis.RULE_VERSION,
                status="COMPLETED",
                summary={
                    "tiers": tiers,
                    "statuses": statuses,
                    "change_types": changes,
                    "concerns": concerns,
                    "top_administrations": dict(
                        sorted(administrations.items(), key=lambda kv: -kv[1])[:8]
                    ),
                    "records": len(records),
                    "skipped": result.get("skipped"),
                    "references": refs.provenance,
                    "methods": sorted(methods),
                },
                findings_object_key=findings_key,
                findings_sha256=hashlib.sha256(payload).hexdigest(),
                findings_count=len(findings),
                cases_created=created,
                created_at_utc=utc_now(),
            )
        )
        session.commit()
    return PipelineStatus.READY


_CHANGE = {
    "NEW": ChangeType.NEW,
    "MODIFIED": ChangeType.MODIFIED,
    "WITHDRAWN": ChangeType.WITHDRAWN,
    "INDETERMINATE": ChangeType.UNRESOLVED,
}


def _candidate(
    finding: dict[str, Any],
    domain: CaseDomain,
    source_id: str,
    artifact_id: str,
    issue: int,
    ordinal: int | None,
) -> CaseCandidate | None:
    if domain is CaseDomain.TERRESTRIAL:
        start = end = finding.get("frequency_mhz")
        bandwidth = finding.get("bandwidth_khz")
        if isinstance(start, int | float) and isinstance(bandwidth, int | float):
            start, end = start - bandwidth / 2000, start + bandwidth / 2000
        freq_match = finding["stage_a_frequency"]["status"] == "MATCH"
        service = finding["stage_b_service"].get("status")
        geometry = finding["stage_c_geography"].get("status")
        scenario = finding["calculations"][0]["inputs"] if finding["calculations"] else {}
        scenario_block = {"terrestrial_p1546": scenario} if scenario else {}
    else:
        ranges = [g["range_mhz"] for g in finding["groups"] if g["range_mhz"][0] is not None]
        if not ranges:
            return None
        start, end = min(r[0] for r in ranges), max(r[1] for r in ranges)
        freq_match = (
            finding["stage_a_frequency"]["groups_overlapping_special_interest_stations"] > 0
        )
        service = finding["stage_b_service"].get("status")
        geometry = finding["stage_c_geometry"].get("status")
        calc = finding["calculations"][0] if finding["calculations"] else None
        scenario_block = {"space_pfd_free_space": calc["inputs"]} if calc else {}
    if not isinstance(start, int | float) or not isinstance(end, int | float):
        return None
    reasons = [k.upper() for k, v in finding["priority"]["components"].items() if v][:20]
    scenario = {
        **scenario_block,
        "ific_issue": issue,
        "ific_finding": {
            "priority": finding["priority"],
            "change": finding["change"]["change_type"],
            "status": finding["finding_status"],
        },
    }
    digest = hashlib.sha256(json.dumps(scenario, sort_keys=True, default=str).encode()).hexdigest()
    notice_version = f"{source_id}:{issue}:{finding['notice_id']}"
    return CaseCandidate(
        notice_uid=hashlib.sha256(notice_version.encode()).hexdigest()[:32],
        notice_id=str(finding["notice_id"]),
        source_id=source_id,
        source_issue_id=artifact_id,
        source_record_id=f"{artifact_id}-{ordinal}" if ordinal is not None else None,
        administration=finding.get("administration"),
        domain=domain,
        change_type=_CHANGE.get(finding["change"]["change_type"], ChangeType.UNRESOLVED),
        frequency_start_mhz=max(float(start), 0.0),
        frequency_end_mhz=max(float(end), float(start), 0.0),
        relevance=RelevanceGates(
            label=f"PRIORITY_{finding['priority']['tier']}",
            reason_codes=reasons,
            rule_version=finding["rule_version"],
            overlap_start_mhz=None,
            overlap_end_mhz=None,
            frequency_match=freq_match,
            service_match=None if service == "UNKNOWN" else service == "MATCH",
            geometry_match=None
            if geometry == "UNKNOWN"
            else geometry not in ("NOT_VISIBLE", "DOES_NOT_REACH", "BEYOND_1000_KM"),
            technical_data_ready=bool(finding["calculations"]),
            criterion_available=False,
        ),
        scenario_id=digest[:32],
        scenario=scenario,
    )


def latest_analyses(session: Session, tenant_id: str) -> list[IficAnalysisRow]:
    return list(
        session.scalars(
            select(IficAnalysisRow)
            .where(IficAnalysisRow.tenant_id == tenant_id)
            .order_by(IficAnalysisRow.issue.desc(), IficAnalysisRow.created_at_utc.desc())
        )
    )


def count_analyses(session: Session, tenant_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(IficAnalysisRow)
            .where(IficAnalysisRow.tenant_id == tenant_id)
        )
        or 0
    )
