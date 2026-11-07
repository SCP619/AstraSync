"""Traficom allocation table: connector -> discovery -> archive -> parser -> search, end to end.

By default the real client talks to a mock transport serving a three-row excerpt of the real API
response (CC BY 4.0, see astrasync-core-lib/tests/fixtures). Set ASTRASYNC_LIVE_SOURCES=1 to use
the live public endpoint instead; that run is the real-source verification.
"""

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from conftest import TENANT_A
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    _drain_new_check,
    fake_source,
    store,
)

from astrasync_api import admin
from astrasync_api.connectors import traficom_opendata as traficom
from astrasync_api.contract.enums import DiscoveryMode, IssueDomain, SourceType, UsageClassification
from astrasync_api.ingest import PipelineContext
from astrasync_api.library_tables import SourceArtifactRow
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.worker import WorkerRuntime

m4 = pytest.importorskip("astrasync_data.traficom_m4_table")

LIVE = os.environ.get("ASTRASYNC_LIVE_SOURCES") == "1"
EXCERPT = (
    Path(__file__).resolve().parents[3]
    / "astrasync-core-lib"
    / "tests"
    / "fixtures"
    / "traficom_m4_excerpt.json"
)
SOURCE_ID = "SRC-TRAFICOM-M4-TABLE"


def recorded_client() -> traficom.TraficomFrequencyTableClient:
    body = EXCERPT.read_bytes()

    def serve(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"ETag": '"recorded-excerpt"', "Content-Length": str(len(body))},
            stream=httpx.ByteStream(body),
        )

    return traficom.TraficomFrequencyTableClient(
        httpx.Client(transport=httpx.MockTransport(serve), headers=traficom.HEADERS)
    )


@pytest.fixture
def m4_runtime(
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    users: Any,
    record_store: Any,
) -> WorkerRuntime:
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=SOURCE_ID,
        publisher="Finnish Transport and Communications Agency Traficom",
        domain=IssueDomain.FINNISH_REFERENCE,
        source_type=SourceType.M4_ALLOCATION,
        classification=UsageClassification.PUBLIC,
        rights_basis="Public open data, Creative Commons BY 4.0 (attribute Traficom)",
        discovery_mode=DiscoveryMode.API_POLL,
        endpoint_ref="traficom-m4",
        poll_interval_seconds=86_400,
        expected_cadence_seconds=86_400,
    )
    client = traficom.TraficomFrequencyTableClient() if LIVE else recorded_client()
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions,
            store=store,
            adapters={m4.SOURCE_TYPE: m4.TraficomM4TableAdapter()},
            records=record_store,
        ),
        clients={"traficom-m4": client},
        worker_id="test-worker",
    )


def test_table_is_discovered_archived_parsed_and_searchable(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    m4_runtime: WorkerRuntime,
) -> None:
    checked = secure_client.post(
        f"/api/v1/admin/sources/{SOURCE_ID}/check",
        headers={**bearer("admin-a"), "Idempotency-Key": uuid4().hex},
    )
    assert checked.status_code == 202, checked.text
    _drain_new_check(sessions, m4_runtime)

    with sessions() as session:
        artifact = session.scalars(
            select(SourceArtifactRow).where(SourceArtifactRow.source_id == SOURCE_ID)
        ).one()
        artifact_id, status = artifact.artifact_id, artifact.status
    assert status == "INDEXED", status

    headers = bearer("analyst-a")
    report = secure_client.get(
        f"/api/v1/source-artifacts/{artifact_id}/integrity", headers=headers
    ).json()
    parsed = report["row_reconciliation"]["parsed"]
    print("row reconciliation:", report["row_reconciliation"])
    assert report["row_reconciliation"]["rejected"] == 0
    assert parsed == (report["row_reconciliation"]["accepted"])
    if not LIVE:
        assert parsed == 3

    # The Ku-band fixed-satellite downlink row is found by frequency.
    hits = secure_client.get(
        "/api/v1/source-records",
        params={"frequency_start_mhz": 10_800, "frequency_end_mhz": 10_800},
        headers=headers,
    ).json()["items"]
    mine = [hit for hit in hits if hit["source_id"] == SOURCE_ID]
    assert mine, hits
    assert all(hit["frequency_start_mhz"] <= 10_800 <= hit["frequency_end_mhz"] for hit in mine)
