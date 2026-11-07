"""The Parquet record store (Stage 6): the same API answers as the PostgreSQL index, crash-safe
publication with idempotent retries, fail-closed reads of damaged files, and a sandboxed engine.

These tests always use a Parquet store. ASTRASYNC_TEST_RECORD_STORE=parquet also runs the whole
suite on it.
"""

import dataclasses
import io
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from support.demo_adapter import DemoAdapter
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    adapters,
    artifact_of,
    begin_upload,
    demo_file,
    fake_source,
    ingest,
    registered_sources,
    send_all,
    store,
)

from astrasync_api import ingest as ingest_module
from astrasync_api.ingest import DatasetBuildRefused, PipelineContext, build_record_dataset
from astrasync_api.library_tables import (
    ArtifactIntegrityCheckRow,
    JobRunRow,
    RecordDatasetRow,
    SourceArtifactRow,
)
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.record_store import DatasetDamaged, DatasetWriter, ParquetRecordStore
from astrasync_api.worker import WorkerRuntime, run_one, run_until_idle

challenge = pytest.importorskip("astrasync_data.challenge_reference")
synthetic = pytest.importorskip("astrasync_data.synthetic_scale")


@pytest.fixture
def parquet(tmp_path: Path) -> ParquetRecordStore:
    return ParquetRecordStore(tmp_path / "parquet-records")


@pytest.fixture
def parquet_app(secure_app: FastAPI, parquet: ParquetRecordStore) -> FastAPI:
    secure_app.state.library = dataclasses.replace(secure_app.state.library, records=parquet)
    return secure_app


def worker(
    sessions: sessionmaker[Session],
    objects: LocalObjectStore,
    parsers: dict[str, Any],
    records: ParquetRecordStore | None,
) -> WorkerRuntime:
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=objects, adapters=parsers, records=records
        ),
        clients={},
        worker_id="test-worker",
    )


def synthetic_file(rows: int, seed: int = 11) -> bytes:
    buffer = io.StringIO()
    rates = synthetic.AnomalyRates(missing_tx=0.05, unitless_tx=0.05, negative_agl=0.05)
    synthetic.generate(buffer, rows=rows, seed=seed, rates=rates)
    return buffer.getvalue().encode()


def without_timestamps(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: without_timestamps(v) for k, v in value.items() if k != "generated_at_utc"}
    if isinstance(value, list):
        return [without_timestamps(item) for item in value]
    return value


def api_view(client: TestClient, headers: dict[str, str], artifact_id: str) -> dict[str, Any]:
    """Every record read the API offers: preview pages, searches, details and locations."""

    def pages(path: str, params: dict[str, Any], key: str) -> list[Any]:
        found: list[Any] = []
        cursor = None
        while True:
            response = client.get(
                path, params={**params, **({"cursor": cursor} if cursor else {})}, headers=headers
            )
            assert response.status_code == 200, response.text
            body = response.json()
            found.append(without_timestamps(body))
            cursor = body["next_cursor"]
            if cursor is None:
                return found

    searches = {
        name: pages("/api/v1/source-records", {"limit": 37, **params}, "items")
        for name, params in {
            "all": {},
            "text": {"query": "10001"},
            "station": {"station_number": "100007"},
            "window": {"frequency_start_mhz": 150.0, "frequency_end_mhz": 450.0},
            "open_start": {"frequency_start_mhz": 3000.0},
        }.items()
    }
    ids = [item["source_record_id"] for page in searches["all"] for item in page["items"]]
    details: dict[str, list[Any]] = {}
    for record_id in ids:
        details[record_id] = []
        for suffix in ("", "/source-location"):
            response = client.get(f"/api/v1/source-records/{record_id}{suffix}", headers=headers)
            assert response.status_code == 200, response.text
            details[record_id].append(without_timestamps(response.json()))
    preview = pages(f"/api/v1/source-artifacts/{artifact_id}/preview", {}, "rows")
    return {"searches": searches, "details": details, "preview": preview, "count": len(ids)}


def test_api_responses_match_the_postgresql_index(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    parquet: ParquetRecordStore,
) -> None:
    adapters[DemoAdapter.source_type] = challenge.ChallengeReferenceAdapter()
    library = secure_app.state.library
    secure_app.state.library = dataclasses.replace(library, records=None)
    headers = bearer("analyst-a")
    upload = ingest(
        secure_client, worker(sessions, store, adapters, None), headers, synthetic_file(260)
    )
    artifact_id = artifact_of(secure_client, headers, sessions, upload).artifact_id

    # Build the record dataset of the already indexed artifact. The PostgreSQL rows stay.
    context = PipelineContext(sessions=sessions, store=store, adapters=adapters, records=parquet)
    dataset = build_record_dataset(context, artifact_id)
    assert dataset.record_count == 260
    assert build_record_dataset(context, artifact_id).relative_path == dataset.relative_path
    with sessions() as session:
        checks = session.scalars(
            select(ArtifactIntegrityCheckRow.check_type).where(
                ArtifactIntegrityCheckRow.artifact_id == artifact_id
            )
        ).all()
    assert checks.count("RECORD_DATASET") == 1

    from_index = api_view(secure_client, headers, artifact_id)
    secure_app.state.library = dataclasses.replace(library, records=parquet)
    from_parquet = api_view(secure_client, headers, artifact_id)
    assert from_index["count"] == 260
    text_hits = [item for page in from_index["searches"]["text"] for item in page["items"]]
    assert 0 < len(text_hits) < 260  # The text filter really filtered.
    assert from_index["searches"]["station"][0]["items"]
    assert from_parquet == from_index


def test_a_build_is_refused_when_the_records_would_differ(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    parquet: ParquetRecordStore,
) -> None:
    headers = bearer("analyst-a")
    upload = ingest(secure_client, worker(sessions, store, adapters, None), headers, demo_file())
    artifact_id = artifact_of(secure_client, headers, sessions, upload).artifact_id
    context = PipelineContext(sessions=sessions, store=store, adapters=adapters, records=parquet)
    with sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        recorded = dict(artifact.row_reconciliation)
        artifact.row_reconciliation = {**recorded, "parsed": recorded["parsed"] + 1}
        session.commit()
    with pytest.raises(DatasetBuildRefused, match="differ"):
        build_record_dataset(context, artifact_id)
    with sessions() as session:
        artifact = session.get_one(SourceArtifactRow, artifact_id)
        artifact.row_reconciliation = recorded
        artifact.parser_version = "some-other-parser/9"
        session.commit()
    with pytest.raises(DatasetBuildRefused, match="some-other-parser"):
        build_record_dataset(context, artifact_id)
    with sessions() as session:
        assert session.scalars(select(RecordDatasetRow)).all() == []
    assert list(parquet.root.rglob("*.parquet")) == []


def test_a_dataset_is_invisible_until_its_manifest_commits(
    parquet_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    parquet: ParquetRecordStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_finish = ingest_module._finish_index
    calls = {"n": 0}

    def crash_once(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("power cut after the files were renamed into place")
        return real_finish(*args, **kwargs)

    monkeypatch.setattr(ingest_module, "_finish_index", crash_once)
    runtime = worker(sessions, store, adapters, parquet)
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)
    assert run_one(runtime) is True

    published = list((parquet.root / "datasets").rglob("records.parquet"))
    assert len(published) == 1  # Complete files are in place, but nothing points at them.
    with sessions() as session:
        assert session.scalars(select(RecordDatasetRow)).all() == []
        artifact_id = session.scalars(select(SourceArtifactRow.artifact_id)).one()
        job = session.scalars(select(JobRunRow)).one()
        assert job.status == "RETRYING"
        job.next_attempt_at_utc = datetime.now(UTC)
        session.commit()
    hits = secure_client.get("/api/v1/source-records", headers=headers).json()["items"]
    assert hits == []
    missing = secure_client.get(f"/api/v1/source-records/{artifact_id}-1", headers=headers)
    assert missing.status_code == 404

    run_until_idle(runtime)
    with sessions() as session:
        dataset = session.get_one(RecordDatasetRow, artifact_id)
    remaining = list((parquet.root / "datasets").rglob("records.parquet"))
    assert remaining == [parquet.root / dataset.relative_path / "records.parquet"]
    assert remaining != published  # The orphan was removed, not adopted.
    assert parquet.verify(dataset)
    hits = secure_client.get("/api/v1/source-records", headers=headers).json()["items"]
    assert len(hits) == 2


def test_a_killed_writer_leaves_nothing_readable_and_the_retry_is_clean(
    parquet_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    parquet: ParquetRecordStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DiesOnce(DemoAdapter):
        died = False

        def iter_record_batches(self, artifact_path: Path, *, batch_rows: int) -> Iterator[Any]:
            for batch in super().iter_record_batches(artifact_path, batch_rows=1):
                yield batch
                if not DiesOnce.died:
                    DiesOnce.died = True
                    raise OSError("worker killed mid-write")

    # A killed process runs no cleanup: the partial staging files stay behind.
    monkeypatch.setattr(DatasetWriter, "discard", lambda self: None)
    adapters[DemoAdapter.source_type] = DiesOnce()
    runtime = worker(sessions, store, adapters, parquet)
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)
    assert run_one(runtime) is True
    assert list((parquet.root / "staging").rglob("*.parquet"))
    assert not (parquet.root / "datasets").exists()
    assert secure_client.get("/api/v1/source-records", headers=headers).json()["items"] == []

    with sessions() as session:
        job = session.scalars(select(JobRunRow)).one()
        job.next_attempt_at_utc = datetime.now(UTC)
        session.commit()
    run_until_idle(runtime)
    assert list((parquet.root / "staging").rglob("*")) == []
    with sessions() as session:
        dataset = session.scalars(select(RecordDatasetRow)).one()
        assert dataset.record_count == 2
        assert session.scalars(select(JobRunRow)).one().status == "READY"


def test_a_damaged_dataset_fails_closed(
    parquet_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    parquet: ParquetRecordStore,
) -> None:
    headers = bearer("analyst-a")
    ingest(secure_client, worker(sessions, store, adapters, parquet), headers, demo_file())
    with sessions() as session:
        dataset = session.scalars(select(RecordDatasetRow)).one()
    path = parquet.root / dataset.relative_path / "records.parquet"
    with path.open("ab") as handle:
        handle.write(b"tampered")
    assert not parquet.verify(dataset)
    with pytest.raises(DatasetDamaged):
        parquet.record(dataset, 0)
    response = secure_client.get(f"/api/v1/source-records/{dataset.artifact_id}-0", headers=headers)
    assert response.status_code == 500
    assert "STATION" not in response.text


def test_the_query_engine_is_confined_to_the_store(
    parquet: ParquetRecordStore, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.csv"
    outside.write_text("secret\n1\n", encoding="utf-8")
    connection = parquet._connect()
    with pytest.raises(duckdb.PermissionException):
        connection.execute("SELECT * FROM read_csv(?)", [outside.as_posix()])
    with pytest.raises(duckdb.Error):
        connection.execute("SET enable_external_access = true")
    with pytest.raises(duckdb.Error):
        connection.execute("INSTALL httpfs")
    escaping = RecordDatasetRow(
        artifact_id="a", relative_path="../../outside", records_bytes=1, findings_bytes=1
    )
    with pytest.raises(DatasetDamaged):
        parquet.record(escaping, 0)
