"""Local-only development stack: a throwaway identity provider and the API with test accounts.

NOT part of the product. It is not packaged, binds to loopback and has no passwords: any local
user can pick any persona. The API accepts it only in the DEMO environment, because config.py
refuses plain-HTTP issuers elsewhere and off loopback.

    python tests/support/dev_stack.py idp
    python tests/support/dev_stack.py api
"""

import base64
import hashlib
import html
import os
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa
from demo_adapter import FORMAT_HEADER, DemoAdapter
from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select

from astrasync_api import admin
from astrasync_api.contract.enums import (
    IssueDomain,
    JobType,
    SourceType,
    UsageClassification,
)
from astrasync_api.contract.permissions import Role
from astrasync_api.db import (
    ResourceEntitlement,
    Tenant,
    User,
    build_engine,
    build_session_factory,
    run_migrations,
)
from astrasync_api.ingest import IncomingBytes, PipelineContext, register_bytes
from astrasync_api.jobs import LANE_INGESTION, enqueue
from astrasync_api.library_tables import SourceConnectorRow
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.worker import WorkerRuntime, run_until_idle

HOST = "127.0.0.1"
IDP_PORT = 8801
API_PORT = 8800
UI_ORIGIN = f"http://{HOST}:5173"
ISSUER = f"http://{HOST}:{IDP_PORT}"
CLIENT_ID = "astrasync-dev-ui"
AUDIENCE = "astrasync-api"
REDIRECT_URIS = {f"{UI_ORIGIN}/auth/callback"}
LOGOUT_URIS = {f"{UI_ORIGIN}/login"}
KID = "dev-key-1"
TENANT_A = "DEMO-TENANT-A"
TENANT_B = "DEMO-TENANT-B"
DEV_DIR = Path(__file__).resolve().parents[2] / ".dev"
DATABASE_PATH = DEV_DIR / "astrasync-dev.db"
OBJECTS_PATH = DEV_DIR / "objects"


@dataclass(frozen=True)
class Persona:
    subject: str
    label: str
    amr: tuple[str, ...] = ("pwd", "mfa")
    token_lifetime_seconds: int = 900


PERSONAS = {
    persona.subject: persona
    for persona in (
        Persona("analyst-a", "Analyst, tenant A"),
        Persona("reviewer-a", "Reviewer, tenant A"),
        Persona("admin-a", "Administrator, tenant A"),
        Persona("demo-a", "Demo viewer, tenant A"),
        Persona("analyst-b", "Analyst, tenant B"),
        Persona("no-roles-a", "Provisioned with no role"),
        Persona("not-provisioned", "Valid sign-in, no AstraSync account"),
        Persona("analyst-no-mfa", "Analyst signed in without MFA", amr=("pwd",)),
        Persona("analyst-expired", "Analyst with an expired token", token_lifetime_seconds=-3600),
    )
}
_SEED_ACCOUNTS = {
    "analyst-a": (TENANT_A, [Role.ANALYST]),
    "reviewer-a": (TENANT_A, [Role.REVIEWER]),
    "admin-a": (TENANT_A, [Role.ADMINISTRATOR]),
    "demo-a": (TENANT_A, [Role.DEMO_VIEWER]),
    "analyst-b": (TENANT_B, [Role.ANALYST]),
    "no-roles-a": (TENANT_A, []),
    "analyst-no-mfa": (TENANT_A, [Role.ANALYST]),
    "analyst-expired": (TENANT_A, [Role.ANALYST]),
}


def create_idp() -> FastAPI:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk: dict[str, Any] = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    codes: dict[str, dict[str, str]] = {}

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[UI_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/.well-known/openid-configuration")
    def discovery() -> dict[str, Any]:
        return {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/jwks",
            "end_session_endpoint": f"{ISSUER}/logout",
            "response_types_supported": ["code"],
            "code_challenge_methods_supported": ["S256"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "subject_types_supported": ["public"],
        }

    @app.get("/jwks")
    def jwks() -> dict[str, Any]:
        return {"keys": [{**public_jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}

    @app.get("/authorize", response_class=HTMLResponse)
    def authorize(
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        state: str,
        response_type: str = "code",
        code_challenge_method: str = "S256",
        scope: str = "",
        nonce: str = "",
    ) -> str:
        if (
            client_id != CLIENT_ID
            or redirect_uri not in REDIRECT_URIS
            or response_type != "code"
            or code_challenge_method != "S256"
        ):
            raise HTTPException(400, "Invalid authorization request")
        hidden = {
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "state": state,
            "scope": scope,
            "nonce": nonce,
        }
        fields = "".join(
            f'<input type="hidden" name="{name}" value="{html.escape(value, quote=True)}">'
            for name, value in hidden.items()
        )
        buttons = "".join(
            f'<button name="subject" value="{p.subject}">{html.escape(p.label)}</button>'
            for p in PERSONAS.values()
        )
        return (
            "<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Development sign-in</title>"
            "<style>body{font:16px system-ui;margin:0 auto;max-width:440px;padding:24px 16px}"
            "button{display:block;width:100%;margin:8px 0;padding:12px;font:inherit;"
            "text-align:left;cursor:pointer}</style>"
            "<h1>Development sign-in</h1>"
            "<p><strong>Local testing only.</strong> Not a real identity provider. "
            "Choose a test persona. There are no passwords.</p>"
            f"<form method='post' action='/authorize'>{fields}{buttons}</form></html>"
        )

    @app.post("/authorize")
    def approve(
        subject: str = Form(),
        redirect_uri: str = Form(),
        code_challenge: str = Form(),
        state: str = Form(),
        scope: str = Form(""),
        nonce: str = Form(""),
    ) -> RedirectResponse:
        if redirect_uri not in REDIRECT_URIS or subject not in PERSONAS:
            raise HTTPException(400, "Invalid authorization request")
        code = secrets.token_urlsafe(24)
        codes[code] = {
            "subject": subject,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "scope": scope,
            "nonce": nonce,
            "expires_at": str(time.time() + 60),
        }
        query = urlencode({"code": code, "state": state, "iss": ISSUER})
        return RedirectResponse(f"{redirect_uri}?{query}", status_code=303)

    @app.post("/token")
    def token(
        grant_type: str = Form(),
        code: str = Form(),
        redirect_uri: str = Form(),
        code_verifier: str = Form(),
        client_id: str = Form(),
    ) -> dict[str, Any]:
        grant = codes.pop(code, None)  # Single use, whatever the outcome.
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        if (
            grant is None
            or grant_type != "authorization_code"
            or client_id != CLIENT_ID
            or redirect_uri != grant["redirect_uri"]
            or time.time() > float(grant["expires_at"])
            or not secrets.compare_digest(challenge, grant["code_challenge"])
        ):
            raise HTTPException(400, "invalid_grant")

        persona = PERSONAS[grant["subject"]]
        now = int(time.time())
        expires = now + persona.token_lifetime_seconds
        issued_at = min(now, expires - 60)
        common = {"iss": ISSUER, "sub": persona.subject, "iat": issued_at, "exp": expires}
        headers = {"kid": KID}
        access = jwt.encode(
            {**common, "aud": AUDIENCE, "scope": grant["scope"], "amr": list(persona.amr)},
            key,
            algorithm="RS256",
            headers=headers,
        )
        # The ID token is for the UI only and always readable, so that expiry reaches the API.
        identity: dict[str, Any] = {
            "iss": ISSUER,
            "sub": persona.subject,
            "aud": CLIENT_ID,
            "iat": now,
            "exp": now + 900,
        }
        if grant["nonce"]:
            identity["nonce"] = grant["nonce"]
        return {
            "access_token": access,
            "id_token": jwt.encode(identity, key, algorithm="RS256", headers=headers),
            "token_type": "Bearer",
            "expires_in": 900,
            "scope": grant["scope"],
        }

    @app.get("/logout")
    def logout(
        post_logout_redirect_uri: str = Query(""), state: str = Query("")
    ) -> RedirectResponse:
        target = post_logout_redirect_uri if post_logout_redirect_uri in LOGOUT_URIS else ISSUER
        suffix = f"?{urlencode({'state': state})}" if state and target != ISSUER else ""
        return RedirectResponse(f"{target}{suffix}", status_code=303)

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "AstraSync development identity provider", "scope": "local testing"}

    return app


def seed_accounts(database_url: str) -> None:
    engine = build_engine(database_url)
    run_migrations(engine)
    sessions = build_session_factory(engine)
    with sessions() as session:
        tenants = set(session.scalars(select(Tenant.tenant_id)).all())
        subjects = set(session.scalars(select(User.oidc_subject)).all())
    for tenant in (TENANT_A, TENANT_B):
        if tenant not in tenants:
            admin.create_tenant(sessions, tenant, "1")
    for subject, (tenant, roles) in _SEED_ACCOUNTS.items():
        if subject not in subjects:
            admin.provision_user(
                sessions, tenant_id=tenant, issuer=ISSUER, subject=subject, roles=roles
            )
    seed_sources(sessions)
    engine.dispose()


def _stage_bytes(store: LocalObjectStore, data: bytes) -> Any:
    path = store.new_staging_path()
    path.write_bytes(data)
    return store.hash_file(path)


def seed_sources(sessions: Any) -> None:
    """Made-up records through the real pipeline. Nothing here comes from a real source."""
    with sessions() as session:
        if session.get(SourceConnectorRow, "DEMO-SYNTHETIC") is not None:
            return
    common: dict[str, Any] = {
        "tenant_id": TENANT_A,
        "publisher": "Demo synthetic publisher",
        "domain": IssueDomain.FINNISH_REFERENCE,
        "source_type": SourceType.CHALLENGE_SYNTHETIC_REFERENCE,
        "rights_basis": "Made-up local test data",
        "is_synthetic": True,
    }
    admin.register_source(
        sessions,
        source_id="DEMO-SYNTHETIC",
        classification=UsageClassification.INTERNAL,
        **common,
    )
    admin.register_source(
        sessions,
        source_id="DEMO-RESTRICTED",
        classification=UsageClassification.RESTRICTED,
        **common,
    )
    with sessions() as session:
        analyst = session.scalar(select(User.user_id).where(User.oidc_subject == "analyst-a"))
        session.add(
            ResourceEntitlement(
                grant_id="dev-analyst-restricted",
                subject=analyst,
                tenant_id=TENANT_A,
                object_type="source",
                object_id="DEMO-RESTRICTED",
                classification="RESTRICTED",
                rights=["READ", "DOWNLOAD", "IMPORT"],
            )
        )
        session.commit()

    store = LocalObjectStore(OBJECTS_PATH)
    context = PipelineContext(
        sessions=sessions, store=store, adapters={DemoAdapter.source_type: DemoAdapter()}
    )
    rows = "\n".join(
        ("DEMO-STATION-1,100.5 MHz,10", "DEMO-STATION-2,99,20", "DEMO-STATION-3,410.25 MHz,5")
    )
    good = f"{FORMAT_HEADER}\n{rows}\n".encode()
    secret = f"{FORMAT_HEADER}\nDEMO-RESTRICTED-STATION,450 MHz,1\n".encode()
    artifacts = [
        register_bytes(
            context,
            IncomingBytes(
                tenant_id=TENANT_A,
                source_id="DEMO-SYNTHETIC",
                filename_original="demo-reference.txt",
                classification=UsageClassification.INTERNAL.value,
                staged=_stage_bytes(store, good),
                expected_size_bytes=len(good),
                transport_sha256=None,
                expected_digest=hashlib.sha256(good).hexdigest(),
                expected_digest_origin="uploader-supplied-manifest",
            ),
        ),
        register_bytes(
            context,
            IncomingBytes(
                tenant_id=TENANT_A,
                source_id="DEMO-RESTRICTED",
                filename_original="demo-restricted.txt",
                classification=UsageClassification.RESTRICTED.value,
                staged=_stage_bytes(store, secret),
                expected_size_bytes=len(secret),
                transport_sha256=None,
                expected_digest=None,
                expected_digest_origin=None,
            ),
        ),
    ]
    for artifact in artifacts:
        enqueue(
            sessions,
            tenant_id=TENANT_A,
            job_type=JobType.INGEST,
            lane=LANE_INGESTION,
            idempotency_key=f"seed:{artifact.artifact_id}",
            requested_by="dev-seed",
            payload={"artifact_id": artifact.artifact_id},
        )
    run_until_idle(WorkerRuntime(context=context, clients={}, worker_id="dev-seed"))


def run_api() -> None:
    DEV_DIR.mkdir(exist_ok=True)
    database_url = f"sqlite:///{DATABASE_PATH.as_posix()}"
    os.environ.update(
        {
            "ASTRASYNC_ENVIRONMENT": "DEMO",
            "ASTRASYNC_DATABASE_URL": database_url,
            "ASTRASYNC_OIDC_ISSUER": ISSUER,
            "ASTRASYNC_OIDC_AUDIENCE": AUDIENCE,
            "ASTRASYNC_OIDC_JWKS_URI": f"{ISSUER}/jwks",
            "ASTRASYNC_OIDC_REQUIRED_SCOPES": "astrasync.api",
            "ASTRASYNC_CORS_ORIGINS": UI_ORIGIN,
            "ASTRASYNC_OBJECT_STORE_PATH": str(OBJECTS_PATH),
        }
    )
    seed_accounts(database_url)
    uvicorn.run("astrasync_api.app:create_app", factory=True, host=HOST, port=API_PORT)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if target == "idp":
        uvicorn.run(create_idp(), host=HOST, port=IDP_PORT)
    elif target == "api":
        run_api()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
