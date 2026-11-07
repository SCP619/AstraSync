"""FastAPI application factory. Run with ``uvicorn astrasync_api.app:create_app --factory``."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic.json_schema import models_json_schema
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from .alerts import TokenCipher
from .authz import ObjectAccessPolicy
from .config import Settings, SettingsError, load_named
from .contract import CONTRACT_VERSION
from .contract.enums import UsageClassification
from .contract.interfaces import EvidenceDraftAgent
from .contract.models import (
    AdapterRecord,
    AgentDraftResponse,
    CaseCandidate,
    DomainEvent,
    MethodAssessment,
    MethodCalculation,
    PushPayload,
)
from .db import build_engine, build_session_factory
from .errors import install_error_handlers
from .identity import IdentityStore
from .library import LibraryRuntime
from .objectstore import LocalObjectStore
from .oidc import JwksCache, TokenValidator, fetch_jwks_over_http
from .record_store import ParquetRecordStore
from .routes import router
from .security import SecurityRuntime

# Payloads exchanged outside REST, published so workers and clients share one generated contract.
_INTEGRATION_MODELS = (
    AdapterRecord,
    AgentDraftResponse,
    CaseCandidate,
    DomainEvent,
    MethodAssessment,
    MethodCalculation,
    PushPayload,
)


def build_openapi(app: FastAPI) -> dict[str, Any]:
    schema = get_openapi(
        title="AstraSync API",
        version=CONTRACT_VERSION,
        routes=app.routes,
        # One schema per model, so the UI and fixtures see the same type for reads and writes.
        separate_input_output_schemas=False,
    )
    _, definitions = models_json_schema(
        [(model, "validation") for model in _INTEGRATION_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    schema["components"]["schemas"].update(definitions["$defs"])
    return schema


def _build_security(
    settings: Settings, keys: JwksCache | None
) -> tuple[SecurityRuntime, Engine | None]:
    if not settings.configured:
        return SecurityRuntime(), None
    assert settings.oidc is not None  # noqa: S101 - guaranteed by ``configured``.
    assert settings.database_url is not None  # noqa: S101 - guaranteed by ``configured``.
    oidc = settings.oidc
    keys = keys or JwksCache(lambda: fetch_jwks_over_http(oidc.jwks_uri))
    engine = build_engine(settings.database_url)
    sessions = build_session_factory(engine)
    security = SecurityRuntime(
        environment=settings.environment,
        validator=TokenValidator(oidc, keys),
        identities=IdentityStore(sessions),
    )
    return security, engine


def dispose_app(app: FastAPI) -> None:
    """Closes the app's pooled database connections (on shutdown, and after each test)."""
    engine: Engine | None = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()


def _load_draft_agent(settings: Settings) -> EvidenceDraftAgent | None:
    if not settings.draft_agent:
        return None
    agent = load_named(settings.draft_agent)()
    if not isinstance(agent, EvidenceDraftAgent):
        raise SettingsError("The draft agent does not implement EvidenceDraftAgent")
    return agent


def _install_probes(app: FastAPI) -> None:
    """Unauthenticated liveness and readiness for orchestration. They reveal nothing else."""

    @app.get("/healthz", include_in_schema=False)
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def ready() -> JSONResponse:
        identities = app.state.security.identities
        if identities is None:
            return JSONResponse({"status": "unconfigured"}, status_code=503)
        try:
            with identities.session_factory() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"status": "database unavailable"}, status_code=503)
        return JSONResponse({"status": "ready"})


def create_app(settings: Settings | None = None, *, keys: JwksCache | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env(os.environ)
    # Interactive docs and the live spec stay off: the contract ships as a reviewed file.
    security, engine = _build_security(settings, keys)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        dispose_app(app)

    app = FastAPI(
        title="AstraSync API",
        version=CONTRACT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    # The app owns its database engine: ``dispose_app`` closes its pooled connections.
    app.state.engine = engine
    app.state.security = security
    identities = app.state.security.identities
    app.state.object_access = None
    app.state.library = None
    if identities is not None:
        app.state.object_access = ObjectAccessPolicy(identities.session_factory)
        app.state.library = LibraryRuntime(
            policy=app.state.object_access,
            identities=identities,
            store=(
                LocalObjectStore(settings.object_store_path)
                if settings.object_store_path is not None
                else None
            ),
            max_upload_bytes=settings.max_upload_bytes,
            records=(
                ParquetRecordStore(settings.record_store_path)
                if settings.record_store_path is not None
                else None
            ),
        )
    app.state.push_cipher = (
        TokenCipher(settings.push_token_key) if settings.push_token_key else None
    )
    app.state.alert_stream_poll_seconds = 2.0
    app.state.alert_stream_max_seconds = 900.0
    app.state.draft_agent = _load_draft_agent(settings)
    app.state.ai_classifications = frozenset(
        UsageClassification(level) for level in settings.ai_classifications
    )
    install_error_handlers(app)
    app.include_router(router)
    _install_probes(app)
    if settings.cors_origins:
        # Bearer tokens only, so no cookies and no credentialed CORS.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
            expose_headers=["X-Request-ID"],
        )
    return app
