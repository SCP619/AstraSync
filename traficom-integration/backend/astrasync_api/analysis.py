"""Orchestrates one analysis run. It holds no physics and selects no legal limit.

For every candidate method it records a row, even when the method did not run. Results come only
from registered ``RFMethod`` plugins, and criteria only from a registered ``CriterionResolver``.
The one calculation here is ``margin = predicted - limit``, for a verified upper-bound criterion
whose unit, bandwidth and statistics all match.
"""

import copy
import hashlib
import json
import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from .case_tables import AnalysisRunRow, CaseRow, CriterionCheckRow, MethodRunRow
from .contract.enums import (
    AnalysisStatus,
    CaseDomain,
    ComparisonOperator,
    ComparisonStatus,
    CriterionApplicability,
    DomainEventKind,
    FindingStatus,
    MethodApplicability,
    MethodExecution,
    MethodRole,
    MetricKind,
    PipelineStatus,
)
from .contract.interfaces import CriterionResolver, RFMethod
from .contract.models import CriterionCheck, MethodAssessment, MethodCalculation, MethodRun
from .jobs import emit_event, utc_now

logger = logging.getLogger("astrasync.analysis")

_ROLE_ORDER = {
    MethodRole.REGULATORY: 0,
    MethodRole.ENGINEERING: 1,
    MethodRole.VERIFICATION: 2,
    MethodRole.SCREENING: 3,
}


@dataclass(frozen=True)
class CatalogueEntry:
    method_id: str
    standard_ref_id: str | None
    role: MethodRole
    metric_kind: MetricKind | None


# RF_METHODS_AND_VALIDATION.md sections 2 and 3. A label for what could run, not an implementation.
CANDIDATES: dict[CaseDomain, tuple[CatalogueEntry, ...]] = {
    CaseDomain.SPACE: (
        CatalogueEntry(
            "SPACE_PFD_FREE_SPACE", "ITU-R P.525-5", MethodRole.SCREENING, MetricKind.PFD
        ),
        CatalogueEntry("SPACE_PFD_DIRECTIONAL", None, MethodRole.ENGINEERING, MetricKind.PFD),
        CatalogueEntry("SPACE_PFD_TIME_SERIES", None, MethodRole.ENGINEERING, MetricKind.PFD),
        CatalogueEntry("SPACE_EPFD_NGSO", "ITU-R S.1503-4", MethodRole.REGULATORY, MetricKind.EPFD),
        CatalogueEntry("SPACE_AUTHORITATIVE_CHECK", None, MethodRole.VERIFICATION, None),
    ),
    CaseDomain.TERRESTRIAL: (
        CatalogueEntry(
            "TERR_FREE_SPACE",
            "ITU-R P.525-5",
            MethodRole.SCREENING,
            MetricKind.BASIC_TRANSMISSION_LOSS,
        ),
        CatalogueEntry(
            "TERR_P1546", "ITU-R P.1546-6", MethodRole.ENGINEERING, MetricKind.FIELD_STRENGTH
        ),
        CatalogueEntry(
            "TERR_P1812", "ITU-R P.1812-8", MethodRole.ENGINEERING, MetricKind.FIELD_STRENGTH
        ),
        CatalogueEntry(
            "TERR_P452",
            "ITU-R P.452-18",
            MethodRole.ENGINEERING,
            MetricKind.BASIC_TRANSMISSION_LOSS,
        ),
    ),
}


@dataclass(frozen=True)
class AnalysisPlugins:
    methods: Mapping[str, RFMethod] = field(default_factory=dict)
    criterion_resolver: CriterionResolver | None = None
    build_sha: str = "unknown"


def snapshot_hash(scenario: Mapping[str, Any]) -> str:
    canonical = json.dumps(scenario, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def registry_version(plugins: AnalysisPlugins) -> str:
    versions = sorted(f"{m.method_id}={m.method_version}" for m in plugins.methods.values())
    digest = hashlib.sha256(";".join(versions).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:32]}"


def _base_row(
    run: AnalysisRunRow, method_id: str, version: str, standard: str | None, role: MethodRole
) -> dict[str, Any]:
    return {
        "method_run_id": f"{run.analysis_run_id}-{method_id}",
        "analysis_run_id": run.analysis_run_id,
        "scenario_id": run.scenario_id,
        "method_id": method_id,
        "method_version": version,
        "standard_ref_id": standard,
        "role": role,
        "applicability": MethodApplicability.NOT_IMPLEMENTED,
        "execution_status": MethodExecution.NOT_RUN,
        "reason_codes": [],
        "missing_fields": [],
        "metric_kind": None,
        "numeric_value": None,
        "unit": None,
        "reference_bandwidth_hz": None,
        "time_percentage": None,
        "location_percentage": None,
        "receiver_site_id": None,
        "satellite_epoch_utc": None,
        "inputs": {},
        "assumptions": [],
        "diagnostics": {},
        "result_trace": {},
        "implementation_sha": None,
        "calculation_sha256": None,
    }


def _failed(base: dict[str, Any], metric: MetricKind | None, reason: str) -> MethodRun:
    return MethodRun(
        **{
            **base,
            "applicability": MethodApplicability.APPLICABLE,
            "execution_status": MethodExecution.FAILED,
            "metric_kind": metric,
            "reason_codes": [reason],
        }
    )


def _run_method(
    base: dict[str, Any],
    entry: CatalogueEntry | None,
    method: RFMethod,
    scenario: Mapping[str, Any],
) -> MethodRun:
    metric = entry.metric_kind if entry else None
    method_id = base["method_id"]
    try:
        assessment = MethodAssessment.model_validate(
            method.assess_applicability(copy.deepcopy(dict(scenario)))
        )
        if assessment.method_id != method_id:
            raise ValueError("assessment names another method")
        metric = assessment.metric_kind or metric
        if assessment.applicability is not MethodApplicability.APPLICABLE:
            return MethodRun(
                **{
                    **base,
                    "applicability": assessment.applicability,
                    "reason_codes": assessment.reason_codes,
                    "missing_fields": assessment.missing_fields,
                    "metric_kind": metric,
                }
            )
    except Exception:
        logger.exception("method_assessment_failed method_id=%s", method_id)
        return _failed(base, metric, "INVALID_ASSESSMENT")

    try:
        calculation = MethodCalculation.model_validate(
            method.calculate(copy.deepcopy(dict(scenario)))
        )
        if calculation.method_id != method_id:
            raise ValueError("result names another method")
        if metric is not None and calculation.metric_kind is not metric:
            raise ValueError("result is not the metric this method declares")
        return MethodRun(
            **{
                **base,
                "applicability": MethodApplicability.APPLICABLE,
                "execution_status": MethodExecution.SUCCEEDED,
                **calculation.model_dump(),
            }
        )
    except Exception:
        # One failed method never hides the others, and never produces a number.
        logger.exception("method_calculation_failed method_id=%s", method_id)
        return _failed(base, metric, "CALCULATION_FAILED")


def plan_and_run(
    run: AnalysisRunRow, domain: CaseDomain, plugins: AnalysisPlugins
) -> list[MethodRun]:
    entries = CANDIDATES[domain]
    known = {entry.method_id for entry in entries}
    results: list[MethodRun] = []
    for entry in entries:
        method = plugins.methods.get(entry.method_id)
        base = _base_row(
            run,
            entry.method_id,
            method.method_version if method else "none",
            entry.standard_ref_id,
            entry.role,
        )
        if method is None:
            results.append(
                MethodRun(
                    **{
                        **base,
                        "metric_kind": entry.metric_kind,
                        "reason_codes": ["NOT_IMPLEMENTED"],
                    }
                )
            )
        else:
            results.append(_run_method(base, entry, method, run.scenario_snapshot))
    # Registered methods outside the catalogue decide their own applicability.
    for method_id in sorted(set(plugins.methods) - known):
        method = plugins.methods[method_id]
        base = _base_row(run, method_id, method.method_version, None, MethodRole.SCREENING)
        results.append(_run_method(base, None, method, run.scenario_snapshot))
    return results


def _comparison_status(check: dict[str, Any], method_run: MethodRun) -> ComparisonStatus:
    """Every condition must match, or the margin stays null."""
    if check.get("applicable") != CriterionApplicability.VERIFIED.value:
        return ComparisonStatus.CRITERION_UNVERIFIED
    conditions = check.get("matching_conditions") or {}
    matches = (
        check.get("comparison_operator") == ComparisonOperator.UPPER_BOUND.value
        and check.get("citation") is not None
        and check.get("limit_value") is not None
        and check.get("limit_unit") == method_run.unit
        and check.get("limit_reference_bandwidth_hz") == method_run.reference_bandwidth_hz
        and conditions.get("metric_kind", method_run.metric_kind) == method_run.metric_kind
        and conditions.get("time_percentage", method_run.time_percentage)
        == method_run.time_percentage
        and conditions.get("location_percentage", method_run.location_percentage)
        == method_run.location_percentage
    )
    return ComparisonStatus.COMPARED if matches else ComparisonStatus.NOT_COMPARABLE


def resolve_criteria(
    run: AnalysisRunRow, method_runs: list[MethodRun], plugins: AnalysisPlugins
) -> list[CriterionCheck]:
    resolver = plugins.criterion_resolver
    if resolver is None:
        return []
    checks: list[CriterionCheck] = []
    context = {"analysis_run_id": run.analysis_run_id, "scenario": run.scenario_snapshot}
    for method_run in method_runs:
        if method_run.execution_status is not MethodExecution.SUCCEEDED:
            continue
        try:
            candidates = resolver.resolve(
                method_run.model_dump(mode="json"), copy.deepcopy(context)
            )
        except Exception:
            logger.exception("criterion_resolution_failed run=%s", method_run.method_run_id)
            continue
        for index, candidate in enumerate(candidates):
            check_id = f"{method_run.method_run_id}-{index}"
            try:
                status = _comparison_status(candidate, method_run)
                # Any margin a resolver supplies is ignored: only this calculation is stored.
                margin = (
                    float(method_run.numeric_value) - float(candidate["limit_value"])
                    if status is ComparisonStatus.COMPARED and method_run.numeric_value is not None
                    else None
                )
                if margin is not None and not math.isfinite(margin):
                    raise ValueError("margin is not finite")
                checks.append(
                    CriterionCheck(
                        **{
                            **candidate,
                            "criterion_check_id": check_id,
                            "method_run_id": method_run.method_run_id,
                            "margin_db": margin,
                            "comparison_status": status,
                        }
                    )
                )
            except (ValidationError, ValueError, TypeError, KeyError):
                logger.exception("criterion_rejected check=%s", check_id)
                checks.append(_unverified_check(check_id, method_run))
    return checks


def _unverified_check(check_id: str, method_run: MethodRun) -> CriterionCheck:
    return CriterionCheck(
        criterion_check_id=check_id,
        method_run_id=method_run.method_run_id,
        criterion_ref_id=None,
        regulatory_scope=None,
        applicable=CriterionApplicability.UNVERIFIED,
        matching_conditions={},
        limit_value=None,
        limit_unit=None,
        limit_reference_bandwidth_hz=None,
        comparison_operator=None,
        margin_db=None,
        comparison_status=ComparisonStatus.CRITERION_UNVERIFIED,
        review_note="The resolver returned an unusable criterion.",
        citation=None,
    )


def analysis_status_of(method_runs: list[MethodRun]) -> AnalysisStatus:
    if any(run.execution_status is MethodExecution.SUCCEEDED for run in method_runs):
        return AnalysisStatus.READY
    if any(run.execution_status is MethodExecution.FAILED for run in method_runs):
        return AnalysisStatus.FAILED
    if any(run.applicability is MethodApplicability.INSUFFICIENT_DATA for run in method_runs):
        return AnalysisStatus.BLOCKED_BY_INPUTS
    return AnalysisStatus.NOT_APPLICABLE


@dataclass(frozen=True)
class CaseOutcome:
    finding: FindingStatus
    lead: MethodRun | None
    margin_db: float | None
    criterion_status: CriterionApplicability | None


def summarise(method_runs: list[MethodRun], checks: list[CriterionCheck]) -> CaseOutcome:
    """Deliberately cautious. Nothing here ever concludes that there is no concern or a breach."""
    succeeded = [run for run in method_runs if run.execution_status is MethodExecution.SUCCEEDED]
    if not succeeded:
        return CaseOutcome(FindingStatus.INSUFFICIENT_DATA, None, None, None)

    # The lead follows method role and ID, never the most alarming value.
    ordered = sorted(succeeded, key=lambda run: (_ROLE_ORDER[run.role], run.method_id))
    by_method = {run.method_run_id: run for run in ordered}
    compared = [
        check
        for check in checks
        if check.margin_db is not None and check.applicable is CriterionApplicability.VERIFIED
    ]
    exceeded = [check for check in compared if (check.margin_db or 0) > 0]
    if exceeded:
        chosen = min(
            exceeded,
            key=lambda c: (
                _ROLE_ORDER[by_method[c.method_run_id].role],
                c.method_run_id,
                c.criterion_check_id,
            ),
        )
        return CaseOutcome(
            FindingStatus.POTENTIAL_LIMIT_EXCEEDANCE,
            by_method[chosen.method_run_id],
            chosen.margin_db,
            CriterionApplicability.VERIFIED,
        )

    lead = ordered[0]
    lead_checks = [check for check in compared if check.method_run_id == lead.method_run_id]
    if len(lead_checks) == 1:
        margin = lead_checks[0].margin_db
        return CaseOutcome(
            FindingStatus.EXPERT_REVIEW_REQUIRED, lead, margin, CriterionApplicability.VERIFIED
        )
    return CaseOutcome(FindingStatus.EXPERT_REVIEW_REQUIRED, lead, None, None)


def run_analysis(
    sessions: sessionmaker[Session], plugins: AnalysisPlugins, job_id: str, run_id: str
) -> PipelineStatus:
    """Results are written in one transaction at the end, so a retry can never duplicate them."""
    with sessions() as session:
        run = session.get_one(AnalysisRunRow, run_id)
        case = session.get_one(CaseRow, run.case_id)
        if run.analysis_status not in (
            AnalysisStatus.QUEUED.value,
            AnalysisStatus.RUNNING.value,
        ):
            return PipelineStatus.READY
        run.analysis_status = AnalysisStatus.RUNNING.value
        run.software_commit_sha = plugins.build_sha[:64]
        run.method_registry_version = registry_version(plugins)
        session.commit()
        domain = CaseDomain(case.domain)

    method_runs = plan_and_run(run, domain, plugins)
    checks = resolve_criteria(run, method_runs, plugins)
    outcome = summarise(method_runs, checks)

    with sessions() as session:
        run = session.get_one(AnalysisRunRow, run_id)
        case = session.get_one(CaseRow, run.case_id)
        for ordinal, method_run in enumerate(method_runs):
            session.add(
                MethodRunRow(
                    method_run_id=method_run.method_run_id,
                    analysis_run_id=run_id,
                    ordinal=ordinal,
                    result=method_run.model_dump(mode="json"),
                )
            )
        for ordinal, check in enumerate(checks):
            session.add(
                CriterionCheckRow(
                    criterion_check_id=check.criterion_check_id,
                    analysis_run_id=run_id,
                    ordinal=ordinal,
                    result=check.model_dump(mode="json"),
                )
            )
        run.analysis_status = analysis_status_of(method_runs).value

        # A run finishing late must not replace the result of a newer request.
        latest = (
            session.get(AnalysisRunRow, case.latest_analysis_run_id)
            if case.latest_analysis_run_id
            else None
        )
        if latest is None or run.run_created_at_utc >= latest.run_created_at_utc:
            lead = outcome.lead
            case.latest_analysis_run_id = run_id
            case.finding_status = outcome.finding.value
            case.methods_candidates = len(method_runs)
            case.methods_succeeded = sum(
                item.execution_status is MethodExecution.SUCCEEDED for item in method_runs
            )
            case.lead_metric_kind = lead.metric_kind.value if lead and lead.metric_kind else None
            case.lead_numeric_value = lead.numeric_value if lead else None
            case.lead_unit = lead.unit if lead else None
            case.margin_db = outcome.margin_db
            case.criterion_status = (
                outcome.criterion_status.value if outcome.criterion_status else None
            )
            case.updated_at_utc = utc_now()
        emit_event(
            session,
            tenant_id=case.tenant_id,
            event_kind=DomainEventKind.METHOD_COMPLETED.value,
            resource_type="analysis_run",
            resource_id=run_id,
            dedupe_key=f"analysis-complete:{run_id}",
            correlation_id=job_id,
        )
        if outcome.finding is FindingStatus.POTENTIAL_LIMIT_EXCEEDANCE:
            emit_event(
                session,
                tenant_id=case.tenant_id,
                event_kind=DomainEventKind.CRITERION_CHECKED.value,
                resource_type="case",
                resource_id=case.case_id,
                dedupe_key=f"criterion-exceedance:{run_id}",
                correlation_id=job_id,
            )
        session.commit()
    return PipelineStatus.READY
