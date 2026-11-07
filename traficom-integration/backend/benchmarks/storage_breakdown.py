"""Stage 6: where PostgreSQL storage goes for parsed records.

Generates labelled synthetic rows (astrasync_data.synthetic_scale), runs the real ingest code
(register_bytes, then process_artifact) against a scratch PostgreSQL database, and reports heap,
TOAST, free-space/visibility maps and every index per table, per-column stored sizes, and the
size of the byte-integrity tables. Nothing is estimated: every figure is read from PostgreSQL.

    python benchmarks/storage_breakdown.py --server postgresql://postgres:@127.0.0.1:54194 \
        --rows 50000 --work <scratch dir> --out storage.json

The target database (default bench_storage) is dropped and recreated.
"""

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

import psycopg
from astrasync_data.synthetic_scale import generate

from astrasync_api import admin
from astrasync_api.contract.enums import IssueDomain, JobType, SourceType, UsageClassification
from astrasync_api.db import build_engine, build_session_factory, run_migrations
from astrasync_api.ingest import IncomingBytes, PipelineContext, process_artifact, register_bytes
from astrasync_api.jobs import LANE_INGESTION, enqueue

TENANT = "BENCH-TENANT"
SOURCE = "BENCH-SYNTHETIC"
RECORD_TABLES = (
    "source_record_locations",
    "source_library_search_index",
    "record_quality_findings",
    "reference_station_records",
)
INTEGRITY_TABLES = ("source_artifacts", "artifact_integrity_checks", "job_runs", "audit_events")


def _recreate(server: str, name: str) -> None:
    with psycopg.connect(f"{server}/postgres", autocommit=True) as connection:
        connection.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        connection.execute(f'CREATE DATABASE "{name}"')


def ingest(server: str, database: str, csv: Path, work: Path) -> dict[str, Any]:
    from astrasync_data.challenge_reference import ChallengeReferenceAdapter

    from astrasync_api.objectstore import LocalObjectStore

    engine = build_engine(f"{server.replace('postgresql://', 'postgresql+psycopg://')}/{database}")
    run_migrations(engine)
    sessions = build_session_factory(engine)
    admin.create_tenant(sessions, TENANT, "1")
    admin.register_source(
        sessions,
        tenant_id=TENANT,
        source_id=SOURCE,
        publisher="Synthetic benchmark generator",
        domain=IssueDomain.FINNISH_REFERENCE,
        source_type=SourceType.CHALLENGE_SYNTHETIC_REFERENCE,
        classification=UsageClassification.INTERNAL,
        rights_basis="Generated benchmark data, not real data",
        is_synthetic=True,
    )
    adapter = ChallengeReferenceAdapter()
    store = LocalObjectStore(work / "objects")
    adapters = {adapter.source_type: adapter}
    context = PipelineContext(sessions=sessions, store=store, adapters=adapters)
    staging = store.new_staging_path()
    shutil.copyfile(csv, staging)
    staged = store.hash_file(staging)
    artifact = register_bytes(
        context,
        IncomingBytes(
            tenant_id=TENANT,
            source_id=SOURCE,
            filename_original=csv.name,
            classification=UsageClassification.INTERNAL.value,
            staged=staged,
            expected_size_bytes=staged.size_bytes,
            transport_sha256=None,
            expected_digest=staged.sha256,
            expected_digest_origin="uploader-supplied-manifest",
        ),
    )
    job = enqueue(
        sessions,
        tenant_id=TENANT,
        job_type=JobType.INGEST,
        lane=LANE_INGESTION,
        idempotency_key=f"bench:{artifact.artifact_id}",
        requested_by="storage-breakdown",
        payload={"artifact_id": artifact.artifact_id},
    )
    started = time.perf_counter()
    status = process_artifact(context, job.job_id, artifact.artifact_id)
    seconds = time.perf_counter() - started
    engine.dispose()
    return {"artifact_id": artifact.artifact_id, "status": status.value, "index_seconds": seconds}


def _size(cursor: psycopg.Cursor[Any], sql: str, *params: Any) -> int:
    row = cursor.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def measure(server: str, database: str) -> dict[str, Any]:
    with psycopg.connect(f"{server}/{database}", autocommit=True) as connection:
        connection.execute("VACUUM (ANALYZE)")
        connection.execute("CHECKPOINT")
        cursor = connection.cursor()
        tables: dict[str, Any] = {}
        for table in (*RECORD_TABLES, *INTEGRITY_TABLES):
            rows = _size(cursor, f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed names.
            heap = _size(cursor, "SELECT pg_relation_size(%s::regclass, 'main')", table)
            maps = _size(
                cursor,
                "SELECT pg_relation_size(%s::regclass, 'fsm') "
                "+ pg_relation_size(%s::regclass, 'vm')",
                table,
                table,
            )
            toast = _size(
                cursor,
                "SELECT COALESCE(pg_total_relation_size(NULLIF(reltoastrelid, 0)), 0) "
                "FROM pg_class WHERE oid = %s::regclass",
                table,
            )
            indexes = {
                name: int(size)
                for name, size in cursor.execute(
                    "SELECT indexrelid::regclass::text, pg_relation_size(indexrelid) "
                    "FROM pg_index WHERE indrelid = %s::regclass ORDER BY 2 DESC",
                    (table,),
                )
            }
            total = _size(cursor, "SELECT pg_total_relation_size(%s::regclass)", table)
            tables[table] = {
                "rows": rows,
                "heap_bytes": heap,
                "fsm_vm_bytes": maps,
                "toast_bytes": toast,
                "index_bytes": indexes,
                "total_bytes": total,
                "total_bytes_per_row": round(total / rows, 1) if rows else None,
            }
            # Tuple header (23 B, padded to 24) and line pointer (4 B) per stored row.
            tables[table]["tuple_overhead_bytes"] = rows * 28
            columns = [
                name
                for (name,) in cursor.execute(
                    "SELECT attname FROM pg_attribute WHERE attrelid = %s::regclass "
                    "AND attnum > 0 AND NOT attisdropped ORDER BY attnum",
                    (table,),
                )
            ]
            if rows and table in RECORD_TABLES:
                sums = ", ".join(f'sum(pg_column_size("{c}"))' for c in columns)
                values = cursor.execute(f"SELECT {sums} FROM {table}").fetchone() or ()  # noqa: S608
                pairs = sorted(zip(columns, values, strict=True), key=lambda x: -(x[1] or 0))
                tables[table]["column_bytes"] = {c: int(v or 0) for c, v in pairs}
        repeated = {}
        for column in ("field_aliases", "analysis_eligibility", "parser_version", "schema_version"):
            distinct = _size(
                cursor,
                f"SELECT count(DISTINCT {column}::text) FROM source_record_locations",  # noqa: S608
            )
            repeated[column] = distinct
        search_repeats = {
            column: _size(
                cursor,
                f"SELECT count(DISTINCT {column}) FROM source_library_search_index",  # noqa: S608
            )
            for column in (
                "publisher",
                "filename_original",
                "artifact_id",
                "source_id",
                "tenant_id",
            )
        }
        database_bytes = _size(cursor, "SELECT pg_database_size(current_database())")
        empty_baseline = _size(cursor, "SELECT pg_database_size('template1')")
        wal = _size(cursor, "SELECT sum(size) FROM pg_ls_waldir()")
    return {
        "tables": tables,
        "distinct_values_in_source_record_locations": repeated,
        "distinct_values_in_search_index": search_repeats,
        "database_bytes": database_bytes,
        "template1_bytes": empty_baseline,
        "wal_dir_bytes_server_wide": wal,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True, help="postgresql://user:pass@host:port")
    parser.add_argument("--database", default="bench_storage")
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    csv = args.work / f"storage-{args.rows}.csv"
    with csv.open("w", encoding="utf-8", newline="") as handle:
        summary = generate(handle, rows=args.rows)
    _recreate(args.server, args.database)
    result = {
        "source_bytes": csv.stat().st_size,
        "generated": summary.__dict__,
        "ingest": ingest(args.server, args.database, csv, args.work),
    }
    result.update(measure(args.server, args.database))
    record_total = sum(result["tables"][t]["total_bytes"] for t in RECORD_TABLES)
    result["record_tables_bytes"] = record_total
    result["record_tables_over_source"] = round(record_total / result["source_bytes"], 2)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
