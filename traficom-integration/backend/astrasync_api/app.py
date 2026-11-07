"""FastAPI application factory."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic.json_schema import models_json_schema

from .contract import CONTRACT_VERSION
from .contract.models import (
    AgentDraftResponse,
    DomainEvent,
    MethodAssessment,
    MethodCalculation,
    PushPayload,
)
from .errors import install_error_handlers
from .routes import router

# Payloads exchanged outside REST, published so workers and clients share one generated contract.
_INTEGRATION_MODELS = (
    AgentDraftResponse,
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


def create_app() -> FastAPI:
    # Interactive docs and the live spec stay off: the contract ships as a reviewed file.
    app = FastAPI(
        title="AstraSync API",
        version=CONTRACT_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    install_error_handlers(app)
    app.include_router(router)
    return app


app = create_app()
