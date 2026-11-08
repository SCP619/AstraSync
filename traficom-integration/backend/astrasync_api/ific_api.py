"""Read API for IFIC issue analyses (DECISIONS G27). Source READ rights apply to every row."""

import gzip
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .authz import ObjectAccessPolicy, ObjectRef, not_found
from .contract import CONTRACT_VERSION
from .contract.enums import UsageClassification
from .contract.models import IficAnalysis, IficAnalysisList, IficFinding, IficFindingList
from .contract.permissions import Role
from .identity import Principal
from .ific_tables import IficAnalysisRow
from .library_tables import SourceConnectorRow
from .objectstore import ObjectStore

RIGHT_READ = "READ"
TIERS = ("HIGH", "MEDIUM", "LOW")


def _envelope() -> dict[str, Any]:
    return {"schema_version": CONTRACT_VERSION, "generated_at_utc": datetime.now(UTC)}


def _readable(
    session: Session, policy: ObjectAccessPolicy, principal: Principal, row: IficAnalysisRow
) -> bool:
    """READ on the IFIC source and on every reference source the findings were derived from,
    so a restricted reference can never surface through a less restricted issue."""
    references = (row.summary.get("references") or {}).get("reference_sources") or []
    return all(
        _source_readable(session, policy, principal, source_id)
        for source_id in (row.source_id, *references)
    )


def _source_readable(
    session: Session, policy: ObjectAccessPolicy, principal: Principal, source_id: str
) -> bool:
    connector = session.get(SourceConnectorRow, source_id)
    if connector is None or connector.tenant_id != principal.tenant_id:
        return False
    if Role.DEMO_VIEWER in principal.roles and not connector.is_synthetic:
        return False
    target = ObjectRef(
        object_type="source",
        object_id=connector.source_id,
        tenant_id=connector.tenant_id,
        classification=UsageClassification(connector.usage_classification),
        is_synthetic=connector.is_synthetic,
    )
    return policy.can_access(principal, target, RIGHT_READ)


def _view(row: IficAnalysisRow) -> IficAnalysis:
    return IficAnalysis(
        analysis_id=row.analysis_id,
        source_id=row.source_id,
        artifact_id=row.artifact_id,
        previous_artifact_id=row.previous_artifact_id,
        kind=row.kind,
        issue=row.issue,
        rule_version=row.rule_version,
        status=row.status,
        findings_count=row.findings_count,
        cases_created=row.cases_created,
        findings_sha256=row.findings_sha256,
        summary=row.summary,
        created_at_utc=row.created_at_utc,
    )


def list_analyses(
    session: Session, policy: ObjectAccessPolicy, principal: Principal, limit: int
) -> IficAnalysisList:
    rows = session.scalars(
        select(IficAnalysisRow)
        .where(IficAnalysisRow.tenant_id == principal.tenant_id)
        .order_by(IficAnalysisRow.issue.desc(), IficAnalysisRow.analysis_id)
    ).all()
    items = [_view(r) for r in rows if _readable(session, policy, principal, r)][:limit]
    return IficAnalysisList(
        **_envelope(), items=items, limit=limit, next_cursor=None, total_if_known=len(items)
    )


_CACHE: dict[tuple[str, str | None], list[dict[str, Any]]] = {}


def _load(key: str, sha256: str | None, store: ObjectStore) -> list[dict[str, Any]]:
    """Findings are immutable once stored, so a small cache by key and digest is safe."""
    cached = _CACHE.get((key, sha256))
    if cached is not None:
        return cached
    with store.open_read(key) as handle:
        payload = gzip.decompress(handle.read())
    if sha256 is not None and hashlib.sha256(payload).hexdigest() != sha256:
        raise ValueError("Stored findings do not match their recorded SHA-256")
    findings: list[dict[str, Any]] = json.loads(payload)["findings"]
    if len(_CACHE) >= 8:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[(key, sha256)] = findings
    return findings


def _finding(rank: int, f: dict[str, Any]) -> IficFinding:
    space = f["domain"] == "SPACE"
    value = f.get("max_pfd") if space else f.get("max_field_strength")
    return IficFinding(
        rank=rank,
        notice_id=str(f["notice_id"]),
        domain=f["domain"],
        administration=f.get("administration"),
        label=(f.get("satellite_name") or f.get("earth_station_name"))
        if space
        else f.get("site_name"),
        change_type=f["change"]["change_type"],
        priority_score=f["priority"]["score"],
        priority_tier=f["priority"]["tier"],
        finding_status=f["finding_status"],
        max_value=value,
        max_value_unit=(f.get("max_pfd_unit") if space else "dB(uV/m)")
        if value is not None
        else None,
        detail=f,
    )


def list_findings(
    session: Session,
    policy: ObjectAccessPolicy,
    principal: Principal,
    store: ObjectStore,
    analysis_id: str,
    tier: str | None,
    limit: int,
    cursor: str | None,
) -> IficFindingList:
    row = session.get(IficAnalysisRow, analysis_id)
    if row is None or not _readable(session, policy, principal, row):
        raise not_found()
    if row.findings_object_key is None:
        raise not_found()
    findings = _load(row.findings_object_key, row.findings_sha256, store)
    ranked = [(i + 1, f) for i, f in enumerate(findings)]
    if tier is not None:
        ranked = [(i, f) for i, f in ranked if f["priority"]["tier"] == tier]
    start = int(cursor) if cursor and cursor.isdecimal() else 0
    page = ranked[start : start + limit]
    following = start + limit
    return IficFindingList(
        **_envelope(),
        analysis_id=analysis_id,
        items=[_finding(rank, f) for rank, f in page],
        limit=limit,
        next_cursor=str(following) if following < len(ranked) else None,
        total_if_known=len(ranked),
    )
