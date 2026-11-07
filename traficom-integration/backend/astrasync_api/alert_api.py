"""Alert inbox, acknowledgments, preferences, devices and rule administration.

An alert is visible only to its recipients, and a case alert only while the recipient can still
read that case. Denials are the same 404 as a missing alert, so that an ID reveals nothing.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import Request
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .alert_tables import (
    AlertAcknowledgmentRow,
    AlertDeliveryRow,
    AlertPreferenceRow,
    AlertRow,
    AlertRuleRow,
    RegisteredDeviceRow,
)
from .alerts import TokenCipher, latest_rules, token_digest
from .contract.enums import (
    AlertChannel,
    AlertDeliveryState,
    AlertSeverity,
    AlertStatus,
    DeviceStatus,
    DomainEventKind,
    ErrorCode,
)
from .contract.models import (
    AlertAcknowledged,
    AlertAcknowledgeRequest,
    AlertAcknowledgment,
    AlertDelivery,
    AlertDetail,
    AlertList,
    AlertPreferences,
    AlertPreferencesUpdate,
    AlertRule,
    AlertRuleList,
    AlertRuleSaved,
    AlertRuleUpsert,
    AlertSummary,
    Device,
    DeviceRegistrationRequest,
)
from .errors import ApiError
from .identity import Principal
from .jobs import emit_event, utc_now
from .library import LibraryRuntime, _cursor_decode, _cursor_encode, _envelope

_RIGHT_READ = "READ"
_STREAM_REAUTH_SECONDS = 30.0


def _alert_not_found() -> ApiError:
    return ApiError(404, ErrorCode.ALERT_NOT_FOUND, "The requested alert was not found.")


def _visible_clause(runtime: LibraryRuntime, principal: Principal) -> ColumnElement[bool]:
    """Non-case alerts carry no case content. Case alerts follow the case's own access rules."""
    return or_(
        AlertRow.case_id.is_(None),
        runtime.policy.readable_clause(
            principal,
            _RIGHT_READ,
            tenant_column=AlertRow.tenant_id,
            source_column=AlertRow.source_id,
            classification_column=AlertRow.usage_classification,
            synthetic_column=AlertRow.is_synthetic,
        ),
    )


def _summary_fields(row: AlertRow) -> dict[str, Any]:
    return {
        "alert_id": row.alert_id,
        "event_id": row.event_id,
        "case_id": row.case_id,
        "rule_id": row.rule_id,
        "rule_version": row.rule_version,
        "severity": row.severity,
        "safe_title": row.safe_title,
        "safe_preview": row.safe_preview,
        "status": row.status,
        "created_at_utc": row.created_at_utc,
        "expires_at_utc": row.expires_at_utc,
        "is_synthetic": row.is_synthetic,
    }


def _inbox_query(runtime: LibraryRuntime, principal: Principal) -> Any:
    return (
        select(AlertRow)
        .join(AlertDeliveryRow, AlertDeliveryRow.alert_id == AlertRow.alert_id)
        .where(
            AlertDeliveryRow.recipient_user_id == principal.user_id,
            AlertDeliveryRow.channel == AlertChannel.IN_APP.value,
            AlertRow.tenant_id == principal.tenant_id,
            _visible_clause(runtime, principal),
        )
    )


def list_alerts(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    *,
    status: AlertStatus | None,
    severity: AlertSeverity | None,
    limit: int,
    cursor: str | None,
) -> AlertList:
    query = _inbox_query(runtime, principal)
    if status is not None:
        query = query.where(AlertRow.status == status.value)
    if severity is not None:
        query = query.where(AlertRow.severity == severity.value)
    decoded = _cursor_decode(cursor)
    if decoded is not None:
        try:
            created, alert_id = json.loads(decoded)
            created_at = datetime.fromisoformat(created)
        except (ValueError, TypeError) as exc:
            raise ApiError(422, ErrorCode.VALIDATION_ERROR, "Invalid cursor.") from exc
        query = query.where(
            or_(
                AlertRow.created_at_utc < created_at,
                (AlertRow.created_at_utc == created_at) & (AlertRow.alert_id < alert_id),
            )
        )
    rows = list(
        session.scalars(
            query.order_by(AlertRow.created_at_utc.desc(), AlertRow.alert_id.desc()).limit(
                limit + 1
            )
        )
    )
    kept = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = kept[-1]
        next_cursor = _cursor_encode(json.dumps([last.created_at_utc.isoformat(), last.alert_id]))
    return AlertList(
        **_envelope(),
        items=[AlertSummary(**_summary_fields(row)) for row in kept],
        limit=limit,
        next_cursor=next_cursor,
        total_if_known=None,
    )


def _visible_alert(
    runtime: LibraryRuntime, session: Session, principal: Principal, alert_id: str
) -> AlertRow:
    row: AlertRow | None = session.scalars(
        _inbox_query(runtime, principal).where(AlertRow.alert_id == alert_id)
    ).first()
    if row is None:
        raise _alert_not_found()
    return row


def _acknowledgment_fields(row: AlertAcknowledgmentRow) -> dict[str, Any]:
    return {
        "ack_id": row.ack_id,
        "alert_id": row.alert_id,
        "actor_id": row.actor_id,
        "comment": row.comment,
        "acknowledged_at_utc": row.acknowledged_at_utc,
    }


def get_alert(
    runtime: LibraryRuntime, session: Session, principal: Principal, alert_id: str
) -> AlertDetail:
    """Opening an alert marks the caller's in-app copy read. Identity is re-checked on each call."""
    row = _visible_alert(runtime, session, principal, alert_id)
    deliveries = list(
        session.scalars(
            select(AlertDeliveryRow).where(
                AlertDeliveryRow.alert_id == alert_id,
                AlertDeliveryRow.recipient_user_id == principal.user_id,
            )
        )
    )
    for delivery in deliveries:
        if delivery.channel == AlertChannel.IN_APP.value:
            delivery.state = AlertDeliveryState.READ.value
    session.commit()
    acknowledgments = session.scalars(
        select(AlertAcknowledgmentRow)
        .where(AlertAcknowledgmentRow.alert_id == alert_id)
        .order_by(AlertAcknowledgmentRow.acknowledged_at_utc)
    )
    return AlertDetail(
        **_envelope(),
        **_summary_fields(row),
        evidence_refs=row.evidence_refs,
        deliveries=[
            AlertDelivery(
                delivery_id=item.delivery_id,
                channel=item.channel,
                # A push that has not been attempted yet still counts as attempt 1 for display.
                attempt=max(item.attempt, 1),
                state=item.state,
                last_attempt_at_utc=item.last_attempt_at_utc,
                delivered_at_utc=item.delivered_at_utc,
                failure_code=item.failure_code,
            )
            for item in deliveries
        ],
        acknowledgments=[
            AlertAcknowledgment(**_acknowledgment_fields(item)) for item in acknowledgments
        ],
    )


def acknowledge(
    runtime: LibraryRuntime,
    session: Session,
    principal: Principal,
    alert_id: str,
    body: AlertAcknowledgeRequest,
) -> AlertAcknowledged:
    """Idempotent: a repeat, or a tap on a second device, returns the first acknowledgment."""
    row = _visible_alert(runtime, session, principal, alert_id)
    existing = session.scalar(
        select(AlertAcknowledgmentRow).where(
            AlertAcknowledgmentRow.alert_id == alert_id,
            AlertAcknowledgmentRow.actor_id == principal.user_id,
        )
    )
    if existing is not None:
        return AlertAcknowledged(**_envelope(), **_acknowledgment_fields(existing))
    ack = AlertAcknowledgmentRow(
        ack_id=uuid4().hex,
        alert_id=alert_id,
        actor_id=principal.user_id,
        comment=body.comment,
        acknowledged_at_utc=utc_now(),
    )
    session.add(ack)
    if row.status == AlertStatus.OPEN.value:
        row.status = AlertStatus.ACKNOWLEDGED.value
    emit_event(
        session,
        tenant_id=row.tenant_id,
        event_kind=DomainEventKind.ALERT_ACKNOWLEDGED.value,
        resource_type="alert",
        resource_id=alert_id,
        dedupe_key=f"ack:{ack.ack_id}",
        correlation_id=row.event_id,
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return acknowledge(runtime, session, principal, alert_id, body)
    return AlertAcknowledged(**_envelope(), **_acknowledgment_fields(ack))


def get_preferences(session: Session, principal: Principal) -> AlertPreferences:
    row = session.get(AlertPreferenceRow, principal.user_id)
    return AlertPreferences(
        **_envelope(),
        enabled_channels=(
            row.enabled_channels
            if row
            else [AlertChannel.IN_APP, AlertChannel.WINDOWS, AlertChannel.ANDROID]
        ),
        quiet_hours_start_utc=row.quiet_hours_start_utc if row else None,
        quiet_hours_end_utc=row.quiet_hours_end_utc if row else None,
    )


def update_preferences(
    session: Session, principal: Principal, body: AlertPreferencesUpdate
) -> AlertPreferences:
    channels = [channel.value for channel in body.enabled_channels]
    if AlertChannel.IN_APP.value not in channels:
        # The persistent inbox is the required fallback for every other channel.
        channels.insert(0, AlertChannel.IN_APP.value)
    row = session.get(AlertPreferenceRow, principal.user_id)
    if row is None:
        row = AlertPreferenceRow(user_id=principal.user_id, enabled_channels=channels)
        session.add(row)
    row.enabled_channels = channels
    row.quiet_hours_start_utc = body.quiet_hours_start_utc
    row.quiet_hours_end_utc = body.quiet_hours_end_utc
    session.commit()
    return get_preferences(session, principal)


# --- Devices ----------------------------------------------------------------------------------


def _device_view(row: RegisteredDeviceRow) -> Device:
    return Device(
        **_envelope(),
        device_id=row.device_id,
        platform=row.platform,
        status=row.status,
        last_seen_at_utc=row.last_seen_at_utc,
    )


def register_device(
    session: Session,
    principal: Principal,
    body: DeviceRegistrationRequest,
    cipher: TokenCipher | None,
) -> Device:
    """A token moves to the latest signed-in user, so a shared handset can't reach the last."""
    if cipher is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE, "Push notifications are not configured.")
    digest = token_digest(body.push_token)
    row = session.scalar(
        select(RegisteredDeviceRow).where(RegisteredDeviceRow.token_sha256 == digest)
    )
    now = utc_now()
    if row is None or row.user_id != principal.user_id or row.platform != body.platform.value:
        if row is not None:
            row.status = DeviceStatus.REVOKED.value
            row.token_sha256 = None
            row.push_token_encrypted = None
            session.flush()
        row = RegisteredDeviceRow(
            device_id=uuid4().hex,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            platform=body.platform.value,
            token_sha256=digest,
            push_token_encrypted=cipher.encrypt(body.push_token),
            status=DeviceStatus.ACTIVE.value,
        )
        session.add(row)
    row.last_seen_at_utc = now
    session.commit()
    return _device_view(row)


def revoke_device(session: Session, principal: Principal, device_id: str) -> None:
    """Idempotent. Pending pushes to this device fail with ``DEVICE_REVOKED`` when due."""
    row = session.get(RegisteredDeviceRow, device_id)
    if row is None or row.user_id != principal.user_id:
        raise ApiError(404, ErrorCode.NOT_FOUND, "The requested resource was not found.")
    row.status = DeviceStatus.REVOKED.value
    row.token_sha256 = None
    row.push_token_encrypted = None
    session.commit()


# --- Administration ---------------------------------------------------------------------------


def _rule_fields(row: AlertRuleRow) -> dict[str, Any]:
    return {
        "rule_id": row.rule_id,
        "version": row.version,
        "trigger_kind": row.trigger_kind,
        "severity": row.severity,
        "enabled": row.enabled,
        "evidence_requirement": row.evidence_requirement,
        "routing_roles": row.routing_roles,
        "dedupe_window_seconds": row.dedupe_window_seconds,
        "ack_timeout_seconds": row.ack_timeout_seconds,
        "escalation_policy": row.escalation_policy,
    }


def list_rules(
    session: Session, principal: Principal, limit: int, cursor: str | None
) -> AlertRuleList:
    rows = latest_rules(session, principal.tenant_id)
    after = _cursor_decode(cursor)
    if after is not None:
        rows = [row for row in rows if row.rule_id > after]
    kept = rows[:limit]
    return AlertRuleList(
        **_envelope(),
        items=[AlertRule(**_rule_fields(row)) for row in kept],
        limit=limit,
        next_cursor=_cursor_encode(kept[-1].rule_id) if len(rows) > limit else None,
        total_if_known=None,
    )


def save_rule(session: Session, principal: Principal, body: AlertRuleUpsert) -> AlertRuleSaved:
    """Always a new version, so past alerts still point at the rule that created them."""
    version = 1
    rule_id = body.rule_id or uuid4().hex
    if body.rule_id is not None:
        current = next(
            (r for r in latest_rules(session, principal.tenant_id) if r.rule_id == body.rule_id),
            None,
        )
        if current is None:
            raise ApiError(404, ErrorCode.NOT_FOUND, "The requested resource was not found.")
        version = current.version + 1
    row = AlertRuleRow(
        rule_id=rule_id,
        version=version,
        tenant_id=principal.tenant_id,
        trigger_kind=body.trigger_kind.value,
        severity=body.severity.value,
        enabled=body.enabled,
        evidence_requirement=body.evidence_requirement.value,
        routing_roles=[role.value for role in body.routing_roles],
        dedupe_window_seconds=body.dedupe_window_seconds,
        ack_timeout_seconds=body.ack_timeout_seconds,
        escalation_policy=body.escalation_policy,
        updated_by=principal.user_id,
        updated_at_utc=utc_now(),
    )
    session.add(row)
    session.commit()
    return AlertRuleSaved(**_envelope(), **_rule_fields(row))


# --- Realtime stream --------------------------------------------------------------------------


def _new_alerts(
    runtime: LibraryRuntime, principal: Principal, seen: set[str], since: Any
) -> list[AlertSummary]:
    with runtime.identities.session_factory() as session:
        rows = session.scalars(
            _inbox_query(runtime, principal)
            .where(AlertDeliveryRow.sent_at_utc >= since)
            .order_by(AlertDeliveryRow.sent_at_utc, AlertRow.alert_id)
            .limit(50)
        ).all()
        return [AlertSummary(**_summary_fields(row)) for row in rows if row.alert_id not in seen]


async def alert_stream(
    request: Request,
    runtime: LibraryRuntime,
    principal: Principal,
    *,
    poll_seconds: float,
    max_seconds: float,
) -> AsyncIterator[str]:
    """Server-Sent Events with safe summaries. History comes from ``GET /alerts`` on reconnect.

    Identity is re-checked while connected, so an expired or revoked session ends the stream.
    """
    authorization = request.headers.get("Authorization")
    security = request.app.state.security
    seen: set[str] = set()
    since = utc_now()
    started = time.monotonic()
    checked = started
    yield ": connected\n\n"
    while time.monotonic() - started < max_seconds:
        if await request.is_disconnected():
            return
        now = time.monotonic()
        if now - checked >= _STREAM_REAUTH_SECONDS:
            checked = now
            try:
                principal = await run_in_threadpool(
                    security.authenticate, authorization, uuid4().hex
                )
            except ApiError:
                yield "event: session-ended\ndata: {}\n\n"
                return
        for alert in await run_in_threadpool(_new_alerts, runtime, principal, seen, since):
            seen.add(alert.alert_id)
            yield f"event: alert\nid: {alert.alert_id}\ndata: {alert.model_dump_json()}\n\n"
        yield ": keep-alive\n\n"
        await asyncio.sleep(poll_seconds)
