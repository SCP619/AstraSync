"""Route capabilities, object access, audit and operational settings."""

import os
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from conftest import TENANT_A, TENANT_B, Users, oidc_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from astrasync_api.app import create_app
from astrasync_api.authz import ObjectAccessPolicy, ObjectRef, not_found
from astrasync_api.config import Settings, SettingsError
from astrasync_api.contract.enums import Environment, ErrorCode, UsageClassification
from astrasync_api.contract.models import ErrorResponse
from astrasync_api.contract.permissions import ROLE_CAPABILITIES, Capability, Role
from astrasync_api.db import AuditEvent, ResourceEntitlement, schema_differences
from astrasync_api.identity import Principal
from astrasync_api.security import AuthorizedRoute

SUBJECT_BY_ROLE = {
    Role.ANALYST: "analyst-a",
    Role.REVIEWER: "reviewer-a",
    Role.ADMINISTRATOR: "admin-a",
    Role.DEMO_VIEWER: "demo-a",
}


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "demo-id", path)


def _operations(openapi: dict[str, Any]) -> list[tuple[str, str, Capability]]:
    return [
        (method, path, Capability(operation["x-required-capability"]))
        for path, item in openapi["paths"].items()
        for method, operation in item.items()
    ]


@pytest.mark.parametrize("role", list(Role))
def test_every_route_enforces_the_role_matrix(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    openapi: dict[str, Any],
    role: Role,
) -> None:
    headers = {**bearer(SUBJECT_BY_ROLE[role]), "Idempotency-Key": "demo-key-1"}
    for method, path, capability in _operations(openapi):
        response = secure_client.request(method.upper(), _concrete(path), headers=headers)
        allowed = capability in ROLE_CAPABILITIES[role] or capability is Capability.AUTHENTICATED
        label = f"{role} {method} {path}"
        if allowed:
            assert response.status_code not in (401, 403), label
        else:
            assert response.status_code == 403, label
            body = ErrorResponse.model_validate(response.json())
            assert body.error.code is ErrorCode.FORBIDDEN


def test_analyst_cannot_approve_but_reviewer_can_reach_approval(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    """The IPD stage 1 exit test."""
    body = {
        "action": "APPROVE_DRAFT",
        "decision_reason": "Evidence checked.",
        "draft_id": "DEMO-DRAFT-001",
    }
    path = "/api/v1/cases/DEMO-SPACE-001/reviews"
    idempotency = {"Idempotency-Key": "demo-key-1"}

    assert secure_client.post(path, json=body, headers=idempotency).status_code == 401

    denied = secure_client.post(path, json=body, headers={**bearer("analyst-a"), **idempotency})
    assert denied.status_code == 403

    denied = secure_client.post(path, json=body, headers={**bearer("admin-a"), **idempotency})
    assert denied.status_code == 403

    reached = secure_client.post(path, json=body, headers={**bearer("reviewer-a"), **idempotency})
    assert reached.status_code == 501
    assert ErrorResponse.model_validate(reached.json()).error.code is ErrorCode.NOT_IMPLEMENTED


def test_user_without_roles_reaches_only_me(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]], openapi: dict[str, Any]
) -> None:
    headers = {**bearer("no-roles-a"), "Idempotency-Key": "demo-key-1"}
    for method, path, capability in _operations(openapi):
        response = secure_client.request(method.upper(), _concrete(path), headers=headers)
        expected_denied = capability is not Capability.AUTHENTICATED
        assert (response.status_code == 403) is expected_denied, f"{method} {path}"


def test_authorization_runs_before_the_body_is_read(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    malformed = {"content": b"{not json", "headers": {"content-type": "application/json"}}
    anonymous = secure_client.post("/api/v1/uploads", **malformed)
    assert anonymous.status_code == 401

    headers = {**malformed["headers"], **bearer("reviewer-a")}
    wrong_role = secure_client.post(
        "/api/v1/uploads", content=malformed["content"], headers=headers
    )
    assert wrong_role.status_code == 403

    headers = {**malformed["headers"], **bearer("analyst-a"), "Idempotency-Key": "demo-key-1"}
    permitted = secure_client.post("/api/v1/uploads", content=malformed["content"], headers=headers)
    assert permitted.status_code == 422


def test_body_tenant_and_role_are_rejected_for_a_permitted_user(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    response = secure_client.post(
        "/api/v1/uploads",
        json={
            "source_type": "SPACE_IFIC",
            "usage_classification": "RESTRICTED",
            "filename_original": "demo.iso",
            "expected_size_bytes": 1,
            "tenant_id": TENANT_B,
            "role": "ADMINISTRATOR",
        },
        headers={**bearer("analyst-a"), "Idempotency-Key": "demo-key-1"},
    )
    assert response.status_code == 422
    assert TENANT_B not in response.text


def test_a_v1_route_without_a_capability_cannot_be_registered() -> None:
    with pytest.raises(RuntimeError, match="no required capability"):
        AuthorizedRoute("/api/v1/open", lambda: None)


def test_a_route_with_an_unknown_capability_cannot_be_registered() -> None:
    with pytest.raises(ValueError):
        AuthorizedRoute(
            "/api/v1/open", lambda: None, openapi_extra={"x-required-capability": "EVERYONE"}
        )


# --- Audit ------------------------------------------------------------------------------------


def _audit_events(sessions: sessionmaker[Session], action: str) -> list[AuditEvent]:
    with sessions() as session:
        return list(session.scalars(select(AuditEvent).where(AuditEvent.action == action)).all())


def test_denied_action_is_audited_without_secrets(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = {**bearer("analyst-a"), "Idempotency-Key": "demo-key-1"}
    response = secure_client.post("/api/v1/cases/DEMO-SPACE-001/reviews", headers=headers)
    events = _audit_events(sessions, "create_review")
    assert len(events) == 1
    event = events[0]
    assert event.actor == users.ids["analyst-a"]
    assert event.tenant_id == TENANT_A
    assert event.object_type == "cases"
    assert event.object_id == "DEMO-SPACE-001"
    assert event.outcome == "DENIED"
    assert event.correlation_id == response.headers["X-Request-ID"]
    stored = " ".join(str(value) for value in vars(event).values())
    assert headers["Authorization"].split()[1] not in stored


def test_allowed_write_and_sensitive_read_are_audited(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
) -> None:
    secure_client.get("/api/v1/cases/DEMO-SPACE-001/export", headers=bearer("reviewer-a"))
    assert [event.outcome for event in _audit_events(sessions, "export_case")] == ["ALLOWED"]


def test_ordinary_reads_do_not_fill_the_audit_log(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
) -> None:
    secure_client.get("/api/v1/me", headers=bearer("analyst-a"))
    secure_client.get("/api/v1/cases", headers=bearer("analyst-a"))
    assert _audit_events(sessions, "get_me") == []
    assert _audit_events(sessions, "list_cases") == []


def test_sensitive_action_stops_if_it_cannot_be_audited(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_kwargs: Any) -> None:
        raise OperationalError("insert", {}, Exception("audit down"))

    identities = secure_client.app.state.security.identities  # type: ignore[attr-defined]
    monkeypatch.setattr(identities, "record_audit", fail)
    response = secure_client.get("/api/v1/cases/DEMO-1/export", headers=bearer("reviewer-a"))
    assert response.status_code == 503


def test_denial_stays_denied_if_it_cannot_be_audited(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(**_kwargs: Any) -> None:
        raise OperationalError("insert", {}, Exception("audit down"))

    identities = secure_client.app.state.security.identities  # type: ignore[attr-defined]
    monkeypatch.setattr(identities, "record_audit", fail)
    response = secure_client.get("/api/v1/cases/DEMO-1/export", headers=bearer("analyst-a"))
    assert response.status_code == 403


@pytest.mark.skipif(
    not os.environ.get("ASTRASYNC_TEST_DATABASE_URL"), reason="PostgreSQL trigger only"
)
@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_events SET outcome = 'ALLOWED'", "DELETE FROM audit_events"],
)
def test_audit_events_are_append_only_on_postgresql(
    engine: Engine, users: Users, statement: str
) -> None:
    with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
        connection.execute(text(statement))


# --- Object access ----------------------------------------------------------------------------


def _principal(users: Users, subject: str, tenant: str, *roles: Role) -> Principal:
    return Principal(
        user_id=users.ids[subject],
        tenant_id=tenant,
        roles=frozenset(roles),
        capabilities=frozenset({Capability.AUTHENTICATED}),
    )


def _object(
    classification: UsageClassification = UsageClassification.RESTRICTED,
    *,
    tenant: str = TENANT_A,
    is_synthetic: bool = False,
) -> ObjectRef:
    return ObjectRef(
        object_type="source_artifact",
        object_id="DEMO-ARTIFACT-001",
        tenant_id=tenant,
        classification=classification,
        is_synthetic=is_synthetic,
    )


def _entitle(
    sessions: sessionmaker[Session],
    users: Users,
    subject: str,
    *,
    rights: tuple[str, ...] = ("READ",),
    expires_at: datetime | None = None,
    classification: str = "RESTRICTED",
    object_id: str = "DEMO-ARTIFACT-001",
) -> None:
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id=f"{subject}-{object_id}-{classification}",
                subject=users.ids[subject],
                tenant_id=TENANT_A,
                object_type="source_artifact",
                object_id=object_id,
                classification=classification,
                rights=list(rights),
                expires_at_utc=expires_at,
            )
        )
        session.commit()


def test_other_tenants_object_is_denied_even_with_public_data(
    sessions: sessionmaker[Session], users: Users
) -> None:
    policy = ObjectAccessPolicy(sessions)
    analyst_b = _principal(users, "analyst-b", TENANT_B, Role.ANALYST)
    assert not policy.can_access(analyst_b, _object(UsageClassification.PUBLIC), "READ")


def test_restricted_object_needs_an_entitlement(
    sessions: sessionmaker[Session], users: Users
) -> None:
    policy = ObjectAccessPolicy(sessions)
    analyst = _principal(users, "analyst-a", TENANT_A, Role.ANALYST)
    assert not policy.can_access(analyst, _object(), "READ")
    _entitle(sessions, users, "analyst-a")
    assert policy.can_access(analyst, _object(), "READ")
    assert not policy.can_access(analyst, _object(), "DOWNLOAD")


@pytest.mark.parametrize(
    "classification",
    [
        UsageClassification.RESTRICTED,
        UsageClassification.CONFIDENTIAL_PARTNER,
        UsageClassification.UNVERIFIED,
    ],
)
def test_administrator_has_no_bypass(
    sessions: sessionmaker[Session], users: Users, classification: UsageClassification
) -> None:
    policy = ObjectAccessPolicy(sessions)
    administrator = _principal(users, "admin-a", TENANT_A, Role.ADMINISTRATOR)
    assert not policy.can_access(administrator, _object(classification), "READ")


def test_expired_entitlement_gives_no_access(
    sessions: sessionmaker[Session], users: Users
) -> None:
    _entitle(sessions, users, "analyst-a", expires_at=datetime.now(UTC) - timedelta(seconds=1))
    policy = ObjectAccessPolicy(sessions)
    analyst = _principal(users, "analyst-a", TENANT_A, Role.ANALYST)
    assert not policy.can_access(analyst, _object(), "READ")


def test_entitlement_is_specific_to_object_and_classification(
    sessions: sessionmaker[Session], users: Users
) -> None:
    _entitle(sessions, users, "analyst-a", object_id="DEMO-ARTIFACT-OTHER")
    _entitle(sessions, users, "analyst-a", classification="UNVERIFIED")
    policy = ObjectAccessPolicy(sessions)
    analyst = _principal(users, "analyst-a", TENANT_A, Role.ANALYST)
    assert not policy.can_access(analyst, _object(), "READ")


def test_demo_viewer_sees_only_synthetic_data(
    sessions: sessionmaker[Session], users: Users
) -> None:
    policy = ObjectAccessPolicy(sessions)
    viewer = _principal(users, "demo-a", TENANT_A, Role.DEMO_VIEWER)
    assert not policy.can_access(viewer, _object(UsageClassification.INTERNAL), "READ")
    synthetic = _object(UsageClassification.INTERNAL, is_synthetic=True)
    assert policy.can_access(viewer, synthetic, "READ")


def test_denied_object_is_indistinguishable_from_a_missing_one(
    sessions: sessionmaker[Session], users: Users
) -> None:
    policy = ObjectAccessPolicy(sessions)
    analyst_b = _principal(users, "analyst-b", TENANT_B, Role.ANALYST)
    with pytest.raises(type(not_found())) as denied:
        policy.require_access(analyst_b, _object(), "READ")
    absent = not_found()
    assert (denied.value.status_code, denied.value.code, denied.value.message) == (
        absent.status_code,
        absent.code,
        absent.message,
    )


# --- Settings, CORS, headers, migrations ------------------------------------------------------


@pytest.mark.parametrize(
    ("environment", "database_url", "oidc", "cors"),
    [
        pytest.param(
            Environment.PRODUCTION,
            "postgresql+psycopg://db/app",
            oidc_settings(issuer="http://idp.test.invalid"),
            (),
            id="production-http-issuer",
        ),
        pytest.param(
            Environment.PRODUCTION,
            "sqlite:///demo.db",
            oidc_settings(),
            (),
            id="production-sqlite",
        ),
        pytest.param(
            Environment.STAGING,
            "postgresql+psycopg://db/app",
            oidc_settings(mfa_required=False),
            (),
            id="staging-mfa-off",
        ),
        pytest.param(
            Environment.PRODUCTION,
            "postgresql+psycopg://db/app",
            oidc_settings(required_scopes=frozenset()),
            (),
            id="production-no-scope",
        ),
        pytest.param(
            Environment.DEMO,
            "sqlite:///demo.db",
            oidc_settings(algorithms=("HS256",)),
            (),
            id="shared-secret-algorithm",
        ),
        pytest.param(
            Environment.DEMO,
            "sqlite:///demo.db",
            oidc_settings(algorithms=("none",)),
            (),
            id="none-algorithm",
        ),
        pytest.param(
            Environment.DEMO,
            "sqlite:///demo.db",
            oidc_settings(issuer="http://192.0.2.10/"),
            (),
            id="demo-http-off-loopback",
        ),
        pytest.param(
            Environment.DEMO, "sqlite:///demo.db", oidc_settings(), ("*",), id="wildcard-cors"
        ),
        pytest.param(
            Environment.DEMO,
            "sqlite:///demo.db",
            oidc_settings(mfa_amr_values=frozenset(), mfa_acr_values=frozenset()),
            (),
            id="mfa-required-without-accepted-values",
        ),
    ],
)
def test_unsafe_settings_refuse_to_start(
    environment: Environment, database_url: str, oidc: Any, cors: tuple[str, ...]
) -> None:
    with pytest.raises(SettingsError):
        Settings(environment=environment, database_url=database_url, oidc=oidc, cors_origins=cors)


def test_secure_production_settings_are_accepted() -> None:
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url="postgresql+psycopg://db/app",
        oidc=oidc_settings(),
        cors_origins=("https://tauri.localhost",),
    )
    assert settings.configured


def test_partial_environment_configuration_is_an_error() -> None:
    with pytest.raises(SettingsError, match="ASTRASYNC_OIDC_AUDIENCE"):
        Settings.from_env(
            {
                "ASTRASYNC_ENVIRONMENT": "DEMO",
                "ASTRASYNC_DATABASE_URL": "sqlite:///demo.db",
                "ASTRASYNC_OIDC_ISSUER": "http://localhost:1/",
            }
        )


def test_empty_environment_is_unconfigured_and_denies() -> None:
    assert not Settings.from_env({}).configured


def test_mfa_defaults_to_required() -> None:
    settings = Settings.from_env(
        {
            "ASTRASYNC_ENVIRONMENT": "DEMO",
            "ASTRASYNC_DATABASE_URL": "sqlite:///demo.db",
            "ASTRASYNC_OIDC_ISSUER": "http://localhost:1/",
            "ASTRASYNC_OIDC_AUDIENCE": "astrasync-api",
            "ASTRASYNC_OIDC_JWKS_URI": "http://localhost:1/jwks",
        }
    )
    assert settings.oidc is not None
    assert settings.oidc.mfa_required


def test_cors_only_answers_approved_origins() -> None:
    app: FastAPI = create_app(Settings(cors_origins=("https://tauri.localhost",)))
    client = TestClient(app)
    preflight = {
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization",
    }
    allowed = client.options(
        "/api/v1/me", headers={"Origin": "https://tauri.localhost", **preflight}
    )
    assert allowed.headers["Access-Control-Allow-Origin"] == "https://tauri.localhost"
    assert "Access-Control-Allow-Credentials" not in allowed.headers
    denied = client.options("/api/v1/me", headers={"Origin": "https://evil.invalid", **preflight})
    assert "Access-Control-Allow-Origin" not in denied.headers


def test_responses_are_not_cacheable(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    assert secure_client.get("/api/v1/me", headers=bearer()).headers["Cache-Control"] == "no-store"


def test_migrations_match_the_models(engine: Engine) -> None:
    assert schema_differences(engine) == []


def test_migration_seeds_exactly_the_contract_roles(engine: Engine) -> None:
    with engine.connect() as connection:
        names = set(connection.execute(text("SELECT name FROM roles")).scalars())
    assert names == {role.value for role in Role}
