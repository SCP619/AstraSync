"""Versioned backup and verified restore of the database, source masters and record datasets.

    python -m astrasync_api.backup create <empty backup dir>
    python -m astrasync_api.backup restore <backup dir>     # into an empty database and stores
    python -m astrasync_api.backup verify <backup dir>      # checks the backup's own digests

Uses the worker's settings (``ASTRASYNC_DATABASE_URL``, ``ASTRASYNC_OBJECT_STORE_PATH``,
``ASTRASYNC_RECORD_STORE_PATH``). A backup holds:

- ``tables/<table>.jsonl``: every row of every table in the schema, in dependency order;
- ``objects/masters/...``: immutable source masters (staging and quarantine excluded);
- ``records/datasets/...``: published Parquet datasets (staging excluded);
- ``manifest.json``: the migration revision, row counts and the SHA-256 of every file.

Restore refuses a backup whose files do not match the manifest, a target database that already
holds data or a different migration revision, and non-empty target stores. After loading it
re-hashes every master against ``source_artifacts.raw_sha256`` and every dataset against its
manifest, so original bytes and provenance are proven, not assumed (TR-NFR-010, AT-P-08).

A backup contains restricted source content, audit history and encrypted device tokens: store it
with the same access controls and encryption at rest as the live system (TR-SEC-009). This tool
is portable across SQLite and PostgreSQL; for large PostgreSQL deployments, native
``pg_dump``/PITR remains preferable and this tool's verification step still applies.
"""

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, Table, delete, func, insert, inspect, select, text

from . import alert_tables, case_tables, library_tables  # noqa: F401 - registers the tables.
from .config import Settings, SettingsError
from .db import Base, build_engine, build_session_factory, run_migrations
from .library_tables import RecordDatasetRow, SourceArtifactRow
from .objectstore import LocalObjectStore
from .record_store import ParquetRecordStore

FORMAT = "astrasync-backup/1"
_CHUNK = 8 * 1024 * 1024
_BATCH = 1000


class BackupError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _encode(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"$dt": value.astimezone(UTC).isoformat()}
    if isinstance(value, bytes | bytearray | memoryview):
        return {"$b64": base64.b64encode(bytes(value)).decode()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and len(value) == 1:
        if "$dt" in value:
            return datetime.fromisoformat(value["$dt"])
        if "$b64" in value:
            return base64.b64decode(value["$b64"])
    return value


def _tables() -> list[Table]:
    return list(Base.metadata.sorted_tables)


def _revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _copy_tree(source: Path, target: Path, files: dict[str, str], prefix: str) -> None:
    if not source.exists():
        return
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        relative = f"{prefix}/{path.relative_to(source).as_posix()}"
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        files[relative] = _sha256(destination)


def create(
    engine: Engine, objects_root: Path, records_root: Path | None, target: Path
) -> dict[str, Any]:
    if target.exists() and any(target.iterdir()):
        raise BackupError("The backup directory must be empty")
    (target / "tables").mkdir(parents=True)
    files: dict[str, str] = {}
    counts: dict[str, int] = {}
    with engine.connect() as connection, connection.begin():
        # One read transaction, so tables are mutually consistent on PostgreSQL.
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        for table in _tables():
            path = target / "tables" / f"{table.name}.jsonl"
            count = 0
            with path.open("w", encoding="utf-8", newline="\n") as handle:
                order = list(table.primary_key.columns)
                for row in connection.execute(select(table).order_by(*order)).mappings():
                    handle.write(json.dumps({k: _encode(v) for k, v in row.items()}) + "\n")
                    count += 1
            counts[table.name] = count
            files[f"tables/{table.name}.jsonl"] = _sha256(path)
    _copy_tree(objects_root / "masters", target, files, "objects/masters")
    if records_root is not None:
        _copy_tree(records_root / "datasets", target, files, "records/datasets")
    manifest = {
        "format": FORMAT,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "migration_revision": _revision(engine),
        "row_counts": counts,
        "files": files,
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_backup(source: Path) -> dict[str, Any]:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise BackupError("Unknown backup format")
    present = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    present.discard("manifest.json")
    if present != set(manifest["files"]):
        raise BackupError("The backup's files differ from its manifest")
    for relative, digest in manifest["files"].items():
        if _sha256(source / relative) != digest:
            raise BackupError(f"Digest mismatch: {relative}")
    return dict(manifest)


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            yield {k: _decode(v) for k, v in json.loads(line).items()}


def _empty(root: Path | None) -> bool:
    return root is None or not root.exists() or not any(root.rglob("*"))


def restore(
    engine: Engine, objects_root: Path, records_root: Path | None, source: Path
) -> dict[str, Any]:
    manifest = verify_backup(source)
    if not _empty(objects_root / "masters") or not _empty(
        records_root / "datasets" if records_root else None
    ):
        raise BackupError("The target object and record stores must be empty")
    if any(name.startswith("records/") for name in manifest["files"]) and records_root is None:
        raise BackupError("The backup holds record datasets but no record store is configured")
    run_migrations(engine)
    if _revision(engine) != manifest["migration_revision"]:
        raise BackupError("The backup was made at another migration revision")
    with engine.begin() as connection:
        tables = _tables()
        for table in tables:
            # Tenant data must be absent; migration-seeded reference tables (such as roles) are
            # replaced below by the backup's rows, which come from the same revision.
            if "tenant_id" in table.c or table.name in ("tenants", "users"):
                if connection.execute(select(func.count()).select_from(table)).scalar():
                    raise BackupError(f"The target database is not empty ({table.name})")
        for table in reversed(tables):
            connection.execute(delete(table))
        for table in tables:
            batch: list[dict[str, Any]] = []
            for row in _rows(source / "tables" / f"{table.name}.jsonl"):
                batch.append(row)
                if len(batch) >= _BATCH:
                    connection.execute(insert(table), batch)
                    batch = []
            if batch:
                connection.execute(insert(table), batch)
    for relative in manifest["files"]:
        prefix, _, rest = relative.partition("/")
        if prefix == "objects":
            destination = objects_root / rest
        elif prefix == "records" and records_root is not None:
            destination = records_root / rest
        else:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, destination)
    return verify_restored(engine, objects_root, records_root, manifest)


def verify_restored(
    engine: Engine, objects_root: Path, records_root: Path | None, manifest: dict[str, Any]
) -> dict[str, Any]:
    """Row counts, every master's SHA-256 and every dataset's digests, after a restore."""
    with engine.connect() as connection:
        for table in _tables():
            count = connection.execute(select(func.count()).select_from(table)).scalar()
            if count != manifest["row_counts"].get(table.name, 0):
                raise BackupError(f"Row count differs after restore: {table.name}")
    sessions = build_session_factory(engine)
    store = LocalObjectStore(objects_root)
    masters = 0
    with sessions() as session:
        for artifact in session.scalars(select(SourceArtifactRow)):
            if not artifact.object_key.startswith("masters/"):
                continue  # Quarantined bytes are not backed up.
            path = store.local_path(artifact.object_key)
            if not path.exists():
                raise BackupError(f"Master missing after restore: {artifact.artifact_id}")
            if _sha256(path) != artifact.raw_sha256:
                raise BackupError(f"Master hash differs after restore: {artifact.artifact_id}")
            masters += 1
        datasets = 0
        if records_root is not None:
            records = ParquetRecordStore(records_root)
            for dataset in session.scalars(select(RecordDatasetRow)):
                if not records.verify(dataset):
                    raise BackupError(f"Dataset differs after restore: {dataset.artifact_id}")
                datasets += 1
    return {
        "tables": len(manifest["row_counts"]),
        "masters_verified": masters,
        "datasets_verified": datasets,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AstraSync backup and verified restore")
    parser.add_argument("command", choices=("create", "restore", "verify"))
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "verify":
        manifest = verify_backup(args.path)
        print(f"backup ok: {len(manifest['files'])} files")
        return 0
    settings = Settings.from_env(os.environ)
    if not settings.database_url or settings.object_store_path is None:
        raise SettingsError("Backup needs a database and an object store")
    engine = build_engine(settings.database_url)
    if args.command == "create":
        manifest = create(engine, settings.object_store_path, settings.record_store_path, args.path)
        print(f"backup created: {len(manifest['files'])} files")
    else:
        result = restore(engine, settings.object_store_path, settings.record_store_path, args.path)
        print(f"restore verified: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
