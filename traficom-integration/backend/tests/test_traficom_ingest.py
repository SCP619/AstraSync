"""The Traficom workbook parser (astrasync-core-lib) through upload, ingest worker and record API.

The made-up workbook runs everywhere. The real challenge workbook is never committed: set
ASTRASYNC_TRAFICOM_WORKBOOK to run the Stage 2 exit test against it (SHA-256 and 874 rows).
"""

import hashlib
import io
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    adapters,
    artifact_of,
    fake_source,
    ingest,
    registered_sources,
    runtime,
    store,
)

from astrasync_api.contract.models import (
    ArtifactIntegrityReport,
    SourceRecordDetail,
    UploadSession,
)
from astrasync_api.worker import WorkerRuntime

workbook = pytest.importorskip("astrasync_data.traficom_workbook")
openpyxl = pytest.importorskip("openpyxl")

REAL_WORKBOOK = os.environ.get("ASTRASYNC_TRAFICOM_WORKBOOK")
PUBLISHED_SHA256 = "bb7f481f085fb6c457efc04b9b6bb8250c42ea81bab4b4a0e518c93834e03c8a"


def made_up_workbook(rows: list[list[Any]]) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = workbook.SHEET
    sheet.append(["Made-up test workbook, not challenge data"])
    for _ in range(9):
        sheet.append([])
    sheet.append(list(workbook.ENGLISH))
    sheet.append(list(workbook.FINNISH))
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def row(station: int, tx: str, agl: int = 30) -> list[Any]:
    return [
        station,
        "FX",
        "25.00000",
        "61.00000",
        50,
        40,
        "KIINTE\u00c4",
        "25 kHz",
        tx,
        "",
        agl,
        90,
        "",
        "F3E",
        "16k",
        90,
        "V",
        5,
        "E",
        "W",
        "",
        "ND",
    ]


@pytest.fixture
def traficom(adapters: dict[str, Any]) -> None:  # noqa: F811
    adapters[workbook.SOURCE_TYPE] = workbook.TraficomWorkbookAdapter()


def upload(client: TestClient, runtime: WorkerRuntime, headers: dict[str, str], data: bytes):  # noqa: F811
    return UploadSession.model_validate(
        ingest(client, runtime, headers, data, filename="frequencies.xlsx")
    )


def test_made_up_workbook_is_indexed_with_flags_and_original_cells(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,  # noqa: F811
    sessions: sessionmaker[Session],
    traficom: None,
) -> None:
    headers = bearer("analyst-a")
    data = made_up_workbook([row(1001, "160.000 MHz"), row(1002, "", agl=-5), row(1001, "26")])
    finished = upload(secure_client, runtime, headers, data)
    artifact = artifact_of(secure_client, headers, sessions, finished.model_dump())
    report = ArtifactIntegrityReport.model_validate(
        secure_client.get(
            f"/api/v1/source-artifacts/{artifact.artifact_id}/integrity", headers=headers
        ).json()
    )
    assert report.row_reconciliation is not None
    assert report.row_reconciliation.parsed == 3
    assert report.row_reconciliation.rejected == 0
    assert artifact.parser_version == workbook.PARSER_VERSION

    hits = secure_client.get(
        "/api/v1/source-records", params={"station_number": "1001"}, headers=headers
    ).json()["items"]
    assert len(hits) == 2  # A repeated station number is two records, not one.
    by_row = {}
    for hit in hits:
        detail = SourceRecordDetail.model_validate(
            secure_client.get(
                f"/api/v1/source-records/{hit['source_record_id']}", headers=headers
            ).json()
        )
        by_row[detail.location.source_row_or_key] = detail
    clean, unitless = by_row["13"], by_row["15"]
    assert clean.reference_station is not None
    assert clean.reference_station.tx_frequency_hz == pytest.approx(160e6)
    assert clean.reference_station.is_synthetic is True
    assert unitless.raw_fields["tx_frequency"] == "26"
    assert unitless.reference_station is not None
    assert unitless.reference_station.tx_frequency_hz is None
    assert "UNIT_UNSPECIFIED" in {f.rule_id for f in unitless.quality_findings}
    assert unitless.location.raw_sha256 == hashlib.sha256(data).hexdigest()


@pytest.mark.skipif(not REAL_WORKBOOK, reason="ASTRASYNC_TRAFICOM_WORKBOOK not set")
def test_stage2_exit_real_workbook_hash_and_874_rows(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,  # noqa: F811
    sessions: sessionmaker[Session],
    traficom: None,
) -> None:
    assert REAL_WORKBOOK
    data = Path(REAL_WORKBOOK).read_bytes()
    assert hashlib.sha256(data).hexdigest() == PUBLISHED_SHA256
    headers = bearer("analyst-a")
    finished = upload(secure_client, runtime, headers, data)
    assert finished.content_sha256 == PUBLISHED_SHA256
    artifact = artifact_of(secure_client, headers, sessions, finished.model_dump())
    report = ArtifactIntegrityReport.model_validate(
        secure_client.get(
            f"/api/v1/source-artifacts/{artifact.artifact_id}/integrity", headers=headers
        ).json()
    )
    assert report.row_reconciliation is not None
    reconciliation = report.row_reconciliation.model_dump()
    print("row reconciliation:", reconciliation)
    assert reconciliation["parsed"] == 874
    assert reconciliation["rejected"] == 0
    hit = secure_client.get(
        "/api/v1/source-records", params={"station_number": "362450"}, headers=headers
    ).json()["items"][0]
    detail = SourceRecordDetail.model_validate(
        secure_client.get(
            f"/api/v1/source-records/{hit['source_record_id']}", headers=headers
        ).json()
    )
    assert detail.location.source_row_or_key == "108"
    assert detail.raw_fields["antenna_height_agl_m"] == "-28"
    assert "INVALID_OR_UNREALISTIC_HEIGHT" in {f.rule_id for f in detail.quality_findings}
