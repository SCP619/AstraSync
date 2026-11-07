"""Source registry, immutable artifacts, indexed records, uploads and jobs (BSD 6.2 and 9).

Every row carries ``tenant_id``, so that every query can be tenant-scoped at execution.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UtcDateTime


class SourceConnectorRow(Base):
    __tablename__ = "source_connectors"

    source_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    publisher: Mapped[str] = mapped_column(String(256))
    domain: Mapped[str] = mapped_column(String(32))
    source_type: Mapped[str] = mapped_column(String(64))
    discovery_mode: Mapped[str] = mapped_column(String(32))
    # A registered client name and a secret-vault reference. Never a credential.
    endpoint_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    auth_secret_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    rights_basis: Mapped[str] = mapped_column(String(512))
    usage_classification: Mapped[str] = mapped_column(String(32))
    poll_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_cadence_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_success_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class SourceObservationRow(Base):
    """A publication seen at the source. Discovery only adds or updates, and never deletes."""

    __tablename__ = "source_observations"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "provider_issue_key", "version_key", name="uq_source_observation"
        ),
    )

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"), index=True)
    provider_issue_key: Mapped[str] = mapped_column(String(256))
    provider_version: Mapped[str | None] = mapped_column(String(256), nullable=True)
    version_key: Mapped[str] = mapped_column(String(256))
    published_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    first_seen_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    last_seen_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    remote_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    observation_status: Mapped[str] = mapped_column(String(32))
    usage_classification: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    remote: Mapped[dict[str, Any]] = mapped_column(JSON)


class SourceArtifactRow(Base):
    """An immutable master. A changed file is a new revision, and old bytes stay retrievable."""

    __tablename__ = "source_artifacts"
    __table_args__ = (
        UniqueConstraint("source_id", "raw_sha256", name="uq_source_artifact_bytes"),
    )

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"), index=True)
    publication_id: Mapped[str | None] = mapped_column(
        ForeignKey("source_observations.observation_id"), nullable=True
    )
    filename_original: Mapped[str] = mapped_column(String(512), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32))
    raw_sha256: Mapped[str] = mapped_column(String(64), index=True)
    expected_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_digest_origin: Mapped[str | None] = mapped_column(String(256), nullable=True)
    publisher_auth_status: Mapped[str] = mapped_column(String(64))
    byte_length: Mapped[int] = mapped_column(BigInteger)
    revision: Mapped[int] = mapped_column(Integer)
    object_key: Mapped[str] = mapped_column(String(512))
    usage_classification: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    analysis_eligible: Mapped[bool] = mapped_column(Boolean)
    published_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    first_seen_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    download_completed_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    indexed_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_reconciliation: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class ArtifactIntegrityCheckRow(Base):
    __tablename__ = "artifact_integrity_checks"

    check_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.artifact_id"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(64))
    value_expected: Mapped[str | None] = mapped_column(String(512), nullable=True)
    value_observed: Mapped[str | None] = mapped_column(String(512), nullable=True)
    trust_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(32))
    tool_version: Mapped[str] = mapped_column(String(64))
    checked_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    diagnostic: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class SourceRecordLocationRow(Base):
    """Points a parsed record at its exact original location, and keeps its raw values."""

    __tablename__ = "source_record_locations"
    __table_args__ = (
        UniqueConstraint("artifact_id", "ordinal", name="uq_source_record_ordinal"),
    )

    source_record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.artifact_id"))
    ordinal: Mapped[int] = mapped_column(BigInteger)
    source_table_or_sheet: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_row_or_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    raw_record_sha256: Mapped[str] = mapped_column(String(64))
    raw_fields: Mapped[dict[str, str | None]] = mapped_column(JSON)
    field_aliases: Mapped[dict[str, list[str]]] = mapped_column(JSON)
    analysis_eligibility: Mapped[dict[str, str]] = mapped_column(JSON)
    parser_version: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(64))


class SourceSearchRow(Base):
    """Permission-filtered search index. Filtering happens in the query, not in the client."""

    __tablename__ = "source_library_search_index"
    __table_args__ = (
        Index("ix_search_frequency", "frequency_start_mhz", "frequency_end_mhz"),
    )

    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("source_record_locations.source_record_id"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"), index=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.artifact_id"), index=True
    )
    issue_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    publisher: Mapped[str] = mapped_column(String(256))
    filename_original: Mapped[str] = mapped_column(String(512))
    station_number: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    network_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    administration: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frequency_start_mhz: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_end_mhz: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_terms: Mapped[str] = mapped_column(Text)
    classification: Mapped[str] = mapped_column(String(32))
    record_status: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)


class RecordQualityFindingRow(Base):
    __tablename__ = "record_quality_findings"

    finding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("source_record_locations.source_record_id"), index=True
    )
    field_key: Mapped[str] = mapped_column(String(256))
    raw_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32))
    reviewer_override_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ReferenceStationRow(Base):
    """Normalized station fields, validated against ``ReferenceStationRecord`` when written."""

    __tablename__ = "reference_station_records"

    source_record_id: Mapped[str] = mapped_column(
        ForeignKey("source_record_locations.source_record_id"), primary_key=True
    )
    fields: Mapped[dict[str, Any]] = mapped_column(JSON)


class UploadSessionRow(Base):
    __tablename__ = "upload_sessions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "created_by", "idempotency_key", name="uq_upload_idempotency"
        ),
    )

    upload_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"))
    source_type: Mapped[str] = mapped_column(String(64))
    usage_classification: Mapped[str] = mapped_column(String(32))
    filename_original: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32))
    expected_size_bytes: Mapped[int] = mapped_column(BigInteger)
    received_size_bytes: Mapped[int] = mapped_column(BigInteger)
    part_size_bytes: Mapped[int] = mapped_column(BigInteger)
    max_size_bytes: Mapped[int] = mapped_column(BigInteger)
    # The digest supplied with a manifest, if any, as distinct from the client's own hash.
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    expires_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    completed_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class UploadPartRow(Base):
    __tablename__ = "upload_parts"

    upload_id: Mapped[str] = mapped_column(
        ForeignKey("upload_sessions.upload_id"), primary_key=True
    )
    part_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    etag: Mapped[str] = mapped_column(String(64))


class JobRunRow(Base):
    """A durable queue entry. A worker holds a job only while its lease is valid."""

    __tablename__ = "job_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_type", "idempotency_key", name="uq_job_idempotency"),
        Index("ix_job_claim", "lane", "status", "next_attempt_at_utc"),
    )

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    job_type: Mapped[str] = mapped_column(String(32))
    lane: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    progress_stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    processed_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    processed_records: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_records_if_known: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer)
    max_attempts: Mapped[int] = mapped_column(Integer)
    next_attempt_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    requested_by: Mapped[str] = mapped_column(String(128))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    started_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    finished_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class OutboxEventRow(Base):
    """Written in the same transaction as the change. Stage 7 alert rules consume it."""

    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("tenant_id", "dedupe_key", name="uq_outbox_dedupe"),)

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    event_kind: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(128))
    correlation_id: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(String(256))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    occurred_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    consumed_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
