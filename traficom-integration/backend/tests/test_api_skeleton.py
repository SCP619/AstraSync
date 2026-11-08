"""The API surface fails closed and answers every failure with the standard error envelope."""

import re
from typing import Any

import pytest
from conftest import CONTRACT_DIR
from fastapi import FastAPI
from fastapi.testclient import TestClient

from astrasync_api.contract.enums import ErrorCode, MethodApplicability, MethodExecution, MethodRole
from astrasync_api.contract.export import render_openapi
from astrasync_api.contract.models import ErrorResponse, MethodRun
from astrasync_api.contract.permissions import Capability
from astrasync_api.identity import Principal

# BSD sections 5, 6.4 and 9. Keeps a route from being dropped or renamed unnoticed.
DOCUMENTED_OPERATIONS = {
    ("get", "/api/v1/me"),
    ("post", "/api/v1/ingest/ific"),
    ("get", "/api/v1/jobs/{job_id}"),
    ("get", "/api/v1/issues"),
    ("get", "/api/v1/issues/{issue_id}/changes"),
    ("get", "/api/v1/cases"),
    ("get", "/api/v1/cases/{case_id}"),
    ("post", "/api/v1/cases/{case_id}/analyse"),
    ("get", "/api/v1/analyses/{analysis_run_id}"),
    ("get", "/api/v1/analyses/{analysis_run_id}/methods"),
    ("get", "/api/v1/references"),
    ("post", "/api/v1/cases/{case_id}/drafts"),
    ("post", "/api/v1/cases/{case_id}/reviews"),
    ("get", "/api/v1/cases/{case_id}/export"),
    ("post", "/api/v1/uploads"),
    ("get", "/api/v1/uploads/{upload_id}"),
    ("post", "/api/v1/uploads/{upload_id}/complete"),
    ("post", "/api/v1/uploads/{upload_id}/abort"),
    ("get", "/api/v1/alerts"),
    ("get", "/api/v1/alerts/stream"),
    ("get", "/api/v1/alerts/{alert_id}"),
    ("post", "/api/v1/alerts/{alert_id}/acknowledge"),
    ("put", "/api/v1/alerts/preferences"),
    ("post", "/api/v1/devices"),
    ("delete", "/api/v1/devices/{device_id}"),
    ("get", "/api/v1/admin/alert-rules"),
    ("put", "/api/v1/admin/alert-rules"),
    ("get", "/api/v1/sources"),
    ("get", "/api/v1/sources/{source_id}/health"),
    ("post", "/api/v1/admin/sources/{source_id}/check"),
    ("get", "/api/v1/source-publications"),
    ("get", "/api/v1/source-artifacts"),
    ("get", "/api/v1/source-artifacts/{artifact_id}"),
    ("get", "/api/v1/source-artifacts/{artifact_id}/integrity"),
    ("get", "/api/v1/source-artifacts/{artifact_id}/preview"),
    ("post", "/api/v1/source-artifacts/{artifact_id}/download-link"),
    ("get", "/api/v1/source-records"),
    ("get", "/api/v1/source-records/{source_record_id}/source-location"),
}
# Recorded in contract/DECISIONS.md: needed by the documented flows but absent from the BSD tables.
ADDED_OPERATIONS = {
    ("get", "/api/v1/ific/analyses"),
    ("get", "/api/v1/ific/analyses/{analysis_id}/findings"),
    ("post", "/api/v1/uploads/{upload_id}/parts"),
    ("get", "/api/v1/source-records/{source_record_id}"),
    ("put", "/api/v1/uploads/{upload_id}/parts/{part_number}"),
    ("get", "/api/v1/source-artifacts/{artifact_id}/content"),
    ("get", "/api/v1/cases/{case_id}/drafts"),
    ("put", "/api/v1/cases/{case_id}/drafts/{draft_id}"),
    ("get", "/api/v1/cases/{case_id}/reviews"),
    ("get", "/api/v1/alerts/preferences"),
    ("get", "/api/v1/finland-relevance/frequency-screen"),
    ("get", "/api/v1/operations/metrics"),
    ("get", "/api/v1/admin/users"),
    ("post", "/api/v1/admin/users"),
    ("get", "/api/v1/admin/users/{user_id}"),
    ("put", "/api/v1/admin/users/{user_id}/roles"),
    ("put", "/api/v1/admin/users/{user_id}/status"),
    ("post", "/api/v1/admin/users/{user_id}/revoke-sessions"),
    ("post", "/api/v1/admin/users/{user_id}/entitlements"),
    ("delete", "/api/v1/admin/users/{user_id}/entitlements/{grant_id}"),
}


def _operations(openapi: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, operation)
        for path, item in openapi["paths"].items()
        for method, operation in item.items()
    ]


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "demo-id", path)


def test_all_documented_routes_exist_and_nothing_else(openapi: dict[str, Any]) -> None:
    found = {(method, path) for method, path, _ in _operations(openapi)}
    assert found == DOCUMENTED_OPERATIONS | ADDED_OPERATIONS


def test_every_operation_declares_a_known_capability(openapi: dict[str, Any]) -> None:
    known = {capability.value for capability in Capability}
    for method, path, operation in _operations(openapi):
        assert operation.get("x-required-capability") in known, f"{method} {path}"
        assert operation.get("x-implementation-status") in {
            "IMPLEMENTED",
            "DESIGNED",
        }, f"{method} {path}"


def test_anonymous_requests_are_denied_everywhere(
    client: TestClient, openapi: dict[str, Any]
) -> None:
    for method, path, _ in _operations(openapi):
        response = client.request(method.upper(), _concrete(path))
        assert response.status_code == 401, f"{method} {path}"
        body = ErrorResponse.model_validate(response.json())
        assert body.error.code is ErrorCode.UNAUTHENTICATED
        assert body.error.request_id == response.headers["X-Request-ID"]


def test_forged_identity_claims_do_not_bypass_denial(secure_client: TestClient) -> None:
    response = secure_client.get(
        "/api/v1/cases",
        params={"tenant_id": "OTHER", "role": "ADMINISTRATOR"},
        headers={"Authorization": "Bearer forged", "X-Role": "ADMINISTRATOR"},
    )
    assert response.status_code == 401


def _all_capabilities_app(app: FastAPI) -> TestClient:
    """A guard that grants everything, to exercise what sits behind authorization."""

    class AllowAll:
        environment = None
        identities = None

        def authorize(self, *_args: Any) -> Principal:
            return Principal("DEMO-USER", "DEMO-TENANT", frozenset(), frozenset(Capability))

    app.state.security = AllowAll()
    return TestClient(app, raise_server_exceptions=False)


def test_routes_never_answer_with_sample_data(app: FastAPI, openapi: dict[str, Any]) -> None:
    client = _all_capabilities_app(app)
    for method, path, operation in _operations(openapi):
        if "requestBody" in operation or operation["x-implementation-status"] != "DESIGNED":
            continue
        headers = {"Idempotency-Key": "demo-key-1"}
        response = client.request(method.upper(), _concrete(path), headers=headers)
        assert response.status_code == 501, f"{method} {path}"
        assert ErrorResponse.model_validate(response.json()).error.code is ErrorCode.NOT_IMPLEMENTED


def test_request_validation_uses_standard_error_without_echoing_input(
    secure_client: TestClient, bearer: Any
) -> None:
    response = secure_client.post(
        "/api/v1/uploads",
        json={"filename_original": "x", "tenant_id": "SECRET-TENANT-VALUE"},
        headers={**bearer("analyst-a"), "Idempotency-Key": "demo-key-1"},
    )
    assert response.status_code == 422
    assert ErrorResponse.model_validate(response.json()).error.code is ErrorCode.VALIDATION_ERROR
    assert "SECRET-TENANT-VALUE" not in response.text


def test_unknown_route_uses_standard_error(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert ErrorResponse.model_validate(response.json()).error.code is ErrorCode.NOT_FOUND


def test_contract_breaking_response_fails_closed(app: FastAPI) -> None:
    """A fabricated number on a method that never ran becomes a 500, not a displayed result."""

    def leaked_secret_value() -> dict[str, Any]:
        return {
            "method_run_id": "DEMO-1",
            "analysis_run_id": "DEMO-RUN",
            "scenario_id": "DEMO-SCENARIO",
            "method_id": "SPACE_PFD_FREE_SPACE",
            "method_version": "DEMO",
            "standard_ref_id": None,
            "role": MethodRole.SCREENING,
            "applicability": MethodApplicability.INSUFFICIENT_DATA,
            "execution_status": MethodExecution.NOT_RUN,
            "reason_codes": [],
            "missing_fields": ["slant_range_m"],
            "metric_kind": None,
            "numeric_value": -123.456,
            "unit": "SECRET-UNIT",
        }

    app.add_api_route("/test/method-run", leaked_secret_value, response_model=MethodRun)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test/method-run")
    assert response.status_code == 500
    assert ErrorResponse.model_validate(response.json()).error.code is ErrorCode.INTERNAL_ERROR
    assert "SECRET-UNIT" not in response.text


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_interactive_docs_are_not_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_credentials_and_storage_locators_are_not_in_the_contract(
    openapi: dict[str, Any],
) -> None:
    forbidden = {
        "auth_secret_ref",
        "object_uri",
        "checkpoint_uri",
        "raw_uri",
        "push_token_encrypted",
    }
    for name, schema in openapi["components"]["schemas"].items():
        assert not forbidden & schema.get("properties", {}).keys(), name
    device = openapi["components"]["schemas"]["Device"]
    assert "push_token" not in device["properties"]


def test_integration_payloads_are_published(openapi: dict[str, Any]) -> None:
    schemas = openapi["components"]["schemas"]
    for name in (
        "PushPayload",
        "DomainEvent",
        "MethodAssessment",
        "MethodCalculation",
        "AgentDraftResponse",
    ):
        assert name in schemas


def test_committed_openapi_matches_the_code() -> None:
    committed = (CONTRACT_DIR / "openapi.json").read_text("utf-8")
    assert committed == render_openapi(), "run: python -m astrasync_api.contract.export"
