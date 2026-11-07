"""Cases, immutable analysis results, drafts and review history (BSD 3.4 to 3.9).

Method runs, criterion checks and review events are insert-only. On PostgreSQL a trigger rejects
any update or delete, so a stored result or decision cannot be changed after the fact.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UtcDateTime


class FinlandRelevanceRow(Base):
    __tablename__ = "finland_relevance_checks"

    relevance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    notice_uid: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(64))
    reason_codes: Mapped[list[str]] = mapped_column(JSON)
    rule_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    overlap_start_mhz: Mapped[float | None] = mapped_column(Float, nullable=True)
    overlap_end_mhz: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency_match: Mapped[bool] = mapped_column(Boolean)
    service_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    geometry_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    technical_data_ready: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    criterion_available: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class CaseRow(Base):
    __tablename__ = "cases"
    __table_args__ = (UniqueConstraint("tenant_id", "notice_uid", name="uq_case_notice"),)

    case_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"), index=True)
    source_issue_id: Mapped[str] = mapped_column(String(128), index=True)
    notice_uid: Mapped[str] = mapped_column(String(128))
    notice_id: Mapped[str] = mapped_column(String(128), index=True)
    administration: Mapped[str | None] = mapped_column(String(128), nullable=True)
    domain: Mapped[str] = mapped_column(String(32))
    change_type: Mapped[str] = mapped_column(String(32))
    frequency_start_mhz: Mapped[float] = mapped_column(Float, index=True)
    frequency_end_mhz: Mapped[float] = mapped_column(Float)
    usage_classification: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    relevance_id: Mapped[str] = mapped_column(ForeignKey("finland_relevance_checks.relevance_id"))
    scenario_id: Mapped[str] = mapped_column(String(128))
    scenario: Mapped[dict[str, Any]] = mapped_column(JSON)
    finding_status: Mapped[str] = mapped_column(String(64), index=True)
    review_status: Mapped[str] = mapped_column(String(32), index=True)
    priority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    priority_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    methods_succeeded: Mapped[int] = mapped_column(Integer)
    methods_candidates: Mapped[int] = mapped_column(Integer)
    lead_metric_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lead_numeric_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    lead_unit: Mapped[str | None] = mapped_column(String(128), nullable=True)
    margin_db: Mapped[float | None] = mapped_column(Float, nullable=True)
    criterion_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
    updated_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class AnalysisRunRow(Base):
    """Inputs are frozen when the run is requested. Only its status changes afterwards."""

    __tablename__ = "analysis_runs"
    __table_args__ = (UniqueConstraint("case_id", "idempotency_key", name="uq_analysis_request"),)

    analysis_run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    scenario_id: Mapped[str] = mapped_column(String(128))
    scenario_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_snapshot_sha256: Mapped[str] = mapped_column(String(64))
    software_commit_sha: Mapped[str] = mapped_column(String(64))
    method_registry_version: Mapped[str] = mapped_column(String(64))
    reference_snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(32))
    created_by: Mapped[str] = mapped_column(String(128))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class MethodRunRow(Base):
    __tablename__ = "method_runs"

    method_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class CriterionCheckRow(Base):
    __tablename__ = "criterion_checks"

    criterion_check_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSON)


class EvidenceLinkRow(Base):
    __tablename__ = "evidence_links"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    label: Mapped[str] = mapped_column(String(256))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(128))
    source_issue_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_locator: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    verified_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class DraftRow(Base):
    __tablename__ = "drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    draft_type: Mapped[str] = mapped_column(String(32))
    source_analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.analysis_run_id")
    )
    content_markdown: Mapped[str] = mapped_column(Text)
    citations: Mapped[list[str]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    ai_model_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    generation_provenance: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[str] = mapped_column(String(128))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class ReviewEventRow(Base):
    __tablename__ = "review_events"
    __table_args__ = (
        UniqueConstraint("case_id", "actor_id", "idempotency_key", name="uq_review_request"),
    )

    review_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.case_id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))
    decision_reason: Mapped[str] = mapped_column(Text)
    analysis_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    draft_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    occurred_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class ReferenceDocumentRow(Base):
    __tablename__ = "reference_documents"

    reference_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    authority: Mapped[str] = mapped_column(String(256))
    document_title: Mapped[str] = mapped_column(String(512))
    edition: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publication_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    snapshot_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_verified_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    usage_classification: Mapped[str] = mapped_column(String(32))
