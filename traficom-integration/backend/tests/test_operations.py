"""Operational metrics (TR-NFR-004/009) and the liveness/readiness probes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    adapters,
    begin_upload,
    demo_file,
    fake_source,
    ingest,
    registered_sources,
    runtime,
    send_all,
    store,
)

from astrasync_api.contract.models import OperationsMetrics
from astrasync_api.worker import WorkerRuntime


def metrics(client: TestClient, headers: dict[str, str]) -> OperationsMetrics:
    response = client.get("/api/v1/operations/metrics", headers=headers)
    assert response.status_code == 200, response.text
    return OperationsMetrics.model_validate(response.json())


def test_backlog_is_counted_per_lane_and_status_for_the_tenant_only(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,  # noqa: F811
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)
    queued = metrics(secure_client, headers)
    assert sum(q.count for q in queued.queues if q.lane == "ingestion") == 1
    assert all(q.oldest_age_seconds is not None for q in queued.queues)
    other = metrics(secure_client, bearer("analyst-b"))
    assert other.tenant_id != queued.tenant_id
    assert other.queues == []
    ingest(secure_client, runtime, headers, demo_file("S-1,101 MHz,1"))
    assert all(q.lane != "ingestion" for q in metrics(secure_client, headers).queues)
    text = secure_client.get("/api/v1/operations/metrics", headers=headers).text
    assert "S-1" not in text and "upload_id" not in text  # Counts only.


def test_metrics_need_job_read(secure_client: TestClient, bearer: Bearer) -> None:
    response = secure_client.get("/api/v1/operations/metrics", headers=bearer("no-role"))
    assert response.status_code == 403


def test_probes_answer_without_a_token(secure_app: FastAPI, secure_client: TestClient) -> None:
    assert secure_client.get("/healthz").json() == {"status": "ok"}
    ready = secure_client.get("/readyz")
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}


def test_readiness_fails_without_a_database() -> None:
    from astrasync_api.app import create_app
    from astrasync_api.config import Settings

    client = TestClient(create_app(Settings()), raise_server_exceptions=False)
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
