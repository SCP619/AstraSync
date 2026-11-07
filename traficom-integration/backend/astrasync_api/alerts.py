"""Alert engine: durable events to safe, deduplicated alerts and audited deliveries.

Runs in its own process (``python -m astrasync_api.alerts``), so a long ingest or RF backlog cannot
hold up alert creation. Alert text comes only from fixed templates here, so a rule or a source
record can never put restricted content on a lock screen. Severity is an operational priority,
never a legal status.
"""

import argparse
import hashlib
import logging
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from .alert_tables import (
    AlertDeliveryRow,
    AlertPreferenceRow,
    AlertRow,
    AlertRuleRow,
    RegisteredDeviceRow,
)
from .authz import ObjectAccessPolicy, ObjectRef
from .case_tables import CaseRow, ReviewEventRow
from .config import Settings, SettingsError, load_named
from .contract.enums import (
    AlertChannel,
    AlertDeliveryState,
    AlertEvidenceRequirement,
    AlertSeverity,
    AlertStatus,
    AlertTriggerKind,
    CriterionApplicability,
    DeviceStatus,
    DomainEventKind,
    FindingStatus,
    PushCategory,
    ReviewAction,
    UsageClassification,
)
from .contract.models import PushPayload
from .contract.permissions import Role, capabilities_for
from .db import AuditEvent, RoleRow, User, UserRoleGrant, build_engine, build_session_factory
from .identity import Principal
from .jobs import utc_now
from .library_tables import OutboxEventRow

logger = logging.getLogger("astrasync.alerts")

SYSTEM_ACTOR = "system:alerts"
_MAX_PUSH_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 30
PUSH_QUOTA_PER_USER_PER_HOUR = 60
_BATCH = 100
# These reach people regardless of their channel choices and quiet hours.
_ALWAYS_DELIVER = frozenset({AlertSeverity.CRITICAL.value, AlertSeverity.SECURITY.value})

_TRIGGER_BY_EVENT = {
    DomainEventKind.CANDIDATE_SCREENED.value: AlertTriggerKind.RELEVANT_CANDIDATE,
    DomainEventKind.CRITERION_CHECKED.value: AlertTriggerKind.POTENTIAL_EXCEEDANCE,
    DomainEventKind.CASE_ESCALATED.value: AlertTriggerKind.REVIEWER_ESCALATION,
    DomainEventKind.SOURCE_PUBLISHED.value: AlertTriggerKind.SOURCE_NEW_RELEASE,
    DomainEventKind.SOURCE_REVISED.value: AlertTriggerKind.SOURCE_REVISED,
    DomainEventKind.SOURCE_FAILED.value: AlertTriggerKind.OPERATIONS_FAILURE,
    DomainEventKind.SOURCE_STALE.value: AlertTriggerKind.SOURCE_STALE,
    DomainEventKind.ARTIFACT_QUARANTINED.value: AlertTriggerKind.ARTIFACT_INTEGRITY_FAILURE,
    DomainEventKind.SECURITY_EVENT.value: AlertTriggerKind.SECURITY_EVENT,
}


@dataclass(frozen=True)
class _Template:
    title: str
    preview: str
    category: PushCategory


_OPEN_APP = "Open AstraSync to view details."
_TEMPLATES = {
    AlertTriggerKind.RELEVANT_CANDIDATE: _Template(
        "New candidate to screen", _OPEN_APP, PushCategory.CASE_UPDATE
    ),
    AlertTriggerKind.POTENTIAL_EXCEEDANCE: _Template(
        "Potential exceedance: expert review required", _OPEN_APP, PushCategory.CASE_UPDATE
    ),
    AlertTriggerKind.REVIEWER_ESCALATION: _Template(
        "Case escalated by a reviewer", _OPEN_APP, PushCategory.CASE_UPDATE
    ),
    AlertTriggerKind.UNCERTAINTY_REVIEW: _Template(
        "Case needs review", _OPEN_APP, PushCategory.CASE_UPDATE
    ),
    AlertTriggerKind.OPERATIONS_FAILURE: _Template(
        "A source or job needs attention", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.SECURITY_EVENT: _Template(
        "Account security change", _OPEN_APP, PushCategory.SECURITY
    ),
    AlertTriggerKind.SOURCE_NEW_RELEASE: _Template(
        "New source release found", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.SOURCE_REVISED: _Template(
        "A source was revised", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.SOURCE_STALE: _Template(
        "A source is stale", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.ARTIFACT_INTEGRITY_FAILURE: _Template(
        "A file failed verification", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.SCHEMA_DRIFT: _Template(
        "A source format changed", _OPEN_APP, PushCategory.OPERATIONS
    ),
    AlertTriggerKind.INDEX_BACKLOG: _Template(
        "Indexing is behind", _OPEN_APP, PushCategory.OPERATIONS
    ),
}


@dataclass(frozen=True)
class _DefaultRule:
    trigger: AlertTriggerKind
    severity: AlertSeverity
    evidence: AlertEvidenceRequirement
    roles: tuple[Role, ...]
    dedupe_seconds: int = 3600
    ack_timeout_seconds: int | None = None


_PROVENANCE = AlertEvidenceRequirement.SOURCE_PROVENANCE
_DIAGNOSTIC = AlertEvidenceRequirement.OPERATIONAL_DIAGNOSTIC
DEFAULT_RULES = (
    _DefaultRule(
        AlertTriggerKind.RELEVANT_CANDIDATE, AlertSeverity.REVIEW, _PROVENANCE, (Role.ANALYST,)
    ),
    _DefaultRule(
        AlertTriggerKind.POTENTIAL_EXCEEDANCE,
        AlertSeverity.HIGH,
        AlertEvidenceRequirement.VERIFIED_CRITERION_AND_METHOD_RUN,
        (Role.ANALYST, Role.REVIEWER),
    ),
    _DefaultRule(
        AlertTriggerKind.REVIEWER_ESCALATION,
        AlertSeverity.CRITICAL,
        AlertEvidenceRequirement.REVIEWER_DECISION,
        (Role.REVIEWER,),
        dedupe_seconds=0,
    ),
    _DefaultRule(
        AlertTriggerKind.OPERATIONS_FAILURE,
        AlertSeverity.OPERATIONS,
        _DIAGNOSTIC,
        (Role.ADMINISTRATOR,),
    ),
    _DefaultRule(
        AlertTriggerKind.SECURITY_EVENT,
        AlertSeverity.SECURITY,
        _DIAGNOSTIC,
        (Role.ADMINISTRATOR,),
        dedupe_seconds=0,
    ),
    _DefaultRule(
        AlertTriggerKind.SOURCE_NEW_RELEASE, AlertSeverity.INFO, _PROVENANCE, (Role.ANALYST,)
    ),
    _DefaultRule(
        AlertTriggerKind.SOURCE_REVISED,
        AlertSeverity.REVIEW,
        _PROVENANCE,
        (Role.ANALYST, Role.REVIEWER),
    ),
    _DefaultRule(
        AlertTriggerKind.SOURCE_STALE, AlertSeverity.OPERATIONS, _DIAGNOSTIC, (Role.ADMINISTRATOR,)
    ),
    _DefaultRule(
        AlertTriggerKind.ARTIFACT_INTEGRITY_FAILURE,
        AlertSeverity.OPERATIONS,
        _DIAGNOSTIC,
        (Role.ADMINISTRATOR, Role.ANALYST),
    ),
)


class PushTokenInvalid(Exception):
    """The provider says this token is dead, so the device is revoked."""


class PushUnavailable(Exception):
    """A temporary provider failure, so the delivery is retried."""


class PushGateway(Protocol):
    def send(self, push_token: str, payload: PushPayload) -> str:
        """Hand the payload to the provider and return its message ID."""
        ...


class TokenCipher:
    """Encrypts push tokens at rest with a server-held key."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode())

    def encrypt(self, token: str) -> bytes:
        return self._fernet.encrypt(token.encode())

    def decrypt(self, value: bytes) -> str:
        return self._fernet.decrypt(value).decode()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def seed_default_rules(session: Session, tenant_id: str) -> None:
    now = utc_now()
    for rule in DEFAULT_RULES:
        session.add(
            AlertRuleRow(
                rule_id=f"{tenant_id}-{rule.trigger.value}",
                version=1,
                tenant_id=tenant_id,
                trigger_kind=rule.trigger.value,
                severity=rule.severity.value,
                enabled=True,
                evidence_requirement=rule.evidence.value,
                routing_roles=[role.value for role in rule.roles],
                dedupe_window_seconds=rule.dedupe_seconds,
                ack_timeout_seconds=rule.ack_timeout_seconds,
                escalation_policy={},
                updated_by=SYSTEM_ACTOR,
                updated_at_utc=now,
            )
        )


def latest_rules(session: Session, tenant_id: str) -> list[AlertRuleRow]:
    versions = (
        select(AlertRuleRow.rule_id, func.max(AlertRuleRow.version).label("version"))
        .where(AlertRuleRow.tenant_id == tenant_id)
        .group_by(AlertRuleRow.rule_id)
        .subquery()
    )
    return list(
        session.scalars(
            select(AlertRuleRow)
            .join(
                versions,
                (AlertRuleRow.rule_id == versions.c.rule_id)
                & (AlertRuleRow.version == versions.c.version),
            )
            .order_by(AlertRuleRow.rule_id)
        )
    )


@dataclass(frozen=True)
class _EventContext:
    case: CaseRow | None
    evidence_refs: list[str]


def _evidence_context(
    session: Session, event: OutboxEventRow, rule: AlertRuleRow
) -> _EventContext | None:
    """Re-checks stored state. An event is not trusted to say that its evidence exists."""
    case = None
    if event.resource_type == "case":
        case = session.get(CaseRow, event.resource_id)
        if case is None or case.tenant_id != event.tenant_id:
            return None
    requirement = AlertEvidenceRequirement(rule.evidence_requirement)
    if requirement is AlertEvidenceRequirement.VERIFIED_CRITERION_AND_METHOD_RUN:
        if (
            case is None
            or case.criterion_status != CriterionApplicability.VERIFIED.value
            or case.margin_db is None
            or case.finding_status != FindingStatus.POTENTIAL_LIMIT_EXCEEDANCE.value
            or case.latest_analysis_run_id is None
        ):
            return None
        return _EventContext(case, [case.latest_analysis_run_id])
    if requirement is AlertEvidenceRequirement.REVIEWER_DECISION:
        review = session.get(ReviewEventRow, str(event.payload.get("review_event_id")))
        if (
            case is None
            or review is None
            or review.case_id != case.case_id
            or review.action != ReviewAction.ESCALATE.value
        ):
            return None
        return _EventContext(case, [review.review_event_id])
    return _EventContext(case, [event.resource_id])


def _recipients(
    session: Session,
    policy: ObjectAccessPolicy,
    tenant_id: str,
    roles: Sequence[str],
    case: CaseRow | None,
    now: datetime,
) -> list[str]:
    """Active users holding a routed role who can open what the alert refers to."""
    rows = session.execute(
        select(User.user_id, RoleRow.name)
        .join(UserRoleGrant, UserRoleGrant.user_id == User.user_id)
        .join(RoleRow, RoleRow.role_id == UserRoleGrant.role_id)
        .where(
            User.tenant_id == tenant_id,
            User.active.is_(True),
            UserRoleGrant.tenant_id == tenant_id,
            or_(UserRoleGrant.expires_at_utc.is_(None), UserRoleGrant.expires_at_utc > now),
        )
    ).all()
    roles_by_user: dict[str, set[Role]] = {}
    for user_id, name in rows:
        roles_by_user.setdefault(user_id, set()).add(Role(name))
    recipients = []
    for user_id, held in sorted(roles_by_user.items()):
        if not {role.value for role in held} & set(roles):
            continue
        if case is not None:
            principal = Principal(user_id, tenant_id, frozenset(held), capabilities_for(held))
            target = ObjectRef(
                object_type="source",
                object_id=case.source_id,
                tenant_id=tenant_id,
                classification=UsageClassification(case.usage_classification),
                is_synthetic=case.is_synthetic,
            )
            if not policy.can_access(principal, target, "READ"):
                continue
        recipients.append(user_id)
    return recipients


def _quiet_until(preference: AlertPreferenceRow | None, now: datetime) -> datetime | None:
    if preference is None or not preference.quiet_hours_start_utc:
        return None
    if not preference.quiet_hours_end_utc:
        return None
    start = _at(now, preference.quiet_hours_start_utc)
    end = _at(now, preference.quiet_hours_end_utc)
    if start <= end:
        return end if start <= now < end else None
    if now >= start:
        return end + timedelta(days=1)
    return end if now < end else None


def _at(now: datetime, clock: str) -> datetime:
    hours, minutes = clock.split(":")
    return now.replace(hour=int(hours), minute=int(minutes), second=0, microsecond=0)


def _add_deliveries(session: Session, alert: AlertRow, recipient: str, now: datetime) -> None:
    session.add(
        AlertDeliveryRow(
            delivery_id=uuid4().hex,
            alert_id=alert.alert_id,
            recipient_user_id=recipient,
            channel=AlertChannel.IN_APP.value,
            device_key="",
            attempt=1,
            state=AlertDeliveryState.SENT.value,
            sent_at_utc=now,
            last_attempt_at_utc=now,
        )
    )
    preference = session.get(AlertPreferenceRow, recipient)
    always = alert.severity in _ALWAYS_DELIVER
    if preference and not always and AlertChannel.ANDROID.value not in preference.enabled_channels:
        return
    devices = session.scalars(
        select(RegisteredDeviceRow).where(
            RegisteredDeviceRow.user_id == recipient,
            RegisteredDeviceRow.platform == AlertChannel.ANDROID.value,
            RegisteredDeviceRow.status == DeviceStatus.ACTIVE.value,
        )
    ).all()
    start_at = (None if always else _quiet_until(preference, now)) or now
    for device in devices:
        session.add(
            AlertDeliveryRow(
                delivery_id=uuid4().hex,
                alert_id=alert.alert_id,
                recipient_user_id=recipient,
                channel=AlertChannel.ANDROID.value,
                device_key=device.device_id,
                attempt=0,
                state=AlertDeliveryState.PENDING.value,
                next_attempt_at_utc=start_at,
            )
        )


def _record_decision(session: Session, event: OutboxEventRow, rule_id: str, outcome: str) -> None:
    """In the same transaction as the alert, so a decision and its result cannot disagree."""
    session.add(
        AuditEvent(
            event_id=uuid4().hex,
            actor=SYSTEM_ACTOR,
            tenant_id=event.tenant_id,
            action="alert_rule_decision",
            object_type="alert_rules",
            object_id=rule_id,
            outcome=outcome,
            correlation_id=event.event_id,
            occurred_at_utc=utc_now(),
        )
    )


def _evaluate(
    session: Session,
    policy: ObjectAccessPolicy,
    event: OutboxEventRow,
    now: datetime,
) -> None:
    trigger = _TRIGGER_BY_EVENT.get(event.event_kind)
    if trigger is None:
        return
    for rule in latest_rules(session, event.tenant_id):
        if not rule.enabled or rule.trigger_kind != trigger.value:
            continue
        existing = session.scalar(
            select(AlertRow.alert_id).where(
                AlertRow.rule_id == rule.rule_id, AlertRow.event_id == event.event_id
            )
        )
        if existing is not None:
            continue
        context = _evidence_context(session, event, rule)
        if context is None:
            _record_decision(session, event, rule.rule_id, "SUPPRESSED_NO_EVIDENCE")
            continue

        dedupe_key = f"{rule.rule_id}:{event.resource_type}:{event.resource_id}"
        if rule.dedupe_window_seconds > 0:
            earlier = session.scalars(
                select(AlertRow)
                .where(AlertRow.tenant_id == event.tenant_id, AlertRow.dedupe_key == dedupe_key)
                .order_by(AlertRow.created_at_utc.desc())
                .limit(1)
            ).first()
            window = timedelta(seconds=rule.dedupe_window_seconds)
            if earlier is not None and (
                earlier.status == AlertStatus.OPEN.value or now - earlier.created_at_utc < window
            ):
                _record_decision(session, event, rule.rule_id, "SUPPRESSED_DUPLICATE")
                continue

        template = _TEMPLATES[trigger]
        case = context.case
        alert = AlertRow(
            alert_id=uuid4().hex,
            tenant_id=event.tenant_id,
            event_id=event.event_id,
            case_id=case.case_id if case else None,
            source_id=case.source_id if case else None,
            usage_classification=case.usage_classification if case else None,
            rule_id=rule.rule_id,
            rule_version=rule.version,
            severity=rule.severity,
            safe_title=template.title,
            safe_preview=template.preview,
            push_category=template.category.value,
            evidence_refs=context.evidence_refs,
            dedupe_key=dedupe_key,
            status=AlertStatus.OPEN.value,
            is_synthetic=case.is_synthetic if case else False,
            ack_timeout_seconds=rule.ack_timeout_seconds,
            escalation_policy=rule.escalation_policy,
            created_at_utc=now,
        )
        session.add(alert)
        session.flush()
        for recipient in _recipients(
            session, policy, event.tenant_id, rule.routing_roles, case, now
        ):
            _add_deliveries(session, alert, recipient, now)
        _record_decision(session, event, rule.rule_id, "ALERT_CREATED")


def process_outbox(
    sessions: sessionmaker[Session], *, limit: int = _BATCH, now: datetime | None = None
) -> int:
    """Consumes events oldest first, each in one transaction with the alerts it creates."""
    now = now or utc_now()
    policy = ObjectAccessPolicy(sessions)
    done = 0
    while done < limit:
        with sessions() as session:
            event = session.scalars(
                select(OutboxEventRow)
                .where(OutboxEventRow.consumed_at_utc.is_(None))
                .order_by(OutboxEventRow.occurred_at_utc, OutboxEventRow.event_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if event is None:
                return done
            _evaluate(session, policy, event, now)
            event.consumed_at_utc = now
            session.commit()
        done += 1
    return done


def process_push(
    sessions: sessionmaker[Session],
    gateway: PushGateway | None,
    cipher: TokenCipher | None,
    *,
    limit: int = _BATCH,
    now: datetime | None = None,
) -> int:
    """Sends due pushes. The payload is only ever the opaque ``PushPayload``."""
    now = now or utc_now()
    sent = 0
    while sent < limit:
        # One per transaction: the lock is held through the send, so no two workers repeat it.
        with sessions() as session:
            delivery = session.scalars(
                select(AlertDeliveryRow)
                .where(
                    AlertDeliveryRow.state == AlertDeliveryState.PENDING.value,
                    AlertDeliveryRow.next_attempt_at_utc <= now,
                )
                .order_by(AlertDeliveryRow.next_attempt_at_utc)
                .limit(1)
                .with_for_update(skip_locked=True)
            ).first()
            if delivery is None:
                return sent
            _send_one(session, delivery, gateway, cipher, now)
            session.commit()
        sent += 1
    return sent


def _fail(delivery: AlertDeliveryRow, code: str, now: datetime) -> None:
    delivery.state = AlertDeliveryState.FAILED.value
    delivery.failure_code = code
    delivery.last_attempt_at_utc = now
    delivery.next_attempt_at_utc = None


def _send_one(
    session: Session,
    delivery: AlertDeliveryRow,
    gateway: PushGateway | None,
    cipher: TokenCipher | None,
    now: datetime,
) -> None:
    device = session.get(RegisteredDeviceRow, delivery.device_key)
    user = session.get(User, delivery.recipient_user_id)
    if device is None or device.status != DeviceStatus.ACTIVE.value:
        _fail(delivery, "DEVICE_REVOKED", now)
        return
    if user is None or not user.active:
        _fail(delivery, "USER_INACTIVE", now)
        return
    if gateway is None or cipher is None or device.push_token_encrypted is None:
        # Visible, not silent: the in-app alert exists and this channel plainly did not send.
        _fail(delivery, "PUSH_NOT_CONFIGURED", now)
        return
    sent_recently = session.scalar(
        select(func.count())
        .select_from(AlertDeliveryRow)
        .where(
            AlertDeliveryRow.recipient_user_id == delivery.recipient_user_id,
            AlertDeliveryRow.channel == AlertChannel.ANDROID.value,
            AlertDeliveryRow.sent_at_utc > now - timedelta(hours=1),
        )
    )
    if (sent_recently or 0) >= PUSH_QUOTA_PER_USER_PER_HOUR:
        _fail(delivery, "QUOTA_EXCEEDED", now)
        return

    alert = session.get_one(AlertRow, delivery.alert_id)
    payload = PushPayload(
        alert_id=alert.alert_id,
        category=PushCategory(alert.push_category),
        created_at_utc=alert.created_at_utc,
    )
    delivery.attempt += 1
    delivery.last_attempt_at_utc = now
    try:
        delivery.provider_message_id = gateway.send(
            cipher.decrypt(device.push_token_encrypted), payload
        )
    except InvalidToken:
        _fail(delivery, "TOKEN_UNREADABLE", now)
    except PushTokenInvalid:
        device.status = DeviceStatus.REVOKED.value
        device.push_token_encrypted = None
        device.token_sha256 = None
        _fail(delivery, "TOKEN_INVALID", now)
    except PushUnavailable:
        if delivery.attempt >= _MAX_PUSH_ATTEMPTS:
            _fail(delivery, "PROVIDER_UNAVAILABLE", now)
        else:
            delay = _BASE_BACKOFF_SECONDS * 2 ** (delivery.attempt - 1)
            delivery.next_attempt_at_utc = now + timedelta(seconds=delay)
    else:
        # Handed to the provider. Whether it reached the device is a separate, unknown fact.
        delivery.state = AlertDeliveryState.SENT.value
        delivery.sent_at_utc = now
        delivery.next_attempt_at_utc = None


def process_escalations(
    sessions: sessionmaker[Session], *, limit: int = _BATCH, now: datetime | None = None
) -> int:
    """Once a configured timeout passes with no acknowledgment, routes the alert further, once."""
    now = now or utc_now()
    policy = ObjectAccessPolicy(sessions)
    with sessions() as session:
        due = session.scalars(
            select(AlertRow)
            .where(
                AlertRow.status == AlertStatus.OPEN.value,
                AlertRow.ack_timeout_seconds.is_not(None),
                AlertRow.escalated_at_utc.is_(None),
            )
            .limit(limit)
        ).all()
        count = 0
        for alert in due:
            deadline = alert.created_at_utc + timedelta(seconds=alert.ack_timeout_seconds or 0)
            roles = alert.escalation_policy.get("escalate_to_roles") or []
            if now < deadline or not roles:
                continue
            case = session.get(CaseRow, alert.case_id) if alert.case_id else None
            already = set(
                session.scalars(
                    select(AlertDeliveryRow.recipient_user_id).where(
                        AlertDeliveryRow.alert_id == alert.alert_id,
                        AlertDeliveryRow.channel == AlertChannel.IN_APP.value,
                    )
                )
            )
            for recipient in _recipients(session, policy, alert.tenant_id, roles, case, now):
                if recipient not in already:
                    _add_deliveries(session, alert, recipient, now)
            alert.escalated_at_utc = now
            session.add(
                AuditEvent(
                    event_id=uuid4().hex,
                    actor=SYSTEM_ACTOR,
                    tenant_id=alert.tenant_id,
                    action="alert_escalated",
                    object_type="alerts",
                    object_id=alert.alert_id,
                    outcome="ALLOWED",
                    correlation_id=alert.event_id,
                    occurred_at_utc=now,
                )
            )
            count += 1
        session.commit()
        return count


def run_once(
    sessions: sessionmaker[Session], gateway: PushGateway | None, cipher: TokenCipher | None
) -> int:
    return (
        process_outbox(sessions)
        + process_push(sessions, gateway, cipher)
        + process_escalations(sessions)
    )


def build_cipher(settings: Settings) -> TokenCipher | None:
    return TokenCipher(settings.push_token_key) if settings.push_token_key else None


def build_gateway(settings: Settings) -> Any:
    if not settings.push_gateway:
        return None
    gateway = load_named(settings.push_gateway)()
    if not callable(getattr(gateway, "send", None)):
        raise SettingsError("The push gateway does not implement PushGateway")
    return gateway


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="process what is due, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    settings = Settings.from_env(os.environ)
    if not settings.database_url:
        raise SettingsError("The alert worker needs a database")
    sessions = build_session_factory(build_engine(settings.database_url))
    gateway, cipher = build_gateway(settings), build_cipher(settings)
    if args.once:
        run_once(sessions, gateway, cipher)
        return 0
    while True:
        if run_once(sessions, gateway, cipher) == 0:
            time.sleep(1.0)


if __name__ == "__main__":
    sys.exit(main())
