"""Shared fixtures. Set ASTRASYNC_TEST_DATABASE_URL to run on PostgreSQL instead of SQLite."""

import os
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from astrasync_api import admin
from astrasync_api.app import build_openapi, create_app
from astrasync_api.config import OidcSettings, Settings
from astrasync_api.contract.enums import Environment
from astrasync_api.contract.permissions import Role
from astrasync_api.db import build_engine, build_session_factory, run_migrations
from astrasync_api.oidc import JwksCache

CONTRACT_DIR = Path(__file__).resolve().parents[2] / "contract"
FIXTURES_DIR = CONTRACT_DIR / "fixtures"

ISSUER = "https://idp.test.invalid/realms/astrasync"
AUDIENCE = "astrasync-api"
SCOPE = "astrasync.api"
KID = "test-key-1"
TENANT_A = "DEMO-TENANT-A"
TENANT_B = "DEMO-TENANT-B"


@pytest.fixture
def app() -> FastAPI:
    """Unconfigured deployment: no identity provider or database."""
    return create_app(Settings())


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def openapi(app: FastAPI) -> dict:
    return build_openapi(app)


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def other_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def public_jwk(key: rsa.RSAPrivateKey, kid: str = KID) -> dict[str, Any]:
    jwk: dict[str, Any] = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


@dataclass
class TokenFactory:
    key: rsa.RSAPrivateKey

    def __call__(
        self,
        subject: str = "analyst-a",
        *,
        key: Any = None,
        algorithm: str = "RS256",
        headers: dict[str, Any] | None = None,
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": subject,
            "iat": now,
            "exp": now + 300,
            "scope": SCOPE,
            "amr": ["pwd", "mfa"],
            **overrides,
        }
        claims = {name: value for name, value in claims.items() if value is not None}
        return jwt.encode(
            claims,
            key if key is not None else self.key,
            algorithm=algorithm,
            headers={"kid": KID} if headers is None else headers,
        )


@pytest.fixture
def token(signing_key: rsa.RSAPrivateKey) -> TokenFactory:
    return TokenFactory(signing_key)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    url = os.environ.get("ASTRASYNC_TEST_DATABASE_URL")
    if url:
        engine = build_engine(url)
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    else:
        engine = build_engine(f"sqlite:///{tmp_path / 'test.db'}")
    run_migrations(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return build_session_factory(engine)


@dataclass
class Users:
    """The role fixtures, as provisioned server-side. Maps OIDC subject to user ID."""

    ids: dict[str, str] = field(default_factory=dict)


@pytest.fixture
def users(sessions: sessionmaker[Session]) -> Users:
    admin.create_tenant(sessions, TENANT_A, "1")
    admin.create_tenant(sessions, TENANT_B, "1")
    people = {
        "analyst-a": (TENANT_A, [Role.ANALYST]),
        "reviewer-a": (TENANT_A, [Role.REVIEWER]),
        "admin-a": (TENANT_A, [Role.ADMINISTRATOR]),
        "demo-a": (TENANT_A, [Role.DEMO_VIEWER]),
        "analyst-b": (TENANT_B, [Role.ANALYST]),
        "no-roles-a": (TENANT_A, []),
    }
    return Users(
        {
            subject: admin.provision_user(
                sessions, tenant_id=tenant, issuer=ISSUER, subject=subject, roles=roles
            )
            for subject, (tenant, roles) in people.items()
        }
    )


def oidc_settings(**overrides: Any) -> OidcSettings:
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "audience": AUDIENCE,
        "jwks_uri": "https://idp.test.invalid/jwks",
        "algorithms": ("RS256",),
        "required_scopes": frozenset({SCOPE}),
        "mfa_required": True,
        "mfa_amr_values": frozenset({"mfa"}),
        "mfa_acr_values": frozenset(),
        **overrides,
    }
    return OidcSettings(**values)


@pytest.fixture
def jwks_document(signing_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    return {"keys": [public_jwk(signing_key)]}


@pytest.fixture
def secure_app(
    engine: Engine, users: Users, jwks_document: dict[str, Any], tmp_path: Path
) -> FastAPI:
    settings = Settings(
        environment=Environment.DEMO,
        database_url=engine.url.render_as_string(hide_password=False),
        oidc=oidc_settings(),
        object_store_path=tmp_path / "objects",
        # ASTRASYNC_TEST_RECORD_STORE=parquet runs the suite on the Parquet record store.
        record_store_path=(
            tmp_path / "records"
            if os.environ.get("ASTRASYNC_TEST_RECORD_STORE") == "parquet"
            else None
        ),
        max_upload_bytes=1024 * 1024,
    )
    app = create_app(settings, keys=JwksCache(lambda: jwks_document))
    # Route sweeps call every route, so the stream must end on its own.
    app.state.alert_stream_poll_seconds = 0.02
    app.state.alert_stream_max_seconds = 0.1
    return app


@pytest.fixture
def record_store(secure_app: FastAPI) -> Any:
    """The app's Parquet record store, or None when records go to the PostgreSQL index."""
    return secure_app.state.library.records


@pytest.fixture
def secure_client(secure_app: FastAPI) -> TestClient:
    return TestClient(secure_app, raise_server_exceptions=False)


@pytest.fixture
def bearer(token: TokenFactory) -> Callable[..., dict[str, str]]:
    def build(subject: str = "analyst-a", **overrides: Any) -> dict[str, str]:
        return {"Authorization": f"Bearer {token(subject, **overrides)}"}

    return build
