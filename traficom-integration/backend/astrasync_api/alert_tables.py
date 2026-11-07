"""Alert rules, alerts, deliveries, acknowledgments and devices (BSD 6.1, 6.3)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, UtcDateTime


class AlertRuleRow(Base):
    """Each edit is a new version. An alert records the exact version that created it."""

    __tablename__ = "alert_rules"

    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    trigger_kind: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean)
    evidence_requirement: Mapped[str] = mapped_column(String(64))
    routing_roles: Mapped[list[str]] = mapped_column(JSON)
    dedupe_window_seconds: Mapped[int] = mapped_column(Integer)
    ack_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_policy: Mapped[dict[str, Any]] = mapped_column(JSON)
    updated_by: Mapped[str] = mapped_column(String(128))
    updated_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class AlertRow(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("rule_id", "event_id", name="uq_alert_rule_event"),
        Index("ix_alert_dedupe", "tenant_id", "dedupe_key", "created_at_utc"),
    )

    alert_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    event_id: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.case_id"), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    usage_classification: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(128))
    rule_version: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(32))
    safe_title: Mapped[str] = mapped_column(String(128))
    safe_preview: Mapped[str] = mapped_column(String(256))
    push_category: Mapped[str] = mapped_column(String(32))
    evidence_refs: Mapped[list[str]] = mapped_column(JSON)
    dedupe_key: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(32))
    is_synthetic: Mapped[bool] = mapped_column(Boolean)
    ack_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_policy: Mapped[dict[str, Any]] = mapped_column(JSON)
    escalated_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    expires_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class AlertDeliveryRow(Base):
    """Sent, delivered and read stay distinct. The in-app row is what puts an alert in an inbox."""

    __tablename__ = "alert_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "alert_id", "recipient_user_id", "channel", "device_key", name="uq_alert_delivery"
        ),
        Index("ix_delivery_inbox", "recipient_user_id", "channel", "sent_at_utc"),
        Index("ix_delivery_pending", "state", "next_attempt_at_utc"),
    )

    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.alert_id"), index=True)
    recipient_user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"))
    channel: Mapped[str] = mapped_column(String(16))
    device_key: Mapped[str] = mapped_column(String(64))
    attempt: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16))
    provider_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    next_attempt_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    sent_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    last_attempt_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    delivered_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AlertAcknowledgmentRow(Base):
    __tablename__ = "alert_acknowledgments"
    __table_args__ = (UniqueConstraint("alert_id", "actor_id", name="uq_alert_ack"),)

    ack_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.alert_id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(128))
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    acknowledged_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class AlertPreferenceRow(Base):
    __tablename__ = "alert_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    enabled_channels: Mapped[list[str]] = mapped_column(JSON)
    quiet_hours_start_utc: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end_utc: Mapped[str | None] = mapped_column(String(5), nullable=True)


class RegisteredDeviceRow(Base):
    """Push tokens belong to devices, are encrypted at rest, and are never returned."""

    __tablename__ = "registered_devices"

    device_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    platform: Mapped[str] = mapped_column(String(16))
    token_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    push_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    status: Mapped[str] = mapped_column(String(16))
    last_seen_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
