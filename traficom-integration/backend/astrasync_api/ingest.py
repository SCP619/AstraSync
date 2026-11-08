"""Worker pipeline: staged bytes to verified immutable master to indexed records.

Byte integrity, publisher trust and parse status stay separate throughout. A digest match against
a supplied manifest is never reported as publisher verification. Format parsing belongs to
registered ``SourceAdapter`` implementations; without one, verified bytes stay verified and
unindexed, and the job says why.
"""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session, sessionmaker

from .contract.enums import (
    ArtifactStatus,
    DomainEventKind,
    ErrorCode,
    IntegrityCheckResult,
    PipelineStatus,
    PublisherAuthStatus,
    QualitySeverity,
    RecordStatus,
)
from .contract.interfaces import SourceAdapter
from .contract.models import AdapterRecord, ReferenceStationRecord
from .jobs import PermanentJobError, emit_event, update_progress, utc_now
from .library_tables import (
    ArtifactIntegrityCheckRow,
    RecordDatasetRow,
    RecordQualityFindingRow,
    ReferenceStationRow,
    SourceArtifactRow,
    SourceConnectorRow,
    SourceRecordLocationRow,
    SourceSearchRow,
    UploadPartRow,
    UploadSessionRow,
)
from .objectstore import AssembledObject, ObjectStore
from .record_store import FORMAT_VERSION, DatasetWriter, ParquetRecordStore, PublishedDataset

TOOL_VERSION = "astrasync-ingest/1"
BATCH_ROWS = 1000
UPLOADER_MANIFEST_ORIGIN = "uploader-supplied-manifest"
_FLAGGED = frozenset(
    {RecordStatus.VALID_WITH_WARNINGS, RecordStatus.INSUFFICIENT_DATA, RecordStatus.REVIEW_REQUIRED}
)


@dataclass(frozen=True)
class PipelineContext:
    sessions: sessionmaker[Session]
    store: ObjectStore
    adapters: Mapping[str, SourceAdapter]
    # When set, parsed records go to Parquet datasets instead of the PostgreSQL index tables.
    records: ParquetRecordStore | None = None


@dataclass(frozen=True)
class IncomingBytes:
    """Bytes in staging, with what is claimed about them."""

    tenant_id: str
    source_id: str
    filename_original: str
    classification: str
    staged: AssembledObject
    expected_size_bytes: int | None
    transport_sha256: str | None
    expected_digest: str | None
    expected_digest_origin: str | None
    publisher_signed: bool = False
    publication_id: str | None = None
    published_at_utc: Any = None
    first_seen_at_utc: Any = None


def _add_check(
    session: Session,
    artifact_id: str,
    check_type: str,
    result: IntegrityCheckResult,
    *,
    expected: str | None = None,
    observed: str | None = None,
    trust: PublisherAuthStatus | None = None,
    diagnostic: str | None = None,
) -> None:
    session.add(
        ArtifactIntegrityCheckRow(
            check_id=uuid4().hex,
            artifact_id=artifact_id,
            check_type=check_type,
            value_expected=expected,
            value_observed=observed,
            trust_level=trust.value if trust else None,
            result=result.value,
            tool_version=TOOL_VERSION,
            checked_at_utc=utc_now(),
            diagnostic=diagnostic,
        )
    )


def _publisher_status(incoming: IncomingBytes) -> PublisherAuthStatus:
    if incoming.expected_digest is None:
        return PublisherAuthStatus.NO_PUBLISHER_DIGEST
    if incoming.expected_digest != incoming.staged.sha256:
        return PublisherAuthStatus.MISMATCH
    if incoming.publisher_signed:
        return PublisherAuthStatus.VERIFIED_PUBLISHER
    return PublisherAuthStatus.HASH_MATCH_MANIFEST_UNTRUSTED


def _artifact_type(filename: str) -> str:
    suffix = Path(filename).suffix.lstrip(".").upper()
    return suffix[:32] if suffix else "UNKNOWN"


def register_bytes(context: PipelineContext, incoming: IncomingBytes) -> SourceArtifactRow:
    """Verifies staged bytes and files them as an immutable artifact, or quarantines them.

    The same bytes for the same source produce one artifact and a recorded repeat receipt.
    The same filename with different bytes produces a new revision. Nothing is overwritten.
    """
    staged = incoming.staged
    auth_status = _publisher_status(incoming)
    size_ok = (
        incoming.expected_size_bytes is None or staged.size_bytes == incoming.expected_size_bytes
    )
    transport_ok = incoming.transport_sha256 is None or incoming.transport_sha256 == staged.sha256
    rejected = not size_ok or not transport_ok or auth_status is PublisherAuthStatus.MISMATCH

    with context.sessions() as session:
        existing = session.scalar(
            select(SourceArtifactRow).where(
                SourceArtifactRow.source_id == incoming.source_id,
                SourceArtifactRow.raw_sha256 == staged.sha256,
            )
        )
        if existing is not None and not rejected:
            _add_check(
                session,
                existing.artifact_id,
                "DUPLICATE_RECEIPT",
                IntegrityCheckResult.PASS,
                observed=staged.sha256,
                diagnostic=f"Same bytes received again as {incoming.filename_original[:256]}",
            )
            session.commit()
            staged.path.unlink(missing_ok=True)
            return existing

        revision = (
            session.scalar(
                select(func.coalesce(func.max(SourceArtifactRow.revision), 0)).where(
                    SourceArtifactRow.source_id == incoming.source_id,
                    SourceArtifactRow.filename_original == incoming.filename_original,
                )
            )
            or 0
        ) + 1
        is_synthetic = session.get_one(SourceConnectorRow, incoming.source_id).is_synthetic

    artifact_id = uuid4().hex
    segments = (incoming.tenant_id, incoming.source_id, artifact_id, staged.sha256)
    object_key = (
        context.store.quarantine(staged.path, segments)
        if rejected
        else context.store.promote(staged.path, segments)
    )
    now = utc_now()
    row = SourceArtifactRow(
        artifact_id=artifact_id,
        tenant_id=incoming.tenant_id,
        source_id=incoming.source_id,
        publication_id=incoming.publication_id,
        filename_original=incoming.filename_original,
        artifact_type=_artifact_type(incoming.filename_original),
        raw_sha256=staged.sha256,
        expected_digest=incoming.expected_digest,
        expected_digest_origin=incoming.expected_digest_origin,
        publisher_auth_status=auth_status.value,
        byte_length=staged.size_bytes,
        revision=revision,
        object_key=object_key,
        usage_classification=incoming.classification,
        status=(ArtifactStatus.QUARANTINED if rejected else ArtifactStatus.VERIFIED_BYTES).value,
        analysis_eligible=False,
        published_at_utc=incoming.published_at_utc,
        first_seen_at_utc=incoming.first_seen_at_utc or now,
        download_completed_at_utc=now,
        is_synthetic=is_synthetic,
    )
    with context.sessions() as session:
        session.add(row)
        session.flush()
        _add_check(
            session,
            artifact_id,
            "BYTE_LENGTH",
            IntegrityCheckResult.PASS if size_ok else IntegrityCheckResult.FAIL,
            expected=str(incoming.expected_size_bytes)
            if incoming.expected_size_bytes is not None
            else None,
            observed=str(staged.size_bytes),
        )
        _add_check(
            session,
            artifact_id,
            "TRANSPORT_SHA256",
            IntegrityCheckResult.PASS if transport_ok else IntegrityCheckResult.FAIL,
            expected=incoming.transport_sha256,
            observed=staged.sha256,
        )
        _add_check(
            session,
            artifact_id,
            "PUBLISHER_DIGEST",
            {
                PublisherAuthStatus.NO_PUBLISHER_DIGEST: IntegrityCheckResult.NOT_AVAILABLE,
                PublisherAuthStatus.MISMATCH: IntegrityCheckResult.FAIL,
                PublisherAuthStatus.HASH_MATCH_MANIFEST_UNTRUSTED: IntegrityCheckResult.WARN,
                PublisherAuthStatus.VERIFIED_PUBLISHER: IntegrityCheckResult.PASS,
            }[auth_status],
            expected=incoming.expected_digest,
            observed=staged.sha256,
            trust=auth_status,
            diagnostic=(
                "Matches the digest supplied with the file. This does not prove who published it."
                if auth_status is PublisherAuthStatus.HASH_MATCH_MANIFEST_UNTRUSTED
                else None
            ),
        )
        if rejected:
            emit_event(
                session,
                tenant_id=incoming.tenant_id,
                event_kind=DomainEventKind.ARTIFACT_QUARANTINED.value,
                resource_type="source_artifact",
                resource_id=artifact_id,
                dedupe_key=f"quarantine:{incoming.source_id}:{staged.sha256}",
                correlation_id=artifact_id,
            )
        session.commit()
    return row


def process_upload(context: PipelineContext, job_id: str, upload_id: str) -> PipelineStatus:
    """Safe to retry: once the artifact is linked, a retry resumes from the preserved master."""
    with context.sessions() as session:
        upload = session.get_one(UploadSessionRow, upload_id)
        if upload.artifact_id is not None:
            artifact = session.get_one(SourceArtifactRow, upload.artifact_id)
            return _index_uploaded_artifact(context, job_id, upload_id, artifact)
        parts = session.scalars(
            select(UploadPartRow.part_number)
            .where(UploadPartRow.upload_id == upload_id)
            .order_by(UploadPartRow.part_number)
        ).all()
        upload.status = PipelineStatus.VERIFYING.value
        session.commit()
    update_progress(context.sessions, job_id, status=PipelineStatus.VERIFYING)

    assembled = context.store.assemble(upload_id, parts)
    update_progress(
        context.sessions,
        job_id,
        status=PipelineStatus.VERIFYING,
        processed_bytes=assembled.size_bytes,
    )
    artifact = register_bytes(
        context,
        IncomingBytes(
            tenant_id=upload.tenant_id,
            source_id=upload.source_id,
            filename_original=upload.filename_original,
            classification=upload.usage_classification,
            staged=assembled,
            expected_size_bytes=upload.expected_size_bytes,
            transport_sha256=upload.client_sha256,
            expected_digest=upload.manifest_sha256,
            expected_digest_origin=UPLOADER_MANIFEST_ORIGIN if upload.manifest_sha256 else None,
        ),
    )
    # Link first: the staged parts are only removed once a retry no longer needs them.
    with context.sessions() as session:
        upload = session.get_one(UploadSessionRow, upload_id)
        upload.artifact_id = artifact.artifact_id
        upload.content_sha256 = artifact.raw_sha256
        session.commit()
    context.store.discard_upload(upload_id)

    if artifact.status == ArtifactStatus.QUARANTINED.value:
        code = ErrorCode.UPLOAD_CHECKSUM_MISMATCH
        _close_upload(context, upload_id, PipelineStatus.QUARANTINED, artifact, code)
        raise PermanentJobError(
            code, "The received bytes failed verification.", PipelineStatus.QUARANTINED
        )
    return _index_uploaded_artifact(context, job_id, upload_id, artifact)


def _index_uploaded_artifact(
    context: PipelineContext, job_id: str, upload_id: str, artifact: SourceArtifactRow
) -> PipelineStatus:
    status = process_artifact(context, job_id, artifact.artifact_id)
    failure = ErrorCode.PARSER_UNAVAILABLE if status is PipelineStatus.PARTIAL else None
    _close_upload(context, upload_id, status, artifact, failure)
    return status


def _close_upload(
    context: PipelineContext,
    upload_id: str,
    status: PipelineStatus,
    artifact: SourceArtifactRow,
    failure: ErrorCode | None,
) -> None:
    with context.sessions() as session:
        upload = session.get_one(UploadSessionRow, upload_id)
        upload.status = status.value
        upload.artifact_id = artifact.artifact_id
        upload.content_sha256 = artifact.raw_sha256
        upload.failure_code = failure.value if failure else None
        upload.completed_at_utc = utc_now()
        session.commit()


def process_artifact(context: PipelineContext, job_id: str, artifact_id: str) -> PipelineStatus:
    """Parses and indexes verified bytes. Safe to retry: earlier partial rows are replaced."""
    with context.sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        connector = session.get_one(SourceConnectorRow, artifact.source_id)
        if artifact.status == ArtifactStatus.QUARANTINED.value:
            raise PermanentJobError(
                ErrorCode.CONFLICT,
                "A quarantined artifact cannot be indexed.",
                PipelineStatus.QUARANTINED,
            )
        if artifact.status in (
            ArtifactStatus.INDEXED.value,
            ArtifactStatus.INDEXED_WITH_WARNINGS.value,
        ):
            return PipelineStatus.READY

        adapter = context.adapters.get(connector.source_type)
        if adapter is None:
            _add_check(
                session,
                artifact_id,
                "FORMAT_PARSER",
                IntegrityCheckResult.NOT_AVAILABLE,
                diagnostic=f"No parser is registered for {connector.source_type}.",
            )
            session.commit()
            return PipelineStatus.PARTIAL
        artifact.status = ArtifactStatus.PARSING.value
        object_key = artifact.object_key
        session.commit()

    # A retry replaces whatever an earlier attempt left: partial rows, or unpublished files.
    writer: DatasetWriter | None = None
    if context.records is not None:
        writer = context.records.begin(connector.tenant_id, artifact_id)
    else:
        _clear_partial_index(context.sessions, artifact_id)
    update_progress(context.sessions, job_id, status=PipelineStatus.PARSING)
    path = context.store.local_path(object_key)
    counts = {"parsed": 0, "accepted": 0, "flagged": 0, "rejected": 0}
    try:
        for batch in adapter.iter_record_batches(path, batch_rows=BATCH_ROWS):
            _write_batch(context.sessions, artifact_id, connector, adapter, batch, counts, writer)
            update_progress(
                context.sessions,
                job_id,
                status=PipelineStatus.NORMALIZING,
                processed_records=counts["parsed"],
            )
        published = writer.publish() if writer is not None else None
    except ValueError as exc:
        # The adapter contract's signal for unreadable or unsafe content.
        if writer is not None:
            writer.discard()
        _quarantine_after_parse(context.sessions, artifact_id, adapter, exc)
        raise PermanentJobError(
            ErrorCode.VALIDATION_ERROR,
            "The file could not be read by its parser.",
            PipelineStatus.QUARANTINED,
        ) from exc
    except BaseException:
        if writer is not None:
            writer.discard()
        raise

    status = _finish_index(context.sessions, job_id, artifact_id, adapter, counts, published)
    if connector.source_type in ("SPACE_IFIC", "TERRESTRIAL_IFIC"):
        from .ific_pipeline import enqueue_relevance

        # The issue analysis runs as its own job, so a failure there never un-indexes the issue.
        enqueue_relevance(context.sessions, connector.tenant_id, artifact_id, "system:ingest")
    return status


def _clear_partial_index(sessions: sessionmaker[Session], artifact_id: str) -> None:
    with sessions() as session:
        record_ids = select(SourceRecordLocationRow.source_record_id).where(
            SourceRecordLocationRow.artifact_id == artifact_id
        )
        session.execute(
            delete(RecordQualityFindingRow).where(
                RecordQualityFindingRow.source_record_id.in_(record_ids)
            )
        )
        session.execute(
            delete(ReferenceStationRow).where(ReferenceStationRow.source_record_id.in_(record_ids))
        )
        session.execute(delete(SourceSearchRow).where(SourceSearchRow.artifact_id == artifact_id))
        session.execute(
            delete(SourceRecordLocationRow).where(
                SourceRecordLocationRow.artifact_id == artifact_id
            )
        )
        session.commit()


def _write_batch(
    sessions: sessionmaker[Session],
    artifact_id: str,
    connector: SourceConnectorRow,
    adapter: SourceAdapter,
    batch: list[dict[str, Any]],
    counts: dict[str, int],
    writer: DatasetWriter | None = None,
    *,
    record_checks: bool = True,
) -> None:
    rows = _BatchRows()
    with sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        for raw in batch:
            ordinal = counts["parsed"]
            counts["parsed"] += 1
            try:
                record = AdapterRecord.model_validate(raw)
                station = (
                    ReferenceStationRecord.model_validate(
                        {
                            **record.reference_station,
                            "source_record_id": f"{artifact_id}-{ordinal}",
                            "is_synthetic": artifact.is_synthetic,
                            "parse_status": record.record_status,
                        }
                    )
                    if record.reference_station is not None
                    else None
                )
            except ValidationError as exc:
                counts["rejected"] += 1
                if not record_checks:
                    continue
                # Field locations only: rejected values may be restricted source content.
                locations = sorted({".".join(map(str, e["loc"])) for e in exc.errors()})
                _add_check(
                    session,
                    artifact_id,
                    "RECORD_REJECTED",
                    IntegrityCheckResult.WARN,
                    observed=f"ordinal {ordinal}",
                    diagnostic=f"Invalid fields: {', '.join(locations)}"[:1024],
                )
                continue
            if record.record_status is RecordStatus.INVALID:
                counts["rejected"] += 1
            elif record.record_status in _FLAGGED or any(
                finding.severity is not QualitySeverity.INFO for finding in record.quality_findings
            ):  # An informational note, such as an optional field left blank, is not a flag.
                counts["flagged"] += 1
            else:
                counts["accepted"] += 1
            _collect_rows(rows, artifact, connector, adapter, record, station, ordinal)
        if writer is not None:
            writer.write_batch(rows.locations, rows.searches, rows.stations, rows.findings)
            session.commit()  # Rejected-record checks only.
            return
        # One multi-row insert per table, parents first. A flush per record cost one database
        # round trip per row (about 450 rows/s on PostgreSQL in the Stage 6 benchmark).
        for model, values in (
            (SourceRecordLocationRow, rows.locations),
            (SourceSearchRow, rows.searches),
            (RecordQualityFindingRow, rows.findings),
            (ReferenceStationRow, rows.stations),
        ):
            if values:
                session.execute(insert(model), values)
        session.commit()


@dataclass
class _BatchRows:
    locations: list[dict[str, Any]] = field(default_factory=list)
    searches: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    stations: list[dict[str, Any]] = field(default_factory=list)


def _collect_rows(
    rows: _BatchRows,
    artifact: SourceArtifactRow,
    connector: SourceConnectorRow,
    adapter: SourceAdapter,
    record: AdapterRecord,
    station: ReferenceStationRecord | None,
    ordinal: int,
) -> None:
    record_id = f"{artifact.artifact_id}-{ordinal}"
    canonical = json.dumps(record.raw_fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
    rows.locations.append(
        {
            "source_record_id": record_id,
            "tenant_id": artifact.tenant_id,
            "artifact_id": artifact.artifact_id,
            "ordinal": ordinal,
            "source_table_or_sheet": record.source_table_or_sheet,
            "source_row_or_key": record.source_row_or_key,
            "source_page": record.source_page,
            "notice_id": record.notice_id,
            "raw_record_sha256": hashlib.sha256(canonical).hexdigest(),
            "raw_fields": record.raw_fields,
            "field_aliases": record.field_aliases,
            "analysis_eligibility": {
                method: status.value for method, status in record.analysis_eligibility.items()
            },
            "parser_version": adapter.parser_version,
            "schema_version": record.schema_version,
        }
    )
    terms = " ".join(
        term
        for term in (
            artifact.filename_original,
            record.notice_id,
            record.station_number,
            record.network_id,
            record.administration,
            record.issue_key,
        )
        if term
    )
    rows.searches.append(
        {
            "source_record_id": record_id,
            "tenant_id": artifact.tenant_id,
            "source_id": artifact.source_id,
            "artifact_id": artifact.artifact_id,
            "issue_key": record.issue_key,
            "publisher": connector.publisher,
            "filename_original": artifact.filename_original,
            "station_number": record.station_number,
            "network_id": record.network_id,
            "administration": record.administration,
            "frequency_start_mhz": record.frequency_start_mhz,
            "frequency_end_mhz": record.frequency_end_mhz,
            "text_terms": terms.lower(),
            "classification": artifact.usage_classification,
            "record_status": record.record_status.value,
            "is_synthetic": artifact.is_synthetic,
        }
    )
    for index, finding in enumerate(record.quality_findings):
        rows.findings.append(
            {
                "finding_id": f"{record_id}-{index}",
                "source_record_id": record_id,
                "field_key": finding.field_key,
                "raw_value": finding.raw_value,
                "normalized_value": finding.normalized_value,
                "rule_id": finding.rule_id,
                "severity": finding.severity.value,
                "status": "OPEN",
            }
        )
    if station is not None:
        rows.stations.append(
            {
                "source_record_id": record_id,
                "fields": station.model_dump(mode="json", exclude={"source_record_id"}),
            }
        )


def _finish_index(
    sessions: sessionmaker[Session],
    job_id: str,
    artifact_id: str,
    adapter: SourceAdapter,
    counts: dict[str, int],
    published: PublishedDataset | None = None,
) -> PipelineStatus:
    update_progress(
        sessions, job_id, status=PipelineStatus.INDEXING, processed_records=counts["parsed"]
    )
    warnings = counts["flagged"] > 0 or counts["rejected"] > 0
    with sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        artifact.status = (
            ArtifactStatus.INDEXED_WITH_WARNINGS if warnings else ArtifactStatus.INDEXED
        ).value
        artifact.analysis_eligible = True
        artifact.indexed_at_utc = utc_now()
        artifact.parser_version = adapter.parser_version
        artifact.row_reconciliation = counts
        if published is not None:
            # Committed with the indexed status: the dataset becomes visible with it, or not at all.
            session.add(_dataset_row(session, artifact, adapter, published))
        _add_check(
            session,
            artifact_id,
            "ROW_RECONCILIATION",
            IntegrityCheckResult.WARN if warnings else IntegrityCheckResult.PASS,
            observed=json.dumps(counts, sort_keys=True),
        )
        emit_event(
            session,
            tenant_id=artifact.tenant_id,
            event_kind=DomainEventKind.ARTIFACT_INDEXED.value,
            resource_type="source_artifact",
            resource_id=artifact_id,
            dedupe_key=f"indexed:{artifact_id}",
            correlation_id=job_id,
        )
        session.commit()
    return PipelineStatus.READY


def _dataset_row(
    session: Session,
    artifact: SourceArtifactRow,
    adapter: SourceAdapter,
    published: PublishedDataset,
) -> RecordDatasetRow:
    connector = session.get_one(SourceConnectorRow, artifact.source_id)
    return RecordDatasetRow(
        artifact_id=artifact.artifact_id,
        tenant_id=artifact.tenant_id,
        source_id=artifact.source_id,
        classification=artifact.usage_classification,
        is_synthetic=artifact.is_synthetic,
        publisher=connector.publisher,
        filename_original=artifact.filename_original,
        relative_path=published.relative_path,
        format_version=FORMAT_VERSION,
        parser_version=adapter.parser_version,
        record_count=published.record_count,
        finding_count=published.finding_count,
        records_sha256=published.records_sha256,
        records_bytes=published.records_bytes,
        findings_sha256=published.findings_sha256,
        findings_bytes=published.findings_bytes,
        published_at_utc=utc_now(),
    )


class DatasetBuildRefused(RuntimeError):
    """The record dataset of an indexed artifact cannot be built faithfully."""


def build_record_dataset(context: PipelineContext, artifact_id: str) -> RecordDatasetRow:
    """Writes the Parquet dataset of an artifact indexed before the record store was enabled.

    The immutable master is parsed again with the same parser version, so the records are the
    ones the PostgreSQL index holds. Publication is refused unless every reconciliation count
    equals the artifact's recorded counts. Idempotent: an existing dataset is returned as it is.
    The PostgreSQL index rows are left in place.
    """
    if context.records is None:
        raise DatasetBuildRefused("No record store is configured.")
    with context.sessions() as session:
        existing = session.get(RecordDatasetRow, artifact_id)
        if existing is not None:
            return existing
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        connector = session.get_one(SourceConnectorRow, artifact.source_id)
        if artifact.status not in (
            ArtifactStatus.INDEXED.value,
            ArtifactStatus.INDEXED_WITH_WARNINGS.value,
        ):
            raise DatasetBuildRefused(f"The artifact is {artifact.status}, not indexed.")
        adapter = context.adapters.get(connector.source_type)
        if adapter is None:
            raise DatasetBuildRefused(f"No parser is registered for {connector.source_type}.")
        if adapter.parser_version != artifact.parser_version:
            raise DatasetBuildRefused(
                f"Indexed with {artifact.parser_version}, but {adapter.parser_version} is loaded."
            )
        expected = dict(artifact.row_reconciliation or {})
        object_key = artifact.object_key
    writer = context.records.begin(connector.tenant_id, artifact_id)
    counts = {"parsed": 0, "accepted": 0, "flagged": 0, "rejected": 0}
    try:
        path = context.store.local_path(object_key)
        for batch in adapter.iter_record_batches(path, batch_rows=BATCH_ROWS):
            _write_batch(
                context.sessions,
                artifact_id,
                connector,
                adapter,
                batch,
                counts,
                writer,
                record_checks=False,
            )
        if counts != expected:
            raise DatasetBuildRefused(f"Counts {counts} differ from the recorded {expected}.")
        published = writer.publish()
    except BaseException:
        writer.discard()
        raise
    with context.sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        row = _dataset_row(session, artifact, adapter, published)
        session.add(row)
        _add_check(
            session,
            artifact_id,
            "RECORD_DATASET",
            IntegrityCheckResult.PASS,
            expected=json.dumps(expected, sort_keys=True),
            observed=json.dumps(counts, sort_keys=True),
        )
        session.commit()
    return row


def _quarantine_after_parse(
    sessions: sessionmaker[Session], artifact_id: str, adapter: SourceAdapter, exc: ValueError
) -> None:
    _clear_partial_index(sessions, artifact_id)
    with sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        artifact.status = ArtifactStatus.QUARANTINED.value
        artifact.analysis_eligible = False
        artifact.parser_version = adapter.parser_version
        _add_check(
            session,
            artifact_id,
            "FORMAT_PARSER",
            IntegrityCheckResult.FAIL,
            # The exception type only: its message could contain restricted file content.
            diagnostic=f"Parser rejected the file: {type(exc).__name__}",
        )
        emit_event(
            session,
            tenant_id=artifact.tenant_id,
            event_kind=DomainEventKind.ARTIFACT_QUARANTINED.value,
            resource_type="source_artifact",
            resource_id=artifact_id,
            dedupe_key=f"quarantine:{artifact.source_id}:{artifact.raw_sha256}",
            correlation_id=artifact_id,
        )
        session.commit()

