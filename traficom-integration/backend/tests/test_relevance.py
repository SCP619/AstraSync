"""Finland relevance, frequency stage (TR-REL-004/005): pure rules, then the API end to end."""

import os
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    _drain_new_check,
    fake_source,
    ingest,
    registered_sources,
    store,
)
from test_traficom_ingest import made_up_workbook, row
from test_traficom_opendata_pipeline import SOURCE_ID as M4_SOURCE
from test_traficom_opendata_pipeline import recorded_client

from astrasync_api import admin, relevance
from astrasync_api.contract.enums import DiscoveryMode, IssueDomain, SourceType, UsageClassification
from astrasync_api.contract.models import FrequencyRelevanceScreen
from astrasync_api.ingest import PipelineContext
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.worker import WorkerRuntime

workbook = pytest.importorskip("astrasync_data.traficom_workbook")
m4 = pytest.importorskip("astrasync_data.traficom_m4_table")

REAL_WORKBOOK = os.environ.get("ASTRASYNC_TRAFICOM_WORKBOOK")


def ref(
    start: float, end: float, kind: str = "M4_ALLOCATION", **kw: Any
) -> relevance.ReferenceInterval:
    values = {
        "source_record_id": "R1",
        "source_id": "S1",
        "artifact_id": "A1",
        "kind": kind,
        "field": "SUB_BAND",
        "basis": "PUBLISHED_SUB_BAND_LIMITS",
        "start_hz": start,
        "end_hz": end,
        "label": None,
        "is_synthetic": False,
        **kw,
    }
    return relevance.ReferenceInterval(**values)


# --- Pure rules ----------------------------------------------------------------------------------


def test_overlap_is_closed_and_edges_touch() -> None:
    assert relevance.overlap(10, 20, 15, 30) == (15, 20)
    assert relevance.overlap(10, 20, 20, 30) == (20, 20)  # Touching edges count.
    assert relevance.overlap(10, 20, 21, 30) is None
    assert relevance.overlap(15, 15, 10, 20) == (15, 15)  # A single frequency inside a band.


def test_a_match_is_a_screening_signal_with_unevaluated_later_stages() -> None:
    gates, matches, truncated = relevance.screen(10.7e9, 10.75e9, [ref(10.7e9, 10.95e9)])
    assert gates.label == "FREQUENCY_MATCH"
    assert gates.frequency_match is True
    assert gates.reason_codes == [
        "M4_ALLOCATION_OVERLAP",
        "SERVICE_NOT_EVALUATED",
        "GEOMETRY_NOT_EVALUATED",
    ]
    # Service, geometry, technical readiness and criteria are not claimed either way.
    assert (gates.service_match, gates.geometry_match, gates.technical_data_ready) == (None,) * 3
    assert gates.criterion_available is None
    assert (gates.overlap_start_mhz, gates.overlap_end_mhz) == (10700.0, 10750.0)
    assert [m.overlap_end_mhz for m in matches] == [10750.0]
    assert truncated is False


def test_no_overlap_says_so_without_claiming_irrelevance_elsewhere() -> None:
    gates, matches, _ = relevance.screen(1e9, 2e9, [ref(3e9, 4e9)])
    assert gates.label == "NO_FREQUENCY_MATCH"
    assert gates.frequency_match is False
    assert "NO_FINNISH_REFERENCE_OVERLAP" in gates.reason_codes
    assert matches == []


def test_station_interval_basis_is_named() -> None:
    both = relevance.station_intervals(
        {"tx_frequency_hz": 160e6, "rx_frequency_hz": 165e6, "channel_bandwidth_hz": 25e3},
        record="R",
        source="S",
        artifact="A",
        label="1001",
        synthetic=True,
    )
    assert [(i.field, i.start_hz, i.end_hz, i.basis) for i in both] == [
        (
            "TX_FREQUENCY",
            160e6 - 12.5e3,
            160e6 + 12.5e3,
            "CENTRE_PLUS_MINUS_HALF_CHANNEL_BANDWIDTH",
        ),
        (
            "RX_FREQUENCY",
            165e6 - 12.5e3,
            165e6 + 12.5e3,
            "CENTRE_PLUS_MINUS_HALF_CHANNEL_BANDWIDTH",
        ),
    ]
    centre_only = relevance.station_intervals(
        {"tx_frequency_hz": 160e6, "rx_frequency_hz": None, "channel_bandwidth_hz": None},
        record="R",
        source="S",
        artifact="A",
        label=None,
        synthetic=True,
    )
    assert [(i.start_hz, i.end_hz, i.basis) for i in centre_only] == [
        (160e6, 160e6, "CENTRE_FREQUENCY_ONLY")
    ]
    # An unknown frequency gives nothing to screen, never a guessed interval.
    assert (
        relevance.station_intervals(
            {"tx_frequency_hz": None, "rx_frequency_hz": None, "channel_bandwidth_hz": 25e3},
            record="R",
            source="S",
            artifact="A",
            label=None,
            synthetic=True,
        )
        == []
    )


def test_matches_are_capped_and_the_cap_is_reported() -> None:
    many = [ref(1e9, 2e9, source_record_id=f"R{n:04d}") for n in range(relevance.MAX_MATCHES + 5)]
    _, matches, truncated = relevance.screen(1.5e9, 1.5e9, many)
    assert len(matches) == relevance.MAX_MATCHES
    assert truncated is True


# --- Through the API -----------------------------------------------------------------------------


@pytest.fixture
def runtime(
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    users: Any,
) -> WorkerRuntime:
    admin.register_source(
        sessions,
        tenant_id="DEMO-TENANT-A",
        source_id=M4_SOURCE,
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
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions,
            store=store,
            adapters={
                m4.SOURCE_TYPE: m4.TraficomM4TableAdapter(),
                workbook.SOURCE_TYPE: workbook.TraficomWorkbookAdapter(),
            },
        ),
        clients={"traficom-m4": recorded_client()},
        worker_id="test-worker",
    )


def load_references(
    client: TestClient, bearer: Bearer, sessions: sessionmaker[Session], runtime: WorkerRuntime
) -> None:
    checked = client.post(
        f"/api/v1/admin/sources/{M4_SOURCE}/check",
        headers={**bearer("admin-a"), "Idempotency-Key": uuid4().hex},
    )
    assert checked.status_code == 202, checked.text
    _drain_new_check(sessions, runtime)
    data = made_up_workbook([row(1001, "10.725 GHz"), row(1002, "87.900 MHz"), row(1003, "")])
    ingest(client, runtime, bearer("analyst-a"), data, filename="frequencies.xlsx")


def screen(client: TestClient, headers: dict[str, str], start: float, end: float) -> Any:
    return client.get(
        "/api/v1/finland-relevance/frequency-screen",
        params={"start_mhz": start, "end_mhz": end},
        headers=headers,
    )


def test_screen_finds_m4_band_and_station_separately(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    load_references(secure_client, bearer, sessions, runtime)
    response = screen(secure_client, bearer("analyst-a"), 10_720, 10_730)
    assert response.status_code == 200, response.text
    result = FrequencyRelevanceScreen.model_validate(response.json())
    kinds = {m.reference_kind for m in result.matches}
    assert kinds == {"M4_ALLOCATION", "SPECIAL_INTEREST_STATION"}
    allocation = next(m for m in result.matches if m.reference_kind == "M4_ALLOCATION")
    assert (allocation.reference_start_mhz, allocation.reference_end_mhz) == (10700.0, 10950.0)
    assert allocation.label is not None and allocation.label.startswith("FIXED SATELLITE")
    assert allocation.is_synthetic is False
    station = next(m for m in result.matches if m.reference_kind == "SPECIAL_INTEREST_STATION")
    assert station.label == "1001"
    assert station.interval_basis == "CENTRE_PLUS_MINUS_HALF_CHANNEL_BANDWIDTH"
    assert station.is_synthetic is True
    assert result.is_synthetic is True  # Any synthetic evidence marks the whole answer.
    assert result.gates.reason_codes[:2] == [
        "M4_ALLOCATION_OVERLAP",
        "SPECIAL_INTEREST_STATION_OVERLAP",
    ]
    assert {s.source_type for s in result.sources_screened} == {
        "M4_ALLOCATION",
        "CHALLENGE_SYNTHETIC_REFERENCE",
    }


def test_a_range_with_no_finnish_reference(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    load_references(secure_client, bearer, sessions, runtime)
    result = screen(secure_client, bearer("analyst-a"), 500, 600).json()
    assert result["gates"]["label"] == "NO_FREQUENCY_MATCH"
    assert result["matches"] == []


def test_another_tenant_sees_nothing_and_is_told_no_reference_data(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    load_references(secure_client, bearer, sessions, runtime)
    result = screen(secure_client, bearer("analyst-b"), 10_720, 10_730).json()
    assert result["matches"] == []
    assert result["sources_screened"] == []
    assert result["gates"]["label"] == "NO_REFERENCE_DATA"
    assert result["gates"]["frequency_match"] is False


def test_requests_are_validated_and_need_sign_in(
    secure_client: TestClient, bearer: Bearer, runtime: WorkerRuntime
) -> None:
    assert screen(secure_client, bearer("analyst-a"), 20, 10).status_code == 422
    assert screen(secure_client, bearer("analyst-a"), -1, 10).status_code == 422
    assert screen(secure_client, {}, 10, 20).status_code == 401
    assert screen(secure_client, bearer("no-roles-a"), 10, 20).status_code == 403


@pytest.mark.skipif(
    not (REAL_WORKBOOK and os.environ.get("ASTRASYNC_LIVE_SOURCES") == "1"),
    reason="needs ASTRASYNC_TRAFICOM_WORKBOOK and ASTRASYNC_LIVE_SOURCES=1",
)
def test_real_references_live_table_and_challenge_workbook(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    from pathlib import Path

    from astrasync_api.connectors.traficom_opendata import TraficomFrequencyTableClient

    runtime.clients["traficom-m4"] = TraficomFrequencyTableClient()
    checked = secure_client.post(
        f"/api/v1/admin/sources/{M4_SOURCE}/check",
        headers={**bearer("admin-a"), "Idempotency-Key": uuid4().hex},
    )
    assert checked.status_code == 202
    _drain_new_check(sessions, runtime)
    assert REAL_WORKBOOK
    data = Path(REAL_WORKBOOK).read_bytes()
    ingest(secure_client, runtime, bearer("analyst-a"), data, filename="frequencies.xlsx")

    for start, end in ((87.9, 87.9), (10_700, 10_950)):
        result = screen(secure_client, bearer("analyst-a"), start, end).json()
        counts: dict[str, int] = {}
        for match in result["matches"]:
            counts[match["reference_kind"]] = counts.get(match["reference_kind"], 0) + 1
        services = sorted(
            {m["label"] for m in result["matches"] if m["reference_kind"] == "M4_ALLOCATION"}
        )
        label, truncated = result["gates"]["label"], result["matches_truncated"]
        print(f"{start}-{end} MHz: {label} {counts} truncated={truncated} M4={services[:6]}")
        assert result["gates"]["frequency_match"] is True
        assert counts.get("M4_ALLOCATION", 0) >= 1
    fm = screen(secure_client, bearer("analyst-a"), 87.9, 87.9).json()
    assert "5931" in {m["label"] for m in fm["matches"]}  # Workbook row 13, 87.900 MHz.
