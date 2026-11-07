"""User, role and entitlement administration (ADMIN_USERS, DECISIONS G26).

Server-side rules: tenant scoping, no self-modification, no content access for administrators,
identity by issuer plus subject, classification taken from the source, every change audited, and
changes effective on the target's very next request.
"""

from typing import Any

from conftest import ISSUER, TENANT_A
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_source_library import (  # noqa: F401 - fixtures used by name.
    RESTRICTED,
    SYNTHETIC,
    Bearer,
    Users,
    adapters,
    fake_source,
    registered_sources,
    restricted_artifact,  # noqa: F811
    runtime,
    store,
)

from astrasync_api.db import AuditEvent

ADMIN = "/api/v1/admin/users"


def detail(client: TestClient, headers: dict[str, str], user_id: str) -> dict[str, Any]:
    response = client.get(f"{ADMIN}/{user_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_only_administrators_can_administer(secure_client: TestClient, bearer: Bearer) -> None:
    for subject in ("analyst-a", "reviewer-a", "demo-a", "no-roles-a"):
        assert secure_client.get(ADMIN, headers=bearer(subject)).status_code == 403, subject
    assert secure_client.get(ADMIN).status_code == 401


def test_the_list_holds_the_administrators_tenant_only(
    secure_client: TestClient, bearer: Bearer, users: Users
) -> None:
    items = secure_client.get(ADMIN, headers=bearer("admin-a")).json()["items"]
    subjects = {item["oidc_subject"] for item in items}
    assert {"analyst-a", "reviewer-a", "admin-a"} <= subjects
    assert "analyst-b" not in subjects
    other = users.ids["analyst-b"]
    for method, path, body in (
        ("get", f"{ADMIN}/{other}", None),
        ("put", f"{ADMIN}/{other}/roles", {"roles": []}),
        ("put", f"{ADMIN}/{other}/status", {"active": False}),
        ("post", f"{ADMIN}/{other}/revoke-sessions", None),
    ):
        response = secure_client.request(method, path, json=body, headers=bearer("admin-a"))
        assert response.status_code == 404, path


def test_administrators_still_get_no_content(secure_client: TestClient, bearer: Bearer) -> None:
    headers = bearer("admin-a")
    for path in ("/api/v1/cases", "/api/v1/source-records"):
        assert secure_client.get(path, headers=headers).status_code == 403, path


def test_an_unprovisioned_identity_gets_nothing_until_provisioned(
    secure_client: TestClient, bearer: Bearer
) -> None:
    newcomer = bearer("newcomer-a")
    assert secure_client.get("/api/v1/me", headers=newcomer).status_code == 403
    created = secure_client.post(
        ADMIN,
        json={"issuer": ISSUER, "oidc_subject": "newcomer-a", "roles": []},
        headers=bearer("admin-a"),
    )
    assert created.status_code == 201, created.text
    assert created.json()["effective_capabilities"] == []  # No roles, no capabilities.
    me = secure_client.get("/api/v1/me", headers=newcomer)
    assert me.status_code == 200 and me.json()["roles"] == []
    assert secure_client.get("/api/v1/cases", headers=newcomer).status_code == 403
    again = secure_client.post(
        ADMIN,
        json={"issuer": ISSUER, "oidc_subject": "newcomer-a", "roles": ["ANALYST"]},
        headers=bearer("admin-a"),
    )
    assert again.status_code == 409  # Idempotent: one identity, one user.


def test_provisioning_refuses_bad_input_and_client_chosen_tenants(
    secure_client: TestClient, bearer: Bearer
) -> None:
    headers = bearer("admin-a")
    for body in (
        {"issuer": "not-a-url", "oidc_subject": "x", "roles": []},
        {"issuer": ISSUER, "oidc_subject": "", "roles": []},
        {"issuer": ISSUER, "oidc_subject": "x", "roles": ["SUPERUSER"]},
        {"issuer": ISSUER, "oidc_subject": "x", "roles": [], "tenant_id": "DEMO-TENANT-B"},
    ):
        response = secure_client.post(ADMIN, json=body, headers=headers)
        assert response.status_code == 422, body
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_roles_take_effect_on_the_next_request_and_cannot_be_self_assigned(
    secure_client: TestClient, bearer: Bearer, users: Users
) -> None:
    admin, target = bearer("admin-a"), users.ids["no-roles-a"]
    assert secure_client.get("/api/v1/cases", headers=bearer("no-roles-a")).status_code == 403
    changed = secure_client.put(
        f"{ADMIN}/{target}/roles", json={"roles": ["ANALYST"]}, headers=admin
    )
    assert changed.status_code == 200
    assert "CASE_READ" in changed.json()["effective_capabilities"]
    assert secure_client.get("/api/v1/cases", headers=bearer("no-roles-a")).status_code == 200
    own = users.ids["admin-a"]
    for method, path, body in (
        ("put", f"{ADMIN}/{own}/roles", {"roles": ["ADMINISTRATOR", "REVIEWER"]}),
        ("put", f"{ADMIN}/{own}/status", {"active": False}),
        ("post", f"{ADMIN}/{own}/revoke-sessions", None),
        ("post", f"{ADMIN}/{own}/entitlements", {"source_id": RESTRICTED, "rights": ["READ"]}),
    ):
        response = secure_client.request(method, path, json=body, headers=admin)
        assert response.status_code == 403, path


def test_a_non_administrator_cannot_escalate(
    secure_client: TestClient, bearer: Bearer, users: Users
) -> None:
    analyst = bearer("analyst-a")
    own = users.ids["analyst-a"]
    response = secure_client.put(
        f"{ADMIN}/{own}/roles", json={"roles": ["ADMINISTRATOR"]}, headers=analyst
    )
    assert response.status_code == 403
    assert (
        "ADMIN_USERS" not in secure_client.get("/api/v1/me", headers=analyst).json()["capabilities"]
    )


def test_deactivation_and_revocation_apply_to_existing_tokens(
    secure_client: TestClient, bearer: Bearer, users: Users
) -> None:
    admin, target = bearer("admin-a"), users.ids["reviewer-a"]
    reviewer = bearer("reviewer-a")  # Issued before the changes below.
    assert (
        secure_client.put(f"{ADMIN}/{target}/status", json={"active": False}, headers=admin).json()[
            "effective_capabilities"
        ]
        == []
    )
    assert secure_client.get("/api/v1/me", headers=reviewer).status_code == 403
    secure_client.put(f"{ADMIN}/{target}/status", json={"active": True}, headers=admin)
    assert secure_client.get("/api/v1/me", headers=reviewer).status_code == 200
    revoked = secure_client.post(f"{ADMIN}/{target}/revoke-sessions", headers=admin)
    assert revoked.json()["user"]["sessions_revoked_before_utc"] is not None
    assert secure_client.get("/api/v1/me", headers=reviewer).status_code == 401


def test_entitlements_follow_the_source_and_open_restricted_records(
    secure_client: TestClient,
    bearer: Bearer,
    users: Users,
    restricted_artifact: dict[str, str],  # noqa: F811
) -> None:
    admin, target = bearer("admin-a"), users.ids["reviewer-a"]
    reviewer = bearer("reviewer-a")
    assert secure_client.get("/api/v1/source-records", headers=reviewer).json()["items"] == []
    granted = secure_client.post(
        f"{ADMIN}/{target}/entitlements",
        json={"source_id": RESTRICTED, "rights": ["READ"]},
        headers=admin,
    )
    assert granted.status_code == 201, granted.text
    [entitlement] = granted.json()["entitlements"]
    assert entitlement["classification"] == "RESTRICTED"  # From the source, not the client.
    assert len(secure_client.get("/api/v1/source-records", headers=reviewer).json()["items"]) == 2
    revoked = secure_client.delete(
        f"{ADMIN}/{target}/entitlements/{entitlement['grant_id']}", headers=admin
    )
    assert revoked.status_code == 200 and revoked.json()["entitlements"] == []
    assert secure_client.get("/api/v1/source-records", headers=reviewer).json()["items"] == []


def test_entitlement_requests_are_validated(
    secure_client: TestClient, bearer: Bearer, users: Users
) -> None:
    admin, target = bearer("admin-a"), users.ids["reviewer-a"]
    path = f"{ADMIN}/{target}/entitlements"
    for body, status in (
        ({"source_id": "NO-SUCH-SOURCE", "rights": ["READ"]}, 404),
        ({"source_id": SYNTHETIC, "rights": []}, 422),
        ({"source_id": SYNTHETIC, "rights": ["DELETE"]}, 422),
        ({"source_id": SYNTHETIC, "rights": ["READ"], "classification": "PUBLIC"}, 422),
        (
            {"source_id": SYNTHETIC, "rights": ["READ"], "expires_at_utc": "2001-01-01T00:00:00Z"},
            422,
        ),
    ):
        assert secure_client.post(path, json=body, headers=admin).status_code == status, body
    missing = f"{path}/no-such-grant"
    assert secure_client.delete(missing, headers=admin).status_code == 404


def test_changes_are_audited_with_the_acting_administrator(
    secure_client: TestClient, bearer: Bearer, users: Users, sessions: sessionmaker[Session]
) -> None:
    target = users.ids["no-roles-a"]
    secure_client.put(
        f"{ADMIN}/{target}/roles", json={"roles": ["DEMO_VIEWER"]}, headers=bearer("admin-a")
    )
    with sessions() as session:
        events = {
            e.action: (e.actor, e.tenant_id, e.object_id, e.outcome)
            for e in session.scalars(select(AuditEvent)).all()
        }
    expected = (users.ids["admin-a"], TENANT_A, target, "ALLOWED")
    assert events["admin_set_roles"] == expected  # The authorised request, before it runs.
    assert events["user_roles_changed"] == expected  # The change, once committed.


def test_a_refused_self_change_is_audited_as_denied(
    secure_client: TestClient, bearer: Bearer, users: Users, sessions: sessionmaker[Session]
) -> None:
    own = users.ids["admin-a"]
    response = secure_client.put(
        f"{ADMIN}/{own}/status", json={"active": False}, headers=bearer("admin-a")
    )
    assert response.status_code == 403
    with sessions() as session:
        refused = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "self_access_change_refused")
        ).one()
    assert (refused.actor, refused.object_id, refused.outcome) == (own, own, "DENIED")
