"""IFIC issue analyses: one row per analysed IFIC artifact (DECISIONS G27)."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UtcDateTime


class IficAnalysisRow(Base):
    __tablename__ = "ific_analyses"

    analysis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_connectors.source_id"), index=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("source_artifacts.artifact_id"), index=True, unique=True
    )
    previous_artifact_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    issue: Mapped[int] = mapped_column(Integer, index=True)
    publication_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rule_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    findings_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    findings_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    findings_count: Mapped[int] = mapped_column(Integer)
    cases_created: Mapped[int] = mapped_column(Integer)
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)
