"""IPD stage 7: alert truthfulness, deduplication, safe delivery and acknowledgment."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from conftest import TENANT_A, TENANT_B, Users
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from support.demo_plugins import DEMO_UNIT, DemoEchoMethod, DemoEchoResolver

from astrasync_api import admin, alert_api, alerts, cases, jobs
from astrasync_api.alert_tables import AlertDeliveryRow, AlertRow, RegisteredDeviceRow
from astrasync_api.analysis import AnalysisPlugins
from astrasync_api.contract.enums import IssueDomain, JobType, SourceType, UsageClassification
from astrasync_api.contract.models import (
    AlertDetail,
    AlertList,
    CaseCandidate,
    PushPayload,
)
from astrasync_api.db import AuditEvent, ResourceEntitlement
from astrasync_api.ingest import PipelineContext
from astrasync_api.library_tables import OutboxEventRow
from astrasync_api.worker import WorkerRuntime, run_until_idle

Bearer = Callable[..., dict[str, str]]
SOURCE = "SRC-ALERTS"
RESTRICTED = "SRC-ALERTS-RESTRICTED"
SECRET_NOTICE = "SECRET-NOTICE-60.1N"
PUSH_TOKEN = "fcm-token-do-not-leak"


@pytest.fixture(autouse=True)
def registered(request: pytest.FixtureRequest) -> None:
    if "users" not in request.fixturenames:
        return
    request.getfixturevalue("users")
    sessions = request.getfixturevalue("sessions")
    common: dict[str, Any] = {
        "tenant_id": TENANT_A,
        "publisher": "Demo publisher",
        "domain": IssueDomain.SPACE,
        "source_type": SourceType.SPACE_IFIC,
        "rights_basis": "Synthetic test data",
        "is_synthetic": True,
    }
    admin.register_source(
        sessions, source_id=SOURCE, classification=UsageClassification.INTERNAL, **common
    )
    admin.register_source(
        sessions, source_id=RESTRICTED, classification=UsageClassification.RESTRICTED, **common
    )


def candidate(sessions: sessionmaker[Session], **overrides: Any) -> str:
    values: dict[str, Any] = {
        "notice_uid": uuid4().hex,
        "notice_id": SECRET_NOTICE,
        "source_id": SOURCE,
        "source_issue_id": "DEMO-IFIC-001",
        "administration": "DEMO",
        "domain": "SPACE",
        "change_type": "NEW",
        "frequency_start_mhz": 10700.0,
        "frequency_end_mhz": 10720.0,
        "relevance": {
            "label": "FREQUENCY_MATCH",
            "reason_codes": [],
            "rule_version": None,
            "overlap_start_mhz": None,
            "overlap_end_mhz": None,
            "frequency_match": True,
            "service_match": None,
            "geometry_match": None,
            "technical_data_ready": None,
            "criterion_available": None,
        },
        "scenario_id": "S",
        "scenario": {},
        **overrides,
    }
    return cases.upsert_candidate(sessions, TENANT_A, CaseCandidate(**values))


VERIFIED = {
    "criterion_ref_id": "DEMO-CRITERION-NOT-REAL",
    "regulatory_scope": "DEMO",
    "applicable": "VERIFIED",
    "matching_conditions": {},
    "limit_value": -100.0,
    "limit_unit": DEMO_UNIT,
    "limit_reference_bandwidth_hz": None,
    "comparison_operator": "UPPER_BOUND",
    "review_note": None,
    "citation": {"reference_id": "R", "section_id": "S", "source_url": "https://example.invalid/"},
}


@pytest.fixture
def runtime(sessions: sessionmaker[Session], secure_app: FastAPI) -> WorkerRuntime:
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test",
        analysis=AnalysisPlugins(
            methods={DemoEchoMethod.method_id: DemoEchoMethod()},
            criterion_resolver=DemoEchoResolver(),
        ),
    )


def exceedance_case(
    client: TestClient,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    headers: dict[str, str],
    **overrides: Any,
) -> str:
    case_id = candidate(
        sessions, scenario={"demo_value": -50.0, "demo_criteria": [VERIFIED]}, **overrides
    )
    response = client.post(
        f"/api/v1/cases/{case_id}/analyse",
        json={},
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 202, response.text
    run_until_idle(runtime)
    return case_id


def inbox(client: TestClient, headers: dict[str, str], **params: Any) -> AlertList:
    response = client.get("/api/v1/alerts", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return AlertList.model_validate(response.json())


def titled(client: TestClient, headers: dict[str, str], fragment: str) -> list[Any]:
    return [item for item in inbox(client, headers).items if fragment in item.safe_title]


def clear_outbox(sessions: sessionmaker[Session]) -> None:
    alerts.process_outbox(sessions, limit=1000)


def forged_event(
    sessions: sessionmaker[Session], kind: str, resource_id: str, **extra: Any
) -> None:
    with sessions() as session:
        jobs.emit_event(
            session,
            tenant_id=TENANT_A,
            event_kind=kind,
            resource_type=extra.pop("resource_type", "case"),
            resource_id=resource_id,
            dedupe_key=uuid4().hex,
            correlation_id="test",
            payload=extra,
        )
        session.commit()


def decisions(sessions: sessionmaker[Session]) -> list[str]:
    with sessions() as session:
        return list(
            session.scalars(
                select(AuditEvent.outcome).where(AuditEvent.action == "alert_rule_decision")
            )
        )


@dataclass
class FakeGateway:
    sent: list[tuple[str, PushPayload]] = field(default_factory=list)
    error: Exception | None = None

    def send(self, push_token: str, payload: PushPayload) -> str:
        if self.error:
            raise self.error
        self.sent.append((push_token, payload))
        return f"message-{len(self.sent)}"


@pytest.fixture
def cipher(secure_app: FastAPI) -> alerts.TokenCipher:
    secure_app.state.push_cipher = alerts.TokenCipher(Fernet.generate_key().decode())
    return secure_app.state.push_cipher


def register(client: TestClient, headers: dict[str, str], token: str = PUSH_TOKEN) -> Any:
    response = client.post(
        "/api/v1/devices", json={"platform": "ANDROID", "push_token": token}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Truthful triggers ------------------------------------------------------------------------


def test_verified_exceedance_alerts_analysts_and_reviewers_only(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = exceedance_case(secure_client, runtime, sessions, bearer())
    clear_outbox(sessions)
    for subject in ("analyst-a", "reviewer-a"):
        found = titled(secure_client, bearer(subject), "Potential exceedance")
        assert len(found) == 1
        assert found[0].severity == "HIGH"
        assert found[0].case_id == case_id
        assert found[0].rule_version == 1
    assert inbox(secure_client, bearer("admin-a")).items == []
    assert inbox(secure_client, bearer("analyst-b")).items == []


def test_frequency_match_alone_is_never_called_an_exceedance(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    candidate(sessions)
    clear_outbox(sessions)
    items = inbox(secure_client, bearer("analyst-a")).items
    assert [item.safe_title for item in items] == ["New candidate to screen"]
    assert items[0].severity == "REVIEW"


def test_event_without_stored_verified_evidence_makes_no_alert(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    clear_outbox(sessions)
    forged_event(sessions, "CRITERION_CHECKED", case_id)
    clear_outbox(sessions)
    assert titled(secure_client, bearer("reviewer-a"), "exceedance") == []
    assert "SUPPRESSED_NO_EVIDENCE" in decisions(sessions)


def test_no_alert_text_contains_case_content_or_a_legal_claim(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = exceedance_case(secure_client, runtime, sessions, bearer())
    clear_outbox(sessions)
    listing = secure_client.get("/api/v1/alerts", headers=bearer()).text
    assert SECRET_NOTICE not in listing
    assert "10700" not in listing
    for word in ("violation", "breach", "harmful", "illegal"):
        assert word not in listing.lower()
    # An ID is enough to fetch the rest, after authorization.
    assert case_id in listing
    for template in alerts._TEMPLATES.values():
        assert "violation" not in template.title.lower()


def test_templates_cover_every_trigger() -> None:
    assert set(alerts._TEMPLATES) == set(alerts.AlertTriggerKind)


def test_reviewer_escalation_is_critical_and_needs_a_reviewer(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    clear_outbox(sessions)
    body = {"action": "ESCALATE", "decision_reason": "Due date is close."}
    denied = secure_client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json=body,
        headers={**bearer("analyst-a"), "Idempotency-Key": uuid4().hex},
    )
    assert denied.status_code == 403
    accepted = secure_client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json=body,
        headers={**bearer("reviewer-a"), "Idempotency-Key": uuid4().hex},
    )
    assert accepted.status_code == 201
    clear_outbox(sessions)
    found = titled(secure_client, bearer("reviewer-a"), "escalated")
    assert [item.severity for item in found] == ["CRITICAL"]
    detail = secure_client.get(f"/api/v1/alerts/{found[0].alert_id}", headers=bearer("reviewer-a"))
    assert detail.json()["evidence_refs"] == [accepted.json()["review_event_id"]]


def test_forged_escalation_event_without_a_decision_makes_no_alert(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    clear_outbox(sessions)
    forged_event(sessions, "CASE_ESCALATED", case_id, review_event_id="invented")
    clear_outbox(sessions)
    assert titled(secure_client, bearer("reviewer-a"), "escalated") == []


def test_quarantine_and_security_events_go_to_operations_roles(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    forged_event(sessions, "ARTIFACT_QUARANTINED", "artifact-1", resource_type="source_artifact")
    admin.revoke_sessions(sessions, users.ids["no-roles-a"])
    clear_outbox(sessions)
    severities = {item.severity for item in inbox(secure_client, bearer("admin-a")).items}
    assert severities == {"OPERATIONS", "SECURITY"}
    assert {item.severity for item in inbox(secure_client, bearer("reviewer-a")).items} == set()


# --- Deduplication and independence -----------------------------------------------------------


def test_repeated_events_produce_one_alert_and_an_audited_decision(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    for _ in range(3):
        forged_event(sessions, "SOURCE_PUBLISHED", "pub-1", resource_type="source_publication")
    clear_outbox(sessions)
    assert len(inbox(secure_client, bearer("analyst-a")).items) == 1
    outcomes = decisions(sessions)
    assert outcomes.count("ALERT_CREATED") == 1
    assert outcomes.count("SUPPRESSED_DUPLICATE") == 2


def test_reprocessing_the_same_event_creates_nothing_new(
    sessions: sessionmaker[Session], users: Users
) -> None:
    forged_event(sessions, "SOURCE_PUBLISHED", "pub-1", resource_type="source_publication")
    clear_outbox(sessions)
    with sessions() as session:
        for event in session.scalars(select(OutboxEventRow)):
            event.consumed_at_utc = None
        session.commit()
    clear_outbox(sessions)
    with sessions() as session:
        assert len(session.scalars(select(AlertRow)).all()) == 1


def test_alerts_are_created_during_a_heavy_job_backlog(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    for index in range(50):
        jobs.enqueue(
            sessions,
            tenant_id=TENANT_A,
            job_type=JobType.RF,
            lane=jobs.LANE_ANALYSIS,
            idempotency_key=f"backlog-{index}",
            requested_by="x",
            payload={},
        )
    candidate(sessions)
    clear_outbox(sessions)
    assert len(inbox(secure_client, bearer("analyst-a")).items) == 1


def test_alert_exists_with_no_connected_device_and_is_recovered_later(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    candidate(sessions)
    candidate(sessions)
    clear_outbox(sessions)
    first = inbox(secure_client, bearer("analyst-a"), limit=1)
    assert len(first.items) == 1
    assert first.next_cursor is not None
    rest = inbox(secure_client, bearer("analyst-a"), limit=1, cursor=first.next_cursor)
    assert len(rest.items) == 1
    assert rest.items[0].alert_id != first.items[0].alert_id


# --- Access -----------------------------------------------------------------------------------


def _entitle(
    sessions: sessionmaker[Session], users: Users, subject: str, grant_id: str = "g"
) -> None:
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id=grant_id,
                subject=users.ids[subject],
                tenant_id=TENANT_A,
                object_type="source",
                object_id=RESTRICTED,
                classification="RESTRICTED",
                rights=["READ"],
            )
        )
        session.commit()


def test_restricted_case_alert_reaches_only_entitled_recipients(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    _entitle(sessions, users, "analyst-a")
    candidate(sessions, source_id=RESTRICTED)
    clear_outbox(sessions)
    assert len(inbox(secure_client, bearer("analyst-a")).items) == 1
    with sessions() as session:
        recipients = set(session.scalars(select(AlertDeliveryRow.recipient_user_id)))
    assert recipients == {users.ids["analyst-a"]}


def test_losing_access_hides_an_existing_alert_and_its_deep_link(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    _entitle(sessions, users, "analyst-a")
    candidate(sessions, source_id=RESTRICTED)
    clear_outbox(sessions)
    alert_id = inbox(secure_client, bearer("analyst-a")).items[0].alert_id
    assert secure_client.get(f"/api/v1/alerts/{alert_id}", headers=bearer()).status_code == 200
    with sessions() as session:
        session.delete(session.get_one(ResourceEntitlement, "g"))
        session.commit()
    assert inbox(secure_client, bearer("analyst-a")).items == []
    denied = secure_client.get(f"/api/v1/alerts/{alert_id}", headers=bearer())
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "ALERT_NOT_FOUND"


@pytest.mark.parametrize("subject", ["analyst-b", "reviewer-a", "admin-a"])
def test_non_recipient_gets_the_same_answer_as_for_a_missing_alert(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session], subject: str
) -> None:
    candidate(sessions)
    clear_outbox(sessions)
    alert_id = inbox(secure_client, bearer("analyst-a")).items[0].alert_id
    headers = {**bearer(subject), "Idempotency-Key": uuid4().hex}
    denied = secure_client.get(f"/api/v1/alerts/{alert_id}", headers=headers).json()["error"]
    absent = secure_client.get("/api/v1/alerts/missing-id", headers=headers).json()["error"]
    assert (denied["code"], denied["message"]) == (absent["code"], absent["message"])
    acknowledged = secure_client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge", json={}, headers=headers
    )
    assert acknowledged.status_code == 404


def test_deactivated_user_cannot_open_an_alert(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    candidate(sessions)
    clear_outbox(sessions)
    headers = bearer("analyst-a")
    alert_id = inbox(secure_client, headers).items[0].alert_id
    admin.deactivate_user(sessions, users.ids["analyst-a"])
    assert secure_client.get(f"/api/v1/alerts/{alert_id}", headers=headers).status_code == 403


# --- Acknowledgment ---------------------------------------------------------------------------


def test_acknowledgment_is_idempotent_and_syncs_across_recipients_and_devices(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    users: Users,
) -> None:
    exceedance_case(secure_client, runtime, sessions, bearer())
    clear_outbox(sessions)
    alert_id = titled(secure_client, bearer("reviewer-a"), "exceedance")[0].alert_id
    path = f"/api/v1/alerts/{alert_id}/acknowledge"
    windows = {**bearer("reviewer-a"), "Idempotency-Key": uuid4().hex}
    android = {**bearer("reviewer-a"), "Idempotency-Key": uuid4().hex}
    first = secure_client.post(path, json={"comment": "Looking."}, headers=windows)
    second = secure_client.post(path, json={}, headers=android)
    assert first.status_code == second.status_code == 200
    assert first.json()["ack_id"] == second.json()["ack_id"]

    other = secure_client.get(f"/api/v1/alerts/{alert_id}", headers=bearer("analyst-a"))
    detail = AlertDetail.model_validate(other.json())
    assert detail.status == "ACKNOWLEDGED"
    assert [ack.actor_id for ack in detail.acknowledgments] == [users.ids["reviewer-a"]]
    with sessions() as session:
        audit = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "acknowledge_alert")
        ).all()
    assert audit


def test_demo_viewer_cannot_acknowledge(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    response = secure_client.post(
        "/api/v1/alerts/any/acknowledge",
        json={},
        headers={**bearer("demo-a"), "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 403


# --- Push -------------------------------------------------------------------------------------


def test_push_payload_is_opaque_and_the_token_is_protected(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    device = register(secure_client, bearer("analyst-a"))
    assert PUSH_TOKEN not in str(device)
    assert "push_token" not in device
    candidate(sessions)
    clear_outbox(sessions)
    gateway = FakeGateway()
    assert alerts.process_push(sessions, gateway, cipher) == 1

    token, payload = gateway.sent[0]
    assert token == PUSH_TOKEN
    assert set(payload.model_dump()) == {"alert_id", "category", "created_at_utc"}
    assert SECRET_NOTICE not in payload.model_dump_json()
    with sessions() as session:
        stored = session.get_one(RegisteredDeviceRow, device["device_id"])
        assert PUSH_TOKEN.encode() not in (stored.push_token_encrypted or b"")
        delivery = session.scalars(
            select(AlertDeliveryRow).where(AlertDeliveryRow.channel == "ANDROID")
        ).one()
    assert delivery.state == "SENT"
    assert delivery.delivered_at_utc is None
    assert delivery.provider_message_id == "message-1"


def test_sending_is_not_reported_as_delivered_to_the_user(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    register(secure_client, bearer("analyst-a"))
    candidate(sessions)
    clear_outbox(sessions)
    alerts.process_push(sessions, FakeGateway(), cipher)
    alert_id = inbox(secure_client, bearer("analyst-a")).items[0].alert_id
    detail = secure_client.get(f"/api/v1/alerts/{alert_id}", headers=bearer("analyst-a")).json()
    states = {item["channel"]: item["state"] for item in detail["deliveries"]}
    assert states == {"IN_APP": "READ", "ANDROID": "SENT"}


def test_without_a_gateway_push_fails_visibly_and_the_inbox_still_works(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    register(secure_client, bearer("analyst-a"))
    candidate(sessions)
    clear_outbox(sessions)
    alerts.process_push(sessions, None, cipher)
    with sessions() as session:
        delivery = session.scalars(
            select(AlertDeliveryRow).where(AlertDeliveryRow.channel == "ANDROID")
        ).one()
    assert (delivery.state, delivery.failure_code) == ("FAILED", "PUSH_NOT_CONFIGURED")
    assert len(inbox(secure_client, bearer("analyst-a")).items) == 1


def test_revoked_device_receives_nothing_more(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    device = register(secure_client, bearer("analyst-a"))
    candidate(sessions)
    clear_outbox(sessions)
    path = f"/api/v1/devices/{device['device_id']}"
    assert secure_client.delete(path, headers=bearer("analyst-b")).status_code == 404
    assert secure_client.delete(path, headers=bearer("analyst-a")).status_code == 204
    gateway = FakeGateway()
    alerts.process_push(sessions, gateway, cipher)
    assert gateway.sent == []
    with sessions() as session:
        delivery = session.scalars(
            select(AlertDeliveryRow).where(AlertDeliveryRow.channel == "ANDROID")
        ).one()
        stored = session.get_one(RegisteredDeviceRow, device["device_id"])
    assert delivery.failure_code == "DEVICE_REVOKED"
    assert stored.push_token_encrypted is None


def test_token_moves_to_the_latest_signed_in_user(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    first = register(secure_client, bearer("analyst-a"))
    second = register(secure_client, bearer("reviewer-a"))
    assert first["device_id"] != second["device_id"]
    candidate(sessions)  # Routed to analysts: the handset now belongs to the reviewer.
    clear_outbox(sessions)
    gateway = FakeGateway()
    alerts.process_push(sessions, gateway, cipher)
    assert gateway.sent == []
    assert register(secure_client, bearer("reviewer-a"))["device_id"] == second["device_id"]


def test_dead_token_revokes_the_device(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    device = register(secure_client, bearer("analyst-a"))
    candidate(sessions)
    clear_outbox(sessions)
    alerts.process_push(sessions, FakeGateway(error=alerts.PushTokenInvalid()), cipher)
    with sessions() as session:
        assert session.get_one(RegisteredDeviceRow, device["device_id"]).status == "REVOKED"


def test_provider_outage_retries_then_stops_visibly(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    register(secure_client, bearer("analyst-a"))
    candidate(sessions)
    clear_outbox(sessions)
    gateway = FakeGateway(error=alerts.PushUnavailable())
    moment = jobs.utc_now()
    for _ in range(3):
        alerts.process_push(sessions, gateway, cipher, now=moment)
        moment += timedelta(hours=1)
    with sessions() as session:
        delivery = session.scalars(
            select(AlertDeliveryRow).where(AlertDeliveryRow.channel == "ANDROID")
        ).one()
    assert (delivery.attempt, delivery.state) == (3, "FAILED")
    assert delivery.failure_code == "PROVIDER_UNAVAILABLE"


def test_push_quota_stops_a_storm_but_the_inbox_keeps_everything(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alerts, "PUSH_QUOTA_PER_USER_PER_HOUR", 2)
    register(secure_client, bearer("analyst-a"))
    for _ in range(4):
        candidate(sessions)
    clear_outbox(sessions)
    gateway = FakeGateway()
    alerts.process_push(sessions, gateway, cipher)
    assert len(gateway.sent) == 2
    assert len(inbox(secure_client, bearer("analyst-a")).items) == 4


def _at_hour(hour: int) -> Any:
    return jobs.utc_now().replace(hour=hour, minute=0, second=0, microsecond=0)


def test_quiet_hours_delay_normal_push_but_not_a_critical_one(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
) -> None:
    register(secure_client, bearer("reviewer-a"))
    response = secure_client.put(
        "/api/v1/alerts/preferences",
        json={
            "enabled_channels": ["ANDROID"],
            "quiet_hours_start_utc": "22:00",
            "quiet_hours_end_utc": "06:00",
        },
        headers=bearer("reviewer-a"),
    )
    assert response.status_code == 200
    assert "IN_APP" in response.json()["enabled_channels"]

    night = _at_hour(23)
    forged_event(sessions, "SOURCE_REVISED", "pub-1", resource_type="source_publication")
    case_id = candidate(sessions)
    alerts.process_outbox(sessions, now=night)
    secure_client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={"action": "ESCALATE", "decision_reason": "Urgent."},
        headers={**bearer("reviewer-a"), "Idempotency-Key": uuid4().hex},
    )
    alerts.process_outbox(sessions, now=night)

    gateway = FakeGateway()
    alerts.process_push(sessions, gateway, cipher, now=night)
    assert len(gateway.sent) == 1
    alerts.process_push(sessions, gateway, cipher, now=night + timedelta(hours=8))
    assert len(gateway.sent) == 2


def test_channel_opt_out_keeps_security_alerts(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    cipher: alerts.TokenCipher,
    users: Users,
) -> None:
    register(secure_client, bearer("admin-a"))
    secure_client.put(
        "/api/v1/alerts/preferences",
        json={"enabled_channels": ["IN_APP"]},
        headers=bearer("admin-a"),
    )
    forged_event(sessions, "SOURCE_FAILED", "src", resource_type="source_connector")
    admin.revoke_sessions(sessions, users.ids["no-roles-a"])
    clear_outbox(sessions)
    gateway = FakeGateway()
    alerts.process_push(sessions, gateway, cipher)
    assert len(gateway.sent) == 1


def test_device_registration_without_a_key_is_refused(
    secure_client: TestClient, bearer: Bearer
) -> None:
    response = secure_client.post(
        "/api/v1/devices",
        json={"platform": "ANDROID", "push_token": "x"},
        headers=bearer("analyst-a"),
    )
    assert response.status_code == 503


# --- Escalation -------------------------------------------------------------------------------


def _rule_with_timeout(client: TestClient, bearer: Bearer) -> None:
    rule_id = f"{TENANT_A}-RELEVANT_CANDIDATE"
    response = client.put(
        "/api/v1/admin/alert-rules",
        json={
            "rule_id": rule_id,
            "trigger_kind": "RELEVANT_CANDIDATE",
            "severity": "REVIEW",
            "enabled": True,
            "evidence_requirement": "SOURCE_PROVENANCE",
            "routing_roles": ["ANALYST"],
            "dedupe_window_seconds": 0,
            "ack_timeout_seconds": 600,
            "escalation_policy": {"escalate_to_roles": ["REVIEWER"]},
        },
        headers=bearer("admin-a"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2


def test_escalation_runs_once_only_after_the_timeout(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    _rule_with_timeout(secure_client, bearer)
    candidate(sessions)
    now = jobs.utc_now()
    alerts.process_outbox(sessions, now=now)
    assert inbox(secure_client, bearer("reviewer-a")).items == []
    assert alerts.process_escalations(sessions, now=now + timedelta(seconds=599)) == 0
    assert alerts.process_escalations(sessions, now=now + timedelta(seconds=601)) == 1
    assert len(inbox(secure_client, bearer("reviewer-a")).items) == 1
    assert alerts.process_escalations(sessions, now=now + timedelta(seconds=999)) == 0


def test_acknowledged_alert_does_not_escalate(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    _rule_with_timeout(secure_client, bearer)
    candidate(sessions)
    now = jobs.utc_now()
    alerts.process_outbox(sessions, now=now)
    alert_id = inbox(secure_client, bearer("analyst-a")).items[0].alert_id
    secure_client.post(
        f"/api/v1/alerts/{alert_id}/acknowledge",
        json={},
        headers={**bearer("analyst-a"), "Idempotency-Key": uuid4().hex},
    )
    assert alerts.process_escalations(sessions, now=now + timedelta(hours=1)) == 0


# --- Rules ------------------------------------------------------------------------------------


def test_rules_are_per_tenant_versioned_and_admin_only(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    assert secure_client.get("/api/v1/admin/alert-rules", headers=bearer()).status_code == 403
    rules = secure_client.get("/api/v1/admin/alert-rules", headers=bearer("admin-a")).json()
    assert len(rules["items"]) == len(alerts.DEFAULT_RULES)
    assert all(rule["rule_id"].startswith(TENANT_A) for rule in rules["items"])

    candidate(sessions)
    clear_outbox(sessions)
    before = inbox(secure_client, bearer("analyst-a")).items[0]
    _rule_with_timeout(secure_client, bearer)
    assert before.rule_version == 1
    latest = secure_client.get("/api/v1/admin/alert-rules", headers=bearer("admin-a")).json()
    versions = {rule["rule_id"]: rule["version"] for rule in latest["items"]}
    assert versions[before.rule_id] == 2
    with sessions() as session:
        audit = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "save_alert_rule")
        ).all()
    assert audit


def test_exceedance_rule_cannot_drop_the_verified_gate(
    secure_client: TestClient, bearer: Bearer
) -> None:
    response = secure_client.put(
        "/api/v1/admin/alert-rules",
        json={
            "trigger_kind": "POTENTIAL_EXCEEDANCE",
            "severity": "HIGH",
            "enabled": True,
            "evidence_requirement": "SOURCE_PROVENANCE",
            "routing_roles": ["ANALYST"],
            "dedupe_window_seconds": 0,
        },
        headers=bearer("admin-a"),
    )
    assert response.status_code == 422


def test_another_tenants_rule_cannot_be_edited(secure_client: TestClient, bearer: Bearer) -> None:
    response = secure_client.put(
        "/api/v1/admin/alert-rules",
        json={
            "rule_id": f"{TENANT_B}-SOURCE_STALE",
            "trigger_kind": "SOURCE_STALE",
            "severity": "OPERATIONS",
            "enabled": False,
            "evidence_requirement": "OPERATIONAL_DIAGNOSTIC",
            "routing_roles": ["ADMINISTRATOR"],
            "dedupe_window_seconds": 0,
        },
        headers=bearer("admin-a"),
    )
    assert response.status_code == 404


def test_disabled_rule_creates_nothing(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    secure_client.put(
        "/api/v1/admin/alert-rules",
        json={
            "rule_id": f"{TENANT_A}-RELEVANT_CANDIDATE",
            "trigger_kind": "RELEVANT_CANDIDATE",
            "severity": "REVIEW",
            "enabled": False,
            "evidence_requirement": "SOURCE_PROVENANCE",
            "routing_roles": ["ANALYST"],
            "dedupe_window_seconds": 0,
        },
        headers=bearer("admin-a"),
    )
    candidate(sessions)
    clear_outbox(sessions)
    assert inbox(secure_client, bearer("analyst-a")).items == []


# --- Realtime and preferences -----------------------------------------------------------------


def test_stream_needs_a_session_and_sends_only_safe_summaries(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
) -> None:
    assert secure_client.get("/api/v1/alerts/stream").status_code == 401
    secure_app.state.alert_stream_max_seconds = 0.3
    candidate(sessions)
    # Dated in the future, so that it is new to a stream starting now.
    alerts.process_outbox(sessions, now=jobs.utc_now() + timedelta(hours=1))
    response = secure_client.get("/api/v1/alerts/stream", headers=bearer("analyst-a"))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.text.count("event: alert") == 1
    assert "New candidate to screen" in response.text
    assert SECRET_NOTICE not in response.text

    other = secure_client.get("/api/v1/alerts/stream", headers=bearer("reviewer-a"))
    assert "event: alert" not in other.text


def test_stream_ends_when_the_session_is_revoked(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(alert_api, "_STREAM_REAUTH_SECONDS", 0.0)
    secure_app.state.alert_stream_max_seconds = 5.0
    headers = bearer("analyst-a")
    admin.deactivate_user(sessions, users.ids["analyst-a"])
    security = secure_app.state.security
    original = security.authorize
    # Connect as if the check passed just before the account was deactivated.
    monkeypatch.setattr(
        security,
        "authorize",
        lambda *_args: alerts.Principal(
            users.ids["analyst-a"], TENANT_A, frozenset(), frozenset(alerts.capabilities_for(set()))
        ),
    )
    response = secure_client.get("/api/v1/alerts/stream", headers=headers)
    assert "event: session-ended" in response.text
    assert original is not None


def test_preferences_round_trip_and_validation(secure_client: TestClient, bearer: Bearer) -> None:
    headers = bearer("analyst-a")
    defaults = secure_client.get("/api/v1/alerts/preferences", headers=headers).json()
    assert "ANDROID" in defaults["enabled_channels"]
    saved = secure_client.put(
        "/api/v1/alerts/preferences",
        json={"enabled_channels": [], "quiet_hours_start_utc": "22:00"},
        headers=headers,
    )
    assert saved.json()["enabled_channels"] == ["IN_APP"]
    assert (
        secure_client.put(
            "/api/v1/alerts/preferences",
            json={"enabled_channels": [], "quiet_hours_start_utc": "not a time"},
            headers=headers,
        ).status_code
        == 422
    )


def test_quiet_hours_calculation() -> None:
    preference = alerts.AlertPreferenceRow(
        user_id="u", enabled_channels=[], quiet_hours_start_utc="22:00", quiet_hours_end_utc="06:00"
    )
    assert alerts._quiet_until(preference, _at_hour(12)) is None
    assert alerts._quiet_until(preference, _at_hour(23)) == _at_hour(6) + timedelta(days=1)
    assert alerts._quiet_until(preference, _at_hour(3)) == _at_hour(6)
    assert alerts._quiet_until(None, _at_hour(3)) is None
