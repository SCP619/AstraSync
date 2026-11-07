"""Token validation and identity lifecycle (SECURITY_AND_ACCESS.md sections 2 and 8)."""

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from conftest import ISSUER, TENANT_A, TENANT_B, TokenFactory, Users, oidc_settings, public_jwk
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from astrasync_api import admin
from astrasync_api.config import Settings
from astrasync_api.contract.enums import ErrorCode
from astrasync_api.contract.models import ErrorResponse, Me
from astrasync_api.contract.permissions import Capability, Role
from astrasync_api.db import UserRoleGrant
from astrasync_api.oidc import (
    IdentityProviderUnavailable,
    JwksCache,
    TokenRejected,
    TokenValidator,
)

ME = "/api/v1/me"


def _code(response: Any) -> ErrorCode:
    return ErrorResponse.model_validate(response.json()).error.code


def test_valid_token_returns_server_side_identity(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]], users: Users
) -> None:
    response = secure_client.get(ME, headers=bearer("analyst-a"))
    assert response.status_code == 200
    me = Me.model_validate(response.json())
    assert me.user_id == users.ids["analyst-a"]
    assert me.tenant_id == TENANT_A
    assert me.roles == [Role.ANALYST]
    assert Capability.ANALYSIS_RUN in me.capabilities
    assert Capability.REVIEW_DECIDE not in me.capabilities


def test_role_and_tenant_claims_in_a_token_are_ignored(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    headers = bearer(
        "analyst-a",
        roles=["ADMINISTRATOR", "REVIEWER"],
        role="ADMINISTRATOR",
        tenant_id=TENANT_B,
        groups=["admin"],
    )
    me = Me.model_validate(secure_client.get(ME, headers=headers).json())
    assert me.tenant_id == TENANT_A
    assert me.roles == [Role.ANALYST]


def test_client_supplied_identity_hints_are_ignored(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    response = secure_client.get(
        ME,
        params={"tenant_id": TENANT_B, "role": "ADMINISTRATOR"},
        headers={**bearer("analyst-a"), "X-Tenant-Id": TENANT_B, "X-Role": "ADMINISTRATOR"},
    )
    me = Me.model_validate(response.json())
    assert me.tenant_id == TENANT_A
    assert me.roles == [Role.ANALYST]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"iss": "https://evil.test.invalid/"}, id="wrong-issuer"),
        pytest.param({"aud": "another-api"}, id="wrong-audience"),
        pytest.param({"exp": int(time.time()) - 3600}, id="expired"),
        pytest.param({"nbf": int(time.time()) + 3600}, id="not-yet-valid"),
        pytest.param({"exp": None}, id="missing-exp"),
        pytest.param({"iat": None}, id="missing-iat"),
        pytest.param({"aud": None}, id="missing-aud"),
        pytest.param({"iss": None}, id="missing-iss"),
        pytest.param({"sub": ""}, id="empty-subject"),
        pytest.param({"scope": "openid"}, id="missing-scope"),
        pytest.param({"scope": None}, id="no-scope"),
    ],
)
def test_invalid_claims_are_rejected(
    secure_client: TestClient, token: TokenFactory, overrides: dict[str, Any]
) -> None:
    response = secure_client.get(
        ME, headers={"Authorization": f"Bearer {token('analyst-a', **overrides)}"}
    )
    assert response.status_code == 401
    assert _code(response) is ErrorCode.UNAUTHENTICATED
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_expired_token_tells_the_client_to_sign_in_again(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    response = secure_client.get(ME, headers=bearer(exp=int(time.time()) - 3600))
    body = ErrorResponse.model_validate(response.json())
    assert body.error.details == {"reason": "TOKEN_EXPIRED"}


def test_token_signed_by_another_key_is_rejected(
    secure_client: TestClient, token: TokenFactory, other_key: rsa.RSAPrivateKey
) -> None:
    forged = token("analyst-a", key=other_key)
    response = secure_client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_unsigned_token_is_rejected(secure_client: TestClient) -> None:
    header = jwt.utils.base64url_encode(json.dumps({"alg": "none", "kid": "test-key-1"}).encode())
    now = int(time.time())
    payload = jwt.utils.base64url_encode(
        json.dumps(
            {
                "iss": ISSUER,
                "aud": "astrasync-api",
                "sub": "analyst-a",
                "iat": now,
                "exp": now + 300,
                "scope": "astrasync.api",
                "amr": ["mfa"],
            }
        ).encode()
    )
    forged = f"{header.decode()}.{payload.decode()}."
    response = secure_client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_public_key_used_as_shared_secret_is_rejected(
    secure_client: TestClient, signing_key: rsa.RSAPrivateKey
) -> None:
    """The classic RS256-to-HS256 confusion attack."""
    public_pem = signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    now = int(time.time())
    header = jwt.utils.base64url_encode(
        json.dumps({"alg": "HS256", "kid": "test-key-1", "typ": "JWT"}).encode()
    )
    payload = jwt.utils.base64url_encode(
        json.dumps(
            {
                "iss": ISSUER,
                "aud": "astrasync-api",
                "sub": "analyst-a",
                "iat": now,
                "exp": now + 300,
                "scope": "astrasync.api",
                "amr": ["mfa"],
            }
        ).encode()
    )
    signature = hmac.new(public_pem, header + b"." + payload, hashlib.sha256).digest()
    forged = b".".join([header, payload, jwt.utils.base64url_encode(signature)]).decode()
    response = secure_client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="missing-kid"),
        pytest.param({"kid": "unknown-key"}, id="unknown-kid"),
    ],
)
def test_token_without_a_known_key_id_is_rejected(
    secure_client: TestClient, token: TokenFactory, headers: dict[str, str]
) -> None:
    forged = token("analyst-a", headers=headers)
    response = secure_client.get(ME, headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Bearer",
        "Bearer ",
        "Basic abc",
        "not-a-token",
        "Bearer not.a.jwt",
        "Bearer " + "x" * 9000,
    ],
)
def test_malformed_authorization_is_rejected(secure_client: TestClient, authorization: str) -> None:
    response = secure_client.get(ME, headers={"Authorization": authorization})
    assert response.status_code == 401


def test_token_in_query_string_is_not_accepted(
    secure_client: TestClient, token: TokenFactory
) -> None:
    response = secure_client.get(ME, params={"access_token": token("analyst-a")})
    assert response.status_code == 401


def test_token_without_mfa_is_rejected_with_a_specific_code(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    for amr in (["pwd"], None):
        response = secure_client.get(ME, headers=bearer(amr=amr))
        assert response.status_code == 401
        assert _code(response) is ErrorCode.MFA_REQUIRED


def test_mfa_can_be_proven_by_an_acr_value(
    signing_key: rsa.RSAPrivateKey, token: TokenFactory
) -> None:
    settings = oidc_settings(
        mfa_amr_values=frozenset(), mfa_acr_values=frozenset({"urn:example:mfa"})
    )
    validator = TokenValidator(settings, JwksCache(lambda: {"keys": [public_jwk(signing_key)]}))
    assert validator.validate(token(acr="urn:example:mfa", amr=None)).subject == "analyst-a"
    with pytest.raises(TokenRejected) as rejected:
        validator.validate(token(acr="urn:example:low", amr=["mfa"]))
    assert rejected.value.reason == "MFA_REQUIRED"


def test_valid_token_for_an_unprovisioned_user_is_forbidden(
    secure_client: TestClient, bearer: Callable[..., dict[str, str]]
) -> None:
    """There is no self-registration: a correct sign-in alone gives no access."""
    response = secure_client.get(ME, headers=bearer("someone-new"))
    assert response.status_code == 403


def test_same_subject_from_another_issuer_is_a_different_identity(
    secure_client: TestClient,
    sessions: sessionmaker[Session],
    users: Users,
    token: TokenFactory,
) -> None:
    admin.provision_user(
        sessions,
        tenant_id=TENANT_B,
        issuer="https://other.test.invalid/",
        subject="analyst-a",
        roles=[Role.REVIEWER],
    )
    me = Me.model_validate(
        secure_client.get(ME, headers={"Authorization": f"Bearer {token('analyst-a')}"}).json()
    )
    assert me.tenant_id == TENANT_A
    assert me.roles == [Role.ANALYST]


def test_deactivation_applies_to_an_unexpired_token(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = bearer("analyst-a")
    assert secure_client.get(ME, headers=headers).status_code == 200
    admin.deactivate_user(sessions, users.ids["analyst-a"])
    assert secure_client.get(ME, headers=headers).status_code == 403


def test_session_revocation_rejects_old_tokens_but_allows_new_sign_in(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    old = bearer("analyst-a", iat=int(time.time()) - 10)
    assert secure_client.get(ME, headers=old).status_code == 200
    admin.revoke_sessions(sessions, users.ids["analyst-a"])
    assert secure_client.get(ME, headers=old).status_code == 401
    fresh = bearer("analyst-a", iat=int(time.time()) + 2)
    assert secure_client.get(ME, headers=fresh).status_code == 200


def test_revoked_role_applies_to_an_unexpired_token(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = bearer("reviewer-a")
    assert secure_client.get("/api/v1/references", headers=headers).status_code == 200
    admin.revoke_role(sessions, users.ids["reviewer-a"], Role.REVIEWER)
    assert secure_client.get("/api/v1/references", headers=headers).status_code == 403
    me = Me.model_validate(secure_client.get(ME, headers=headers).json())
    assert me.roles == []
    assert me.capabilities == [Capability.AUTHENTICATED]


def test_expired_grant_gives_no_capability(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    with sessions() as session:
        session.add(
            UserRoleGrant(
                user_id=users.ids["no-roles-a"],
                role_id=Role.REVIEWER.value,
                tenant_id=TENANT_A,
                expires_at_utc=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    me = Me.model_validate(secure_client.get(ME, headers=bearer("no-roles-a")).json())
    assert me.roles == []


def test_grant_in_another_tenant_gives_no_capability(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    with sessions() as session:
        session.add(
            UserRoleGrant(
                user_id=users.ids["no-roles-a"], role_id=Role.REVIEWER.value, tenant_id=TENANT_B
            )
        )
        session.commit()
    me = Me.model_validate(secure_client.get(ME, headers=bearer("no-roles-a")).json())
    assert me.roles == []


def test_token_with_valid_shape_is_denied_while_unconfigured(
    client: TestClient, token: TokenFactory
) -> None:
    response = client.get(ME, headers={"Authorization": f"Bearer {token()}"})
    assert response.status_code == 503
    assert _code(response) is ErrorCode.SERVICE_UNAVAILABLE


def test_database_failure_denies_the_request(
    secure_client: TestClient,
    bearer: Callable[..., dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise OperationalError("select", {}, Exception("database down"))

    identities = secure_client.app.state.security.identities  # type: ignore[attr-defined]
    monkeypatch.setattr(identities, "resolve", fail)
    response = secure_client.get(ME, headers=bearer())
    assert response.status_code == 503
    assert "database down" not in response.text


class _Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_jwks_rotation_is_picked_up_for_an_unknown_key_id(
    signing_key: rsa.RSAPrivateKey, other_key: rsa.RSAPrivateKey
) -> None:
    document = {"keys": [public_jwk(signing_key, "k1")]}
    clock = _Clock()
    cache = JwksCache(lambda: document, min_refresh_seconds=60, clock=clock)
    assert cache.key_for("k1") is not None
    document = {"keys": [public_jwk(signing_key, "k1"), public_jwk(other_key, "k2")]}
    clock.now += 61
    assert cache.key_for("k2") is not None


def test_forged_key_ids_cannot_hammer_the_provider(signing_key: rsa.RSAPrivateKey) -> None:
    calls = 0

    def fetch() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {"keys": [public_jwk(signing_key, "k1")]}

    cache = JwksCache(fetch, min_refresh_seconds=60, clock=_Clock())
    cache.key_for("k1")
    for attempt in range(20):
        with pytest.raises(TokenRejected):
            cache.key_for(f"forged-{attempt}")
    assert calls == 1


def test_provider_outage_with_no_keys_is_unavailable_not_valid() -> None:
    def fail() -> dict[str, Any]:
        raise ValueError("unreachable")

    with pytest.raises(IdentityProviderUnavailable):
        JwksCache(fail).key_for("k1")


def test_cached_keys_survive_an_outage_only_until_the_stale_limit(
    signing_key: rsa.RSAPrivateKey,
) -> None:
    available = True

    def fetch() -> dict[str, Any]:
        if not available:
            raise ValueError("unreachable")
        return {"keys": [public_jwk(signing_key, "k1")]}

    clock = _Clock()
    cache = JwksCache(fetch, ttl_seconds=10, max_stale_seconds=100, clock=clock)
    cache.key_for("k1")
    available = False
    clock.now += 50
    assert cache.key_for("k1") is not None
    clock.now += 60
    with pytest.raises(IdentityProviderUnavailable):
        cache.key_for("k1")


def test_shared_secret_and_private_keys_in_jwks_are_ignored(
    signing_key: rsa.RSAPrivateKey,
) -> None:
    published = {
        "keys": [
            {"kty": "oct", "kid": "shared", "k": "c2VjcmV0"},
            {**public_jwk(signing_key, "private"), "d": "AQAB"},
            {**public_jwk(signing_key, "encryption"), "use": "enc"},
            public_jwk(signing_key, "good"),
        ]
    }
    cache = JwksCache(lambda: published)
    assert cache.key_for("good") is not None
    for kid in ("shared", "private", "encryption"):
        with pytest.raises(TokenRejected):
            cache.key_for(kid)


def test_unconfigured_settings_have_no_identity(client: TestClient) -> None:
    assert Settings().configured is False
    assert client.get(ME).status_code == 401
