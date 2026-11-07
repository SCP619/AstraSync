"""Backup and verified restore (TR-NFR-010, AT-P-08): rows, masters and datasets round-trip,
and tampering, partial targets and non-empty targets are refused."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from test_source_library import (  # noqa: F401 - fixtures used by name.
    Bearer,
    adapters,
    demo_file,
    fake_source,
    ingest,
    registered_sources,
    store,
)

from astrasync_api.backup import BackupError, create, restore, verify_backup
from astrasync_api.db import AuditEvent, build_engine
from astrasync_api.ingest import PipelineContext
from astrasync_api.library_tables import SourceArtifactRow
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.record_store import ParquetRecordStore
from astrasync_api.worker import WorkerRuntime


@pytest.fixture
def populated(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,  # noqa: F811
    adapters: dict[str, Any],  # noqa: F811
    tmp_path: Path,
) -> ParquetRecordStore:
    records = ParquetRecordStore(tmp_path / "records")
    runtime = WorkerRuntime(
        context=PipelineContext(sessions=sessions, store=store, adapters=adapters, records=records),
        clients={},
        worker_id="test",
    )
    headers = bearer("analyst-a")
    ingest(secure_client, runtime, headers, demo_file())
    ingest(secure_client, runtime, headers, demo_file("S-9,433 MHz,2"))
    return records


def targets(tmp_path: Path) -> tuple[Engine, Path, Path]:
    return (
        build_engine(f"sqlite:///{tmp_path / 'restored.db'}"),
        tmp_path / "restored-objects",
        tmp_path / "restored-records",
    )


def test_a_backup_restores_rows_bytes_and_datasets_exactly(
    engine: Engine,
    store: LocalObjectStore,  # noqa: F811
    populated: ParquetRecordStore,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    manifest = create(engine, store._root, populated.root, backup)
    assert manifest["row_counts"]["source_artifacts"] == 2
    assert any(name.startswith("objects/masters/") for name in manifest["files"])
    assert any(name.startswith("records/datasets/") for name in manifest["files"])

    target, objects, records = targets(tmp_path)
    result = restore(target, objects, records, backup)
    assert result["masters_verified"] == 2
    assert result["datasets_verified"] == 2
    with engine.connect() as old, target.connect() as new:
        for model in (SourceArtifactRow, AuditEvent):
            count = select(func.count()).select_from(model)
            assert old.execute(count).scalar() == new.execute(count).scalar()
        hashes = select(SourceArtifactRow.raw_sha256).order_by(SourceArtifactRow.raw_sha256)
        assert old.execute(hashes).all() == new.execute(hashes).all()


def test_a_tampered_backup_is_refused_before_anything_is_written(
    engine: Engine,
    store: LocalObjectStore,  # noqa: F811
    populated: ParquetRecordStore,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    manifest = create(engine, store._root, populated.root, backup)
    master = next(n for n in manifest["files"] if n.startswith("objects/masters/"))
    (backup / master).chmod(0o644)
    (backup / master).write_bytes(b"tampered")
    with pytest.raises(BackupError, match="Digest mismatch"):
        verify_backup(backup)
    target, objects, records = targets(tmp_path)
    with pytest.raises(BackupError):
        restore(target, objects, records, backup)
    assert not objects.exists()


def test_extra_or_missing_files_and_non_empty_targets_are_refused(
    engine: Engine,
    store: LocalObjectStore,  # noqa: F811
    populated: ParquetRecordStore,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    create(engine, store._root, populated.root, backup)
    (backup / "objects" / "extra.bin").write_bytes(b"x")
    with pytest.raises(BackupError, match="differ from its manifest"):
        verify_backup(backup)
    (backup / "objects" / "extra.bin").unlink()

    # Restoring onto the live database (already populated) is refused.
    with pytest.raises(BackupError, match="not empty"):
        restore(engine, tmp_path / "o2", tmp_path / "r2", backup)
    with pytest.raises(BackupError, match="must be empty"):
        create(engine, store._root, populated.root, backup)


def test_a_backup_from_another_revision_is_refused(
    engine: Engine,
    store: LocalObjectStore,  # noqa: F811
    populated: ParquetRecordStore,
    tmp_path: Path,
) -> None:
    backup = tmp_path / "backup"
    create(engine, store._root, populated.root, backup)
    manifest = json.loads((backup / "manifest.json").read_text(encoding="utf-8"))
    manifest["migration_revision"] = "9999"
    (backup / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    target, objects, records = targets(tmp_path)
    with pytest.raises(BackupError, match="revision"):
        restore(target, objects, records, backup)
