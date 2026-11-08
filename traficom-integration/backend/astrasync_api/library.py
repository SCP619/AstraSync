"""Source library queries. Each read is permission-filtered in the query or checked per object.

A restricted object a user may not read gets the same 404 as one that does not exist.
"""

import base64
import binascii
import math
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .acquisition import request_check
from .authz import ObjectAccessPolicy, ObjectRef, not_found
from .contract import CONTRACT_VERSION
from .contract.enums import (
    ArtifactStatus,
    DiscoveryMode,
    ErrorCode,
    JobType,
    ObservationStatus,
    PipelineStatus,
    SourceHealthStatus,
    UsageClassification,
)
from .contract.models import (
    STATION_FIELDS_ADDED_LATER,
    ArtifactIntegrityCheck,
    ArtifactIntegrityReport,
    DownloadLink,
    JobAccepted,
    JobRun,
    RecordQualityFinding,
    ReferenceStationRecord,
    RowReconciliation,
    SourceArtifact,
    SourceArtifactDetail,
    SourceArtifactList,
    SourceConnector,
    SourceConnectorList,
    SourceHealth,
    SourceLocation,
    SourceLocationDetail,
    SourcePreview,
    SourcePreviewRow,
    SourcePublication,
    SourcePublicationList,
    SourceRecordDetail,
    SourceRecordHit,
    SourceRecordList,
    UploadCompleteRequest,
    UploadCreateRequest,
    UploadPartState,
    UploadPartUrl,
    UploadPartUrls,
    UploadPartUrlsRequest,
    UploadSession,
)
from .contract.permissions import Role
from .errors import ApiError
from .identity import IdentityStore, Principal
from .jobs import LANE_INGESTION, TERMINAL_VALUES, enqueue, utc_now
from .library_tables import (
    ArtifactIntegrityCheckRow,
    JobRunRow,
    RecordDatasetRow,
    RecordQualityFindingRow,
    ReferenceStationRow,
    SourceArtifactRow,
    SourceConnectorRow,
    SourceObservationRow,
    SourceRecordLocationRow,
    SourceSearchRow,
    UploadPartRow,
    UploadSessionRow,
)
from .objectstore import ObjectStore
from .record_store import ParquetRecordStore, dataset_for_record, readable_datasets

PART_SIZE_BYTES = 64 * 1024 * 1024
UPLOAD_LIFETIME = timedelta(hours=24)
PART_URL_LIFETIME = timedelta(hours=1)
DOWNLOAD_LINK_LIFETIME = timedelta(minutes=5)
PREVIEW_ROWS = 50
RIGHT_READ = "READ"
RIGHT_DOWNLOAD = "DOWNLOAD"
RIGHT_IMPORT = "IMPORT"
# Stricter classifications sort higher. An import may tighten a source's level, not relax it.
_CLASSIFICATION_RANK = {
    UsageClassification.PUBLIC: 0,
    UsageClassification.INTERNAL: 1,
    UsageClassification.UNVERIFIED: 2,
    UsageClassification.RESTRICTED: 3,
    UsageClassification.CONFIDENTIAL_PARTNER: 4,
}
_INDEXED = (ArtifactStatus.INDEXED.value, ArtifactStatus.INDEXED_WITH_WARNINGS.value)


@dataclass(frozen=True)
class LibraryRuntime:
    policy: ObjectAccessPolicy
    identities: IdentityStore
    store: ObjectStore | None
    max_upload_bytes: int
    # When set, parsed records are read from Parquet datasets instead of the index tables.
    records: ParquetRecordStore | None = None


def _envelope() -> dict[str, Any]:
    return {"schema_version": CONTRACT_VERSION, "generated_at_utc": utc_now()}


def _cursor_decode(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode()).decode()
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Invalid cursor.") from exc
    # The decoder skips invalid characters, so only a value this API could issue is accepted.
    if _cursor_encode(decoded) != cursor:
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Invalid cursor.")
    return decoded


def _cursor_encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode()


def _page(rows: list[Any], limit: int, key: str) -> tuple[list[Any], str | None]:
    """Rows were fetched with ``limit + 1``, so an extra row means another page exists."""
    if len(rows) <= limit:
        return rows, None
    kept = rows[:limit]
    return kept, _cursor_encode(str(getattr(kept[-1], key)))


def _audit_object_denial(
    runtime: LibraryRuntime, request: Request, principal: Principal, kind: str, object_id: str
) -> None:
    runtime.identities.record_audit(
        actor=principal.user_id,
        tenant_id=principal.tenant_id,
        action=request.scope["route"].name,
        object_type=kind,
        object_id=object_id,
        outcome="DENIED_OBJECT",
        correlation_id=request.state.request_id,
    )


def _require_source_right(
    runtime: LibraryRuntime,
    request: Request,
    principal: Principal,
    *,
    source_id: str,
    classification: str,
    is_synthetic: bool,
    right: str,
    tenant_id: str,
) -> None:
    target = ObjectRef(
        object_type="source",
        object_id=source_id,
        tenant_id=tenant_id,
        classification=UsageClassification(classification),
        is_synthetic=is_synthetic,
    )
    if not runtime.policy.can_access(principal, target, right):
        _audit_object_denial(runtime, request, principal, "source", source_id)
        raise not_found()


# --- Connectors -------------------------------------------------------------------------------


def _connector_for(session: Session, principal: Principal, source_id: str) -> SourceConnectorRow:
    """Connector status is tenant metadata, without credentials, locators or file names."""
    row = session.get(SourceConnectorRow, source_id)
    if row is None or row.tenant_id != principal.tenant_id:
        raise not_found()
    if Role.DEMO_VIEWER in principal.roles and not row.is_synthetic:
        raise not_found()
    return row


def _connector_view(row: SourceConnectorRow) -> SourceConnector:
    return SourceConnector(
        source_id=row.source_id,
        publisher=row.publisher,
        domain=row.domain,
        source_type=row.source_type,
        discovery_mode=row.discovery_mode,
        rights_basis=row.rights_basis,
        usage_classification=row.usage_classification,
        poll_interval_seconds=row.poll_interval_seconds,
        last_checked_at_utc=row.last_checked_at_utc,
        last_success_at_utc=row.last_success_at_utc,
        status=_effective_status(row),
        is_synthetic=row.is_synthetic,
    )


def _effective_status(row: SourceConnectorRow) -> SourceHealthStatus:
    """A connector that has not succeeded recently is stale, whatever its last result was."""
    if row.discovery_mode == DiscoveryMode.MANUAL_TRANSFER.value:
        return SourceHealthStatus.MANUAL_REQUIRED
    status = SourceHealthStatus(row.status)
    cadence = row.expected_cadence_seconds
    if status is SourceHealthStatus.HEALTHY and cadence is not None:
        last = row.last_success_at_utc
        if last is None or (utc_now() - last).total_seconds() > 2 * cadence:
            return SourceHealthStatus.SOURCE_STALE
    return status


def list_sources(
    session: Session, principal: Principal, limit: int, cursor: str | None
) -> SourceConnectorList:
    query = select(SourceConnectorRow).where(SourceConnectorRow.tenant_id == principal.tenant_id)
    if Role.DEMO_VIEWER in principal.roles:
        query = query.where(SourceConnectorRow.is_synthetic.is_(True))
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(SourceConnectorRow.source_id > after)
    rows = list(session.scalars(query.order_by(SourceConnectorRow.source_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "source_id")
    return SourceConnectorList(
        **_envelope(),
        items=[_connector_view(row) for row in kept],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def source_health(session: Session, principal: Principal, source_id: str) -> SourceHealth:
    row = _connector_for(session, principal, source_id)
    latest = session.scalar(
        select(SourceObservationRow.provider_issue_key)
        .where(SourceObservationRow.source_id == source_id)
        .order_by(SourceObservationRow.first_seen_at_utc.desc())
        .limit(1)
    )
    pending = session.scalars(
        select(JobRunRow.job_id).where(
            JobRunRow.tenant_id == principal.tenant_id,
            JobRunRow.job_type.in_([JobType.ACQUIRE.value, JobType.SOURCE_DISCOVERY.value]),
            JobRunRow.status.not_in(sorted(TERMINAL_VALUES)),
        )
    ).all()
    return SourceHealth(
        **_envelope(),
        source_id=source_id,
        status=_effective_status(row),
        discovery_mode=row.discovery_mode,
        latest_known_issue_key=latest,
        last_checked_at_utc=row.last_checked_at_utc,
        last_success_at_utc=row.last_success_at_utc,
        expected_cadence_seconds=row.expected_cadence_seconds,
        pending_index_jobs=len(pending),
        failure_code=row.failure_code,
        failure_summary=row.failure_summary,
    )


# --- Publications and artifacts ---------------------------------------------------------------


def list_publications(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    source_id: str | None,
    issue: str | None,
    status: ObservationStatus | None,
    limit: int,
    cursor: str | None,
) -> SourcePublicationList:
    table = SourceObservationRow
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
    if source_id is not None:
        query = query.where(table.source_id == source_id)
    if issue is not None:
        query = query.where(table.provider_issue_key == issue)
    if status is not None:
        query = query.where(table.observation_status == status.value)
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(table.observation_id > after)
    rows = list(session.scalars(query.order_by(table.observation_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "observation_id")
    return SourcePublicationList(
        **_envelope(),
        items=[
            SourcePublication(
                publication_id=row.observation_id,
                source_id=row.source_id,
                provider_issue_key=row.provider_issue_key,
                provider_version=row.provider_version,
                published_at_utc=row.published_at_utc,
                first_seen_at_utc=row.first_seen_at_utc,
                last_seen_at_utc=row.last_seen_at_utc,
                remote_size_bytes=row.remote_size_bytes,
                observation_status=row.observation_status,
                is_synthetic=row.is_synthetic,
            )
            for row in kept
        ],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def _artifact_fields(row: SourceArtifactRow) -> dict[str, Any]:
    return {
        "artifact_id": row.artifact_id,
        "source_id": row.source_id,
        "publication_id": row.publication_id,
        "filename_original": row.filename_original,
        "artifact_type": row.artifact_type,
        "raw_sha256": row.raw_sha256,
        "expected_digest": row.expected_digest,
        "expected_digest_origin": row.expected_digest_origin,
        "publisher_auth_status": row.publisher_auth_status,
        "byte_length": row.byte_length,
        "revision": row.revision,
        "usage_classification": row.usage_classification,
        "status": row.status,
        "analysis_eligible": row.analysis_eligible,
        "published_at_utc": row.published_at_utc,
        "first_seen_at_utc": row.first_seen_at_utc,
        "download_completed_at_utc": row.download_completed_at_utc,
        "indexed_at_utc": row.indexed_at_utc,
        "parser_version": row.parser_version,
        "is_synthetic": row.is_synthetic,
    }


def list_artifacts(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    source_id: str | None,
    filename: str | None,
    sha256: str | None,
    status: ArtifactStatus | None,
    limit: int,
    cursor: str | None,
) -> SourceArtifactList:
    table = SourceArtifactRow
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
    if source_id is not None:
        query = query.where(table.source_id == source_id)
    if filename is not None:
        query = query.where(table.filename_original.icontains(filename, autoescape=True))
    if sha256 is not None:
        query = query.where(table.raw_sha256 == sha256)
    if status is not None:
        query = query.where(table.status == status.value)
    after = _cursor_decode(cursor)
    if after is not None:
        query = query.where(table.artifact_id > after)
    rows = list(session.scalars(query.order_by(table.artifact_id).limit(limit + 1)))
    kept, next_cursor = _page(rows, limit, "artifact_id")
    return SourceArtifactList(
        **_envelope(),
        items=[SourceArtifact(**_artifact_fields(row)) for row in kept],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def _readable_artifact(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
    right: str = RIGHT_READ,
) -> SourceArtifactRow:
    row = session.get(SourceArtifactRow, artifact_id)
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


def get_artifact(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> SourceArtifactDetail:
    row = _readable_artifact(runtime, request, session, principal, artifact_id)
    return SourceArtifactDetail(**_envelope(), **_artifact_fields(row))


def get_integrity(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> ArtifactIntegrityReport:
    row = _readable_artifact(runtime, request, session, principal, artifact_id)
    checks = session.scalars(
        select(ArtifactIntegrityCheckRow)
        .where(ArtifactIntegrityCheckRow.artifact_id == artifact_id)
        .order_by(ArtifactIntegrityCheckRow.checked_at_utc, ArtifactIntegrityCheckRow.check_id)
    ).all()
    return ArtifactIntegrityReport(
        **_envelope(),
        artifact_id=artifact_id,
        raw_sha256=row.raw_sha256,
        byte_length=row.byte_length,
        publisher_auth_status=row.publisher_auth_status,
        status=row.status,
        checks=[
            ArtifactIntegrityCheck(
                check_id=check.check_id,
                check_type=check.check_type,
                value_expected=check.value_expected,
                value_observed=check.value_observed,
                trust_level=check.trust_level,
                result=check.result,
                tool_version=check.tool_version,
                checked_at_utc=check.checked_at_utc,
                diagnostic=check.diagnostic,
            )
            for check in checks
        ],
        row_reconciliation=(
            RowReconciliation(**row.row_reconciliation) if row.row_reconciliation else None
        ),
        is_synthetic=row.is_synthetic,
    )


def _location_view(
    location: SourceRecordLocationRow, artifact: SourceArtifactRow
) -> SourceLocation:
    return SourceLocation(
        source_record_id=location.source_record_id,
        artifact_id=location.artifact_id,
        raw_sha256=artifact.raw_sha256,
        source_table_or_sheet=location.source_table_or_sheet,
        source_row_or_key=location.source_row_or_key,
        source_page=location.source_page,
        notice_id=location.notice_id,
        raw_record_sha256=location.raw_record_sha256,
        parser_version=location.parser_version,
        record_schema_version=location.schema_version,
        is_synthetic=artifact.is_synthetic,
    )


def get_preview(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
    *,
    page: int | None,
    table: str | None,
    row: int | None,
    cursor: str | None,
) -> SourcePreview:
    """Reads stored index rows only. The master file is not opened or transferred."""
    artifact = _readable_artifact(runtime, request, session, principal, artifact_id)
    if artifact.status not in _INDEXED:
        raise ApiError(
            409,
            ErrorCode.CONFLICT,
            "No preview is available: this file has not been indexed. The original is preserved.",
            {"status": artifact.status},
        )
    after = _cursor_decode(cursor)
    if after is not None and not after.isdecimal():
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Invalid cursor.")
    if runtime.records is not None:
        dataset = session.get(RecordDatasetRow, artifact_id)
        rows = (
            runtime.records.preview(
                dataset,
                page=page,
                table=table,
                row=row,
                after_ordinal=int(after) if after is not None else None,
                limit=PREVIEW_ROWS + 1,
            )
            if dataset is not None
            else []
        )
    else:
        rows = _preview_rows(session, artifact_id, page=page, table=table, row=row, after=after)
    kept, next_cursor = _page(rows, PREVIEW_ROWS, "ordinal")
    return SourcePreview(
        **_envelope(),
        artifact_id=artifact_id,
        rows=[
            SourcePreviewRow(location=_location_view(item, artifact), cells=item.raw_fields)
            for item in kept
        ],
        next_cursor=next_cursor,
        is_synthetic=artifact.is_synthetic,
    )


def _preview_rows(
    session: Session,
    artifact_id: str,
    *,
    page: int | None,
    table: str | None,
    row: int | None,
    after: str | None,
) -> list[SourceRecordLocationRow]:
    locations = SourceRecordLocationRow
    query = select(locations).where(locations.artifact_id == artifact_id)
    if page is not None:
        query = query.where(locations.source_page == page)
    if table is not None:
        query = query.where(locations.source_table_or_sheet == table)
    if row is not None:
        query = query.where(locations.source_row_or_key == str(row))
    if after is not None:
        query = query.where(locations.ordinal > int(after))
    return list(session.scalars(query.order_by(locations.ordinal).limit(PREVIEW_ROWS + 1)))


def create_download_link(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> DownloadLink:
    artifact = _download_target(runtime, request, session, principal, artifact_id)
    return DownloadLink(
        **_envelope(),
        artifact_id=artifact_id,
        url=f"/api/v1/source-artifacts/{artifact_id}/content",
        expires_at_utc=utc_now() + DOWNLOAD_LINK_LIFETIME,
        byte_length=artifact.byte_length,
        raw_sha256=artifact.raw_sha256,
    )


def _download_target(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> SourceArtifactRow:
    artifact = _readable_artifact(
        runtime, request, session, principal, artifact_id, right=RIGHT_DOWNLOAD
    )
    if artifact.status == ArtifactStatus.QUARANTINED.value:
        raise ApiError(409, ErrorCode.CONFLICT, "A quarantined file cannot be downloaded.")
    return artifact


def open_artifact_content(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> tuple[SourceArtifactRow, Any]:
    if runtime.store is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE, "Object storage is not configured.")
    artifact = _download_target(runtime, request, session, principal, artifact_id)
    return artifact, runtime.store.open_read(artifact.object_key)


# --- Records ----------------------------------------------------------------------------------


def search_records(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    query_text: str | None,
    station_number: str | None,
    frequency_start_mhz: float | None,
    frequency_end_mhz: float | None,
    limit: int,
    cursor: str | None,
) -> SourceRecordList:
    if runtime.records is not None:
        rows = runtime.records.search(
            readable_datasets(session, runtime.policy, principal),
            query_text=query_text,
            station_number=station_number,
            frequency_start_mhz=frequency_start_mhz,
            frequency_end_mhz=frequency_end_mhz,
            after=_cursor_decode(cursor),
            limit=limit + 1,
        )
    else:
        rows = _search_index(
            runtime,
            session,
            principal,
            query_text=query_text,
            station_number=station_number,
            frequency_start_mhz=frequency_start_mhz,
            frequency_end_mhz=frequency_end_mhz,
            after=_cursor_decode(cursor),
            limit=limit,
        )
    kept, next_cursor = _page(rows, limit, "source_record_id")
    return SourceRecordList(
        **_envelope(),
        items=[
            SourceRecordHit(
                source_record_id=row.source_record_id,
                source_id=row.source_id,
                artifact_id=row.artifact_id,
                issue_key=row.issue_key,
                publisher=row.publisher,
                filename_original=row.filename_original,
                station_number=row.station_number,
                network_id=row.network_id,
                administration=row.administration,
                frequency_start_mhz=row.frequency_start_mhz,
                frequency_end_mhz=row.frequency_end_mhz,
                classification=row.classification,
                record_status=row.record_status,
                is_synthetic=row.is_synthetic,
            )
            for row in kept
        ],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def _search_index(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    query_text: str | None,
    station_number: str | None,
    frequency_start_mhz: float | None,
    frequency_end_mhz: float | None,
    after: str | None,
    limit: int,
) -> list[SourceSearchRow]:
    table = SourceSearchRow
    query = select(table).where(
        runtime.policy.readable_clause(
            principal,
            RIGHT_READ,
            tenant_column=table.tenant_id,
            source_column=table.source_id,
            classification_column=table.classification,
            synthetic_column=table.is_synthetic,
        )
    )
    if query_text:
        query = query.where(table.text_terms.contains(query_text.lower(), autoescape=True))
    if station_number is not None:
        query = query.where(table.station_number == station_number)
    # Interval overlap. A record without a usable frequency cannot match a frequency filter.
    if frequency_start_mhz is not None:
        query = query.where(table.frequency_end_mhz >= frequency_start_mhz)
    if frequency_end_mhz is not None:
        query = query.where(table.frequency_start_mhz <= frequency_end_mhz)
    if after is not None:
        query = query.where(table.source_record_id > after)
    return list(session.scalars(query.order_by(table.source_record_id).limit(limit + 1)))


def _readable_record(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    source_record_id: str,
) -> tuple[SourceRecordLocationRow, SourceArtifactRow, SourceSearchRow]:
    if runtime.records is not None:
        found = dataset_for_record(session, source_record_id, principal.tenant_id)
        if found is None:
            raise not_found()
        artifact = _readable_artifact(runtime, request, session, principal, found[0].artifact_id)
        record = runtime.records.record(*found)
        if record is None:
            raise not_found()
        return record[0], artifact, record[1]
    location = session.get(SourceRecordLocationRow, source_record_id)
    if location is None or location.tenant_id != principal.tenant_id:
        raise not_found()
    artifact = _readable_artifact(runtime, request, session, principal, location.artifact_id)
    return location, artifact, session.get_one(SourceSearchRow, source_record_id)


def _findings_and_station(
    runtime: LibraryRuntime, session: Session, location: SourceRecordLocationRow
) -> tuple[list[RecordQualityFindingRow], ReferenceStationRow | None]:
    if runtime.records is not None:
        dataset = session.get_one(RecordDatasetRow, location.artifact_id)
        record = runtime.records.record(dataset, location.ordinal)
        station = record[2] if record is not None else None
        return runtime.records.findings(dataset, location.ordinal), station
    findings = session.scalars(
        select(RecordQualityFindingRow)
        .where(RecordQualityFindingRow.source_record_id == location.source_record_id)
        .order_by(RecordQualityFindingRow.finding_id)
    ).all()
    return list(findings), session.get(ReferenceStationRow, location.source_record_id)


def get_record(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    source_record_id: str,
) -> SourceRecordDetail:
    location, artifact, search = _readable_record(
        runtime, request, session, principal, source_record_id
    )
    findings, station = _findings_and_station(runtime, session, location)
    return SourceRecordDetail(
        **_envelope(),
        source_record_id=source_record_id,
        location=_location_view(location, artifact),
        record_status=search.record_status,
        field_aliases=location.field_aliases,
        raw_fields=location.raw_fields,
        reference_station=(
            ReferenceStationRecord(
                source_record_id=source_record_id,
                **{**dict.fromkeys(STATION_FIELDS_ADDED_LATER), **station.fields},
            )
            if station is not None
            else None
        ),
        quality_findings=[
            RecordQualityFinding(
                finding_id=finding.finding_id,
                source_record_id=finding.source_record_id,
                field_key=finding.field_key,
                raw_value=finding.raw_value,
                normalized_value=finding.normalized_value,
                rule_id=finding.rule_id,
                severity=finding.severity,
                status=finding.status,
                reviewer_override_id=finding.reviewer_override_id,
            )
            for finding in findings
        ],
        analysis_eligibility=location.analysis_eligibility,
        is_synthetic=artifact.is_synthetic,
    )


def get_record_location(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    source_record_id: str,
) -> SourceLocationDetail:
    location, artifact, _ = _readable_record(
        runtime, request, session, principal, source_record_id
    )
    return SourceLocationDetail(**_envelope(), **_location_view(location, artifact).model_dump())


# --- Uploads ----------------------------------------------------------------------------------


def _upload_view(session: Session, row: UploadSessionRow) -> UploadSession:
    parts = session.scalars(
        select(UploadPartRow)
        .where(UploadPartRow.upload_id == row.upload_id)
        .order_by(UploadPartRow.part_number)
    ).all()
    return UploadSession(
        **_envelope(),
        upload_id=row.upload_id,
        status=row.status,
        source_type=row.source_type,
        usage_classification=row.usage_classification,
        filename_original=row.filename_original,
        expected_size_bytes=row.expected_size_bytes,
        received_size_bytes=row.received_size_bytes,
        part_size_bytes=row.part_size_bytes,
        max_size_bytes=row.max_size_bytes,
        parts=[
            UploadPartState(
                part_number=part.part_number,
                size_bytes=part.size_bytes,
                etag=part.etag,
                received=True,
            )
            for part in parts
        ],
        content_sha256=row.content_sha256,
        job_id=row.job_id,
        failure_code=row.failure_code,
        created_at_utc=row.created_at_utc,
        expires_at_utc=row.expires_at_utc,
        completed_at_utc=row.completed_at_utc,
    )


def create_upload(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    body: UploadCreateRequest,
    idempotency_key: str,
) -> UploadSession:
    if runtime.store is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE, "Object storage is not configured.")
    existing = session.scalar(
        select(UploadSessionRow).where(
            UploadSessionRow.tenant_id == principal.tenant_id,
            UploadSessionRow.created_by == principal.user_id,
            UploadSessionRow.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return _upload_view(session, existing)

    connector = _connector_for(session, principal, body.source_id)
    if connector.source_type != body.source_type.value:
        raise ApiError(409, ErrorCode.CONFLICT, "This source does not accept that source type.")
    if (
        _CLASSIFICATION_RANK[body.usage_classification]
        < _CLASSIFICATION_RANK[UsageClassification(connector.usage_classification)]
    ):
        raise ApiError(
            409, ErrorCode.CONFLICT, "An import cannot be less restricted than its source."
        )
    _require_source_right(
        runtime,
        request,
        principal,
        source_id=connector.source_id,
        classification=body.usage_classification.value,
        is_synthetic=connector.is_synthetic,
        right=RIGHT_IMPORT,
        tenant_id=connector.tenant_id,
    )
    if body.expected_size_bytes > runtime.max_upload_bytes:
        raise ApiError(
            413,
            ErrorCode.UPLOAD_TOO_LARGE,
            "This file is larger than this deployment accepts.",
            {"max_size_bytes": runtime.max_upload_bytes},
        )
    now = utc_now()
    row = UploadSessionRow(
        upload_id=uuid4().hex,
        tenant_id=principal.tenant_id,
        created_by=principal.user_id,
        idempotency_key=idempotency_key,
        source_id=connector.source_id,
        source_type=body.source_type.value,
        usage_classification=body.usage_classification.value,
        filename_original=body.filename_original,
        status=PipelineStatus.CREATED.value,
        expected_size_bytes=body.expected_size_bytes,
        received_size_bytes=0,
        part_size_bytes=PART_SIZE_BYTES,
        max_size_bytes=runtime.max_upload_bytes,
        manifest_sha256=body.content_sha256,
        created_at_utc=now,
        expires_at_utc=now + UPLOAD_LIFETIME,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return create_upload(runtime, request, session, principal, body, idempotency_key)
    return _upload_view(session, row)


def _visible_upload(session: Session, principal: Principal, upload_id: str) -> UploadSessionRow:
    """The owner, or an administrator of the same tenant for operations."""
    row = session.get(UploadSessionRow, upload_id)
    if row is None or row.tenant_id != principal.tenant_id:
        raise not_found()
    if row.created_by != principal.user_id and Role.ADMINISTRATOR not in principal.roles:
        raise not_found()
    return row


def _owned_open_upload(session: Session, principal: Principal, upload_id: str) -> UploadSessionRow:
    row = session.get(UploadSessionRow, upload_id)
    if row is None or row.tenant_id != principal.tenant_id or row.created_by != principal.user_id:
        raise not_found()
    return row


def _require_receiving(row: UploadSessionRow) -> None:
    if row.status not in (PipelineStatus.CREATED.value, PipelineStatus.UPLOADING.value):
        raise ApiError(409, ErrorCode.CONFLICT, "This upload is no longer receiving data.")
    if utc_now() > row.expires_at_utc:
        raise ApiError(409, ErrorCode.CONFLICT, "This upload has expired. Start a new one.")


def get_upload(session: Session, principal: Principal, upload_id: str) -> UploadSession:
    return _upload_view(session, _visible_upload(session, principal, upload_id))


def part_count(row: UploadSessionRow) -> int:
    return math.ceil(row.expected_size_bytes / row.part_size_bytes)


def expected_part_size(row: UploadSessionRow, part_number: int) -> int:
    total = part_count(row)
    if part_number < total:
        return row.part_size_bytes
    return row.expected_size_bytes - (total - 1) * row.part_size_bytes


def part_urls(
    session: Session, principal: Principal, upload_id: str, body: UploadPartUrlsRequest
) -> UploadPartUrls:
    """Fresh URLs at any time, so that a long or resumed transfer outlives any single URL."""
    row = _owned_open_upload(session, principal, upload_id)
    _require_receiving(row)
    total = part_count(row)
    if any(number > total for number in body.part_numbers):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Part number is outside this upload.")
    expires = utc_now() + PART_URL_LIFETIME
    return UploadPartUrls(
        **_envelope(),
        upload_id=upload_id,
        parts=[
            UploadPartUrl(
                part_number=number,
                url=f"/api/v1/uploads/{upload_id}/parts/{number}",
                expires_at_utc=expires,
            )
            for number in body.part_numbers
        ],
    )


def open_part_upload(
    session: Session, principal: Principal, upload_id: str, part_number: int
) -> UploadSessionRow:
    row = _owned_open_upload(session, principal, upload_id)
    _require_receiving(row)
    if part_number > part_count(row):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Part number is outside this upload.")
    return row


def record_part(
    session: Session, upload_id: str, part_number: int, size_bytes: int, etag: str
) -> UploadPartUrl:
    existing = session.get(UploadPartRow, (upload_id, part_number))
    if existing is None:
        session.add(
            UploadPartRow(
                upload_id=upload_id, part_number=part_number, size_bytes=size_bytes, etag=etag
            )
        )
    else:
        existing.size_bytes = size_bytes
        existing.etag = etag
    session.flush()
    row = session.get_one(UploadSessionRow, upload_id)
    sizes = session.scalars(
        select(UploadPartRow.size_bytes).where(UploadPartRow.upload_id == upload_id)
    ).all()
    row.received_size_bytes = sum(sizes)
    row.status = PipelineStatus.UPLOADING.value
    session.commit()
    return UploadPartUrl(
        part_number=part_number,
        url=f"/api/v1/uploads/{upload_id}/parts/{part_number}",
        expires_at_utc=utc_now() + PART_URL_LIFETIME,
    )


def complete_upload(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    upload_id: str,
    body: UploadCompleteRequest,
) -> UploadSession:
    """Checks the manifest here. The worker hashes the assembled bytes before they are trusted."""
    row = _owned_open_upload(session, principal, upload_id)
    if row.job_id is not None:
        return _upload_view(session, row)  # A repeat of a completed call starts nothing new.
    _require_receiving(row)

    stored = {
        part.part_number: part
        for part in session.scalars(
            select(UploadPartRow).where(UploadPartRow.upload_id == upload_id)
        )
    }
    required = set(range(1, part_count(row) + 1))
    named = {part.part_number: part.etag for part in body.parts}
    if set(stored) != required or set(named) != required:
        raise ApiError(
            409,
            ErrorCode.UPLOAD_INCOMPLETE,
            "Some parts are missing.",
            {"missing_parts": sorted(required - set(stored))[:100]},
        )
    if any(stored[number].etag != etag for number, etag in named.items()):
        raise ApiError(
            409, ErrorCode.UPLOAD_CHECKSUM_MISMATCH, "A part does not match what was received."
        )
    if row.received_size_bytes != row.expected_size_bytes:
        raise ApiError(
            409, ErrorCode.UPLOAD_INCOMPLETE, "The received size differs from the declared size."
        )

    row.client_sha256 = body.content_sha256
    row.status = PipelineStatus.QUEUED.value
    session.commit()
    job = enqueue(
        session_factory_of(session),
        tenant_id=row.tenant_id,
        job_type=JobType.INGEST,
        lane=LANE_INGESTION,
        idempotency_key=f"upload:{upload_id}",
        requested_by=principal.user_id,
        resource_id=upload_id,
        payload={"upload_id": upload_id},
    )
    row.job_id = job.job_id
    session.commit()
    return _upload_view(session, row)


def abort_upload(
    runtime: LibraryRuntime, session: Session, principal: Principal, upload_id: str
) -> UploadSession:
    row = _owned_open_upload(session, principal, upload_id)
    if row.status == PipelineStatus.CANCELLED.value:
        return _upload_view(session, row)
    if row.status not in (PipelineStatus.CREATED.value, PipelineStatus.UPLOADING.value):
        raise ApiError(409, ErrorCode.CONFLICT, "This upload can no longer be cancelled.")
    row.status = PipelineStatus.CANCELLED.value
    row.completed_at_utc = utc_now()
    session.commit()
    if runtime.store is not None:
        runtime.store.discard_upload(upload_id)
    return _upload_view(session, row)


def session_factory_of(session: Session) -> sessionmaker[Session]:
    """A new-session factory on the same engine, for work committed separately."""
    return sessionmaker(session.get_bind(), expire_on_commit=False)


# --- Jobs -------------------------------------------------------------------------------------


def get_job(session: Session, principal: Principal, job_id: str) -> JobRun:
    """The requester, or an administrator of the same tenant for operations."""
    row = session.get(JobRunRow, job_id)
    if row is None or row.tenant_id != principal.tenant_id:
        raise not_found()
    if row.requested_by != principal.user_id and Role.ADMINISTRATOR not in principal.roles:
        raise not_found()
    return JobRun(
        **_envelope(),
        job_id=row.job_id,
        job_type=row.job_type,
        resource_id=row.resource_id,
        status=row.status,
        progress_stage=row.progress_stage,
        processed_bytes=row.processed_bytes,
        processed_records=row.processed_records,
        total_records_if_known=row.total_records_if_known,
        attempt=row.attempt,
        max_attempts=row.max_attempts,
        started_at_utc=row.started_at_utc,
        finished_at_utc=row.finished_at_utc,
        error_code=row.error_code,
    )


def ingest_artifact(
    runtime: LibraryRuntime,
    request: Request,
    session: Session,
    principal: Principal,
    artifact_id: str,
) -> JobAccepted:
    """Runs a parser over bytes already preserved, such as after a parser becomes available."""
    artifact = _readable_artifact(
        runtime, request, session, principal, artifact_id, right=RIGHT_IMPORT
    )
    if artifact.status == ArtifactStatus.QUARANTINED.value:
        raise ApiError(409, ErrorCode.CONFLICT, "A quarantined file cannot be ingested.")
    job = enqueue(
        session_factory_of(session),
        tenant_id=artifact.tenant_id,
        job_type=JobType.INGEST,
        lane=LANE_INGESTION,
        idempotency_key=f"artifact:{artifact_id}:{request.headers['Idempotency-Key']}",
        requested_by=principal.user_id,
        resource_id=artifact_id,
        payload={"artifact_id": artifact_id},
    )
    return JobAccepted(**_envelope(), job_id=job.job_id, status=job.status)


def check_source(session: Session, principal: Principal, source_id: str) -> JobAccepted:
    connector = _connector_for(session, principal, source_id)
    if connector.discovery_mode == DiscoveryMode.MANUAL_TRANSFER.value:
        raise ApiError(
            409,
            ErrorCode.MANUAL_REQUIRED,
            "This source has no permitted automated check. An operator must import it manually.",
        )
    job_id = request_check(session_factory_of(session), connector, principal.user_id)
    return JobAccepted(**_envelope(), job_id=job_id, status=PipelineStatus.QUEUED)

