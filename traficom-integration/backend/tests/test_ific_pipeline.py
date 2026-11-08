"""IFIC issue pipeline (G27): index -> RELEVANCE job -> stored findings -> cases -> read API.

Synthetic records in the real parsers' shape (``norm.*`` fields), so no ITU file is needed. The
analysis itself is ``astrasync_data.ific_analysis``; real-data checks live in astrasync-core.
"""

import gzip
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import TENANT_A, TENANT_B, Users
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from astrasync_api import admin
from astrasync_api.analysis import AnalysisPlugins
from astrasync_api.case_tables import CaseRow, EvidenceLinkRow
from astrasync_api.contract.enums import IssueDomain, JobType, SourceType, UsageClassification
from astrasync_api.ific_tables import IficAnalysisRow
from astrasync_api.ingest import IncomingBytes, PipelineContext, register_bytes
from astrasync_api.jobs import LANE_INGESTION, enqueue
from astrasync_api.library_tables import JobRunRow
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.worker import WorkerRuntime, run_until_idle

astrasync_physics = pytest.importorskip("astrasync_physics.terrestrial_p1546")

ISSUE = "ITU-TERR"
M4 = "M4-TABLE"
STATIONS = "STATIONS"
OTHER = "ITU-TERR-B"


def _norm(fields: dict[str, Any]) -> dict[str, str | None]:
    return {
        f"norm.{k}": None if v is None else v if isinstance(v, str) else json.dumps(v)
        for k, v in fields.items()
    }


def _record(**over: Any) -> dict[str, Any]:
    base = {
        "source_table_or_sheet": "fxm_terra",
        "source_row_or_key": "1",
        "source_page": None,
        "notice_id": "1",
        "issue_key": "3076",
        "station_number": None,
        "network_id": None,
        "administration": "RUS",
        "frequency_start_mhz": 449.99,
        "frequency_end_mhz": 450.01,
        "record_status": "VALID",
        "schema_version": "test",
        "raw_fields": {},
        "field_aliases": {},
        "analysis_eligibility": {},
        "quality_findings": [],
        "reference_station": None,
    }
    base.update(over)
    return base


def _notice(key: str, lat: float, lon: float, intent: str = "ADD") -> dict[str, Any]:
    fields = {
        "role": "NOTICE",
        "intent": intent,
        "assignment_id": f"A{key}",
        "station_class": "FB",
        "is_land_mobile": True,
        "assigned_frequency_mhz": 450.0,
        "bandwidth_khz": 20.0,
        "site_name": f"SITE {key}",
        "site_country": "RUS",
        "latitude_deg": lat,
        "longitude_deg": lon,
        "radiated_power_dbw": 20.0,
        "radiated_power_type": "ERP",
        "antenna_height_agl_m": 40.0,
        "publications": ["NTFD_RR:1"],
        "targets": [],
    }
    return _record(source_row_or_key=key, notice_id=key, raw_fields=_norm(fields))


class _Fixed:
    def __init__(self, source_type: str, records: list[dict[str, Any]]) -> None:
        self.source_type = source_type
        self.parser_version = "test/1"
        self._records = records

    def iter_record_batches(self, path: Path, *, batch_rows: int) -> Iterator[list[dict[str, Any]]]:
        yield self._records


@pytest.fixture
def ific_runtime(
    sessions: sessionmaker[Session], secure_app: FastAPI, record_store: Any, users: Users
) -> WorkerRuntime:
    terrestrial = [
        _notice("100", 60.70, 28.75),  # Near Vyborg, about 20 km from Finland.
        _notice("200", 55.75, 37.62),  # Moscow, far from Finland.
    ]
    m4 = [
        _record(
            source_table_or_sheet="Taajuusjakotaulukko",
            source_row_or_key="7",
            notice_id=None,
            administration="FIN",
            frequency_start_mhz=440.0,
            frequency_end_mhz=470.0,
            raw_fields={
                "Services_in_Finland": "FIXED, MOBILE",
                "Sub_band_usage": "PMR",
                "Class_of_station": "Base station (FB)",
            },
        )
    ]
    station = {
        "station_number_raw": "S1",
        "licence_class_code": None,
        "longitude_deg": 27.0,
        "latitude_deg": 60.6,
        "ground_elevation_m": None,
        "mast_height_m": None,
        "antenna_height_agl_m": 20.0,
        "antenna_height_asl_m": None,
        "antenna_gain_db": None,
        "tx_frequency_hz": 450.0e6,
        "rx_frequency_hz": None,
        "channel_bandwidth_hz": 25000.0,
        "emission_bandwidth_hz": None,
        "polarization_code": None,
        "radiation_power_value": None,
        "radiation_power_unit": None,
        "radiation_power_itu_code_raw": None,
        "transmission_line_db": None,
        "directivity_code": None,
    }
    stations = [
        _record(
            source_table_or_sheet="Frequencies of interest",
            source_row_or_key="2",
            notice_id=None,
            administration="FIN",
            frequency_start_mhz=450.0,
            frequency_end_mhz=450.0,
            reference_station=station,
        )
    ]
    adapters = {
        SourceType.TERRESTRIAL_IFIC.value: _Fixed(SourceType.TERRESTRIAL_IFIC.value, terrestrial),
        SourceType.M4_ALLOCATION.value: _Fixed(SourceType.M4_ALLOCATION.value, m4),
        SourceType.FINLAND_FREQUENCY_INTEREST.value: _Fixed(
            SourceType.FINLAND_FREQUENCY_INTEREST.value, stations
        ),
    }
    for source_id, kind, tenant in (
        (ISSUE, SourceType.TERRESTRIAL_IFIC, TENANT_A),
        (M4, SourceType.M4_ALLOCATION, TENANT_A),
        (STATIONS, SourceType.FINLAND_FREQUENCY_INTEREST, TENANT_A),
        (OTHER, SourceType.TERRESTRIAL_IFIC, TENANT_B),
    ):
        admin.register_source(
            sessions,
            tenant_id=tenant,
            source_id=source_id,
            publisher="Test",
            domain=IssueDomain.TERRESTRIAL,
            source_type=kind,
            classification=UsageClassification.PUBLIC,
            rights_basis="Test data",
        )
    store: LocalObjectStore = secure_app.state.library.store
    context = PipelineContext(
        sessions=sessions, store=store, adapters=adapters, records=record_store
    )
    method = astrasync_physics.TerrestrialP1546()
    return WorkerRuntime(
        context=context,
        clients={},
        worker_id="ific-test",
        analysis=AnalysisPlugins(methods={method.method_id: method}),
    )


def _stage_bytes(store: Any, data: bytes) -> Any:
    staged = store.new_staging_path()
    staged.write_bytes(data)
    return store.hash_file(staged)


def _ingest(runtime: WorkerRuntime, source_id: str, tenant: str, name: str, data: bytes) -> str:
    context = runtime.context
    artifact = register_bytes(
        context,
        IncomingBytes(
            tenant_id=tenant,
            source_id=source_id,
            filename_original=name,
            classification="PUBLIC",
            staged=_stage_bytes(context.store, data),
            expected_size_bytes=len(data),
            transport_sha256=None,
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_digest_origin="uploader-supplied-manifest",
        ),
    )
    enqueue(
        context.sessions,
        tenant_id=tenant,
        job_type=JobType.INGEST,
        lane=LANE_INGESTION,
        idempotency_key=f"t:{artifact.artifact_id}",
        requested_by="test",
        payload={"artifact_id": artifact.artifact_id},
    )
    run_until_idle(runtime)
    return artifact.artifact_id


def test_an_indexed_issue_is_analysed_into_findings_and_cases(
    ific_runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    secure_client: TestClient,
    bearer: Any,
) -> None:
    _ingest(ific_runtime, M4, TENANT_A, "m4.json", b"m4")
    _ingest(ific_runtime, STATIONS, TENANT_A, "stations.xlsx", b"stations")
    artifact = _ingest(ific_runtime, ISSUE, TENANT_A, "brific3076.zip", b"issue")
    with sessions() as session:
        jobs = session.scalars(
            select(JobRunRow).where(JobRunRow.job_type == JobType.RELEVANCE.value)
        ).all()
        assert [j.status for j in jobs] == ["READY"]  # Only the IFIC artifact queues one.
        row = session.scalars(select(IficAnalysisRow)).one()
        assert row.artifact_id == artifact and row.findings_count == 2
        cases = session.scalars(select(CaseRow)).all()
        evidence = session.scalars(select(EvidenceLinkRow)).all()
    # The near notice overlaps a special-interest frequency, is ~20 km away and has a P.1546
    # result: a case. The Moscow notice stays a low-priority finding without a case.
    assert row.cases_created == 1
    [case] = cases
    assert case.notice_id == "100" and case.domain == "TERRESTRIAL"
    assert case.finding_status == "INSUFFICIENT_DATA"  # Never a regulatory outcome.
    assert case.scenario["terrestrial_p1546"]["frequency_mhz"] == 450.0
    assert any(e.entity_id == f"{artifact}-0" for e in evidence)

    with ific_runtime.context.store.open_read(row.findings_object_key) as handle:
        payload = gzip.decompress(handle.read())
    assert hashlib.sha256(payload).hexdigest() == row.findings_sha256
    findings = json.loads(payload)["findings"]
    near = findings[0]
    assert near["notice_id"] == "100"
    assert near["stage_a_frequency"]["status"] == "MATCH"
    assert near["stage_b_service"]["finnish_mobile_allocation"] is True
    assert near["calculations"][0]["method_id"] == "TERR_P1546"
    assert near["regulatory_finding"].startswith("NOT_EVALUATED")

    listed = secure_client.get("/api/v1/ific/analyses", headers=bearer("analyst-a"))
    assert listed.status_code == 200, listed.text
    [analysis] = listed.json()["items"]
    page = secure_client.get(
        f"/api/v1/ific/analyses/{analysis['analysis_id']}/findings?tier=HIGH",
        headers=bearer("analyst-a"),
    )
    assert page.status_code == 200, page.text
    assert [f["notice_id"] for f in page.json()["items"]] == ["100"]
    assert page.json()["items"][0]["rank"] == 1


def test_analyses_respect_tenants_and_roles(
    ific_runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    secure_client: TestClient,
    bearer: Any,
) -> None:
    _ingest(ific_runtime, ISSUE, TENANT_A, "brific3076.zip", b"issue")
    with sessions() as session:
        analysis_id = session.scalars(select(IficAnalysisRow)).one().analysis_id
    path = f"/api/v1/ific/analyses/{analysis_id}/findings"
    assert secure_client.get(path, headers=bearer("analyst-b")).status_code == 404
    assert (
        secure_client.get("/api/v1/ific/analyses", headers=bearer("analyst-b")).json()["items"]
        == []
    )
    # Real (non-synthetic) data is hidden from the demo viewer; administrators lack SOURCE_READ.
    assert secure_client.get(path, headers=bearer("demo-a")).status_code in (403, 404)
    assert secure_client.get(path, headers=bearer("admin-a")).status_code == 403
    assert secure_client.get(path).status_code == 401


def test_a_rerun_does_not_duplicate_the_analysis(
    ific_runtime: WorkerRuntime, sessions: sessionmaker[Session]
) -> None:
    from astrasync_api.ific_pipeline import enqueue_relevance, run_relevance

    artifact = _ingest(ific_runtime, ISSUE, TENANT_A, "brific3076.zip", b"issue")
    enqueue_relevance(sessions, TENANT_A, artifact, "test")
    run_relevance(ific_runtime.context, dict(ific_runtime.analysis.methods), "job", artifact)
    with sessions() as session:
        assert len(session.scalars(select(IficAnalysisRow)).all()) == 1


def test_a_restricted_reference_restricts_the_analysis(
    ific_runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    secure_client: TestClient,
    bearer: Any,
    users: Users,
) -> None:
    from astrasync_api.db import ResourceEntitlement
    from astrasync_api.library_tables import SourceConnectorRow

    with sessions() as session:
        session.get_one(SourceConnectorRow, STATIONS).usage_classification = "RESTRICTED"
        session.commit()
    _ingest(ific_runtime, STATIONS, TENANT_A, "stations.xlsx", b"stations")
    _ingest(ific_runtime, ISSUE, TENANT_A, "brific3076.zip", b"issue")
    reviewer = bearer("reviewer-a")
    assert secure_client.get("/api/v1/ific/analyses", headers=reviewer).json()["items"] == []
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id="g-stations",
                subject=users.ids["reviewer-a"],
                tenant_id=TENANT_A,
                object_type="source",
                object_id=STATIONS,
                classification="RESTRICTED",
                rights=["READ"],
            )
        )
        session.commit()
    assert len(secure_client.get("/api/v1/ific/analyses", headers=reviewer).json()["items"]) == 1
