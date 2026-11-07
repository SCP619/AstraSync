"""FastAPI application factory. Run with ``uvicorn astrasync_api.app:create_app --factory``."""

import os
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic.json_schema import models_json_schema

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


def _build_security(settings: Settings, keys: JwksCache | None) -> SecurityRuntime:
    if not settings.configured:
        return SecurityRuntime()
    assert settings.oidc is not None  # noqa: S101 - guaranteed by ``configured``.
    assert settings.database_url is not None  # noqa: S101 - guaranteed by ``configured``.
    oidc = settings.oidc
    keys = keys or JwksCache(lambda: fetch_jwks_over_http(oidc.jwks_uri))
    sessions = build_session_factory(build_engine(settings.database_url))
    return SecurityRuntime(
        environment=settings.environment,
        validator=TokenValidator(oidc, keys),
        identities=IdentityStore(sessions),
    )


def _load_draft_agent(settings: Settings) -> EvidenceDraftAgent | None:
    if not settings.draft_agent:
        return None
    agent = load_named(settings.draft_agent)()
    if not isinstance(agent, EvidenceDraftAgent):
        raise SettingsError("The draft agent does not implement EvidenceDraftAgent")
    return agent


def create_app(settings: Settings | None = None, *, keys: JwksCache | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_env(os.environ)
    # Interactive docs and the live spec stay off: the contract ships as a reviewed file.
    app = FastAPI(
        title="AstraSync API",
        version=CONTRACT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.security = _build_security(settings, keys)
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
        )
    app.state.draft_agent = _load_draft_agent(settings)
    app.state.ai_classifications = frozenset(
        UsageClassification(level) for level in settings.ai_classifications
    )
    install_error_handlers(app)
    app.include_router(router)
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
