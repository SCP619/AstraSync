"""Stage 6: PostgreSQL record index versus the Parquet/DuckDB record store, on the same rows.

One labelled synthetic file (astrasync_data.synthetic_scale) is indexed twice by the real ingest
code, once into each store, each with its own scratch PostgreSQL database. Then the same API read
functions (library.search_records, get_record, get_preview) and one aggregation run against both.
Reported: storage on disk, indexing throughput, peak resident memory of this process while
indexing, latency percentiles, and whether every answer is identical.

    python benchmarks/record_store_compare.py --server postgresql://postgres:@127.0.0.1:54194 \
        --rows 200000 --work <scratch dir> --out compare.json
"""

import argparse
import base64
import hashlib
import json
import random
import shutil
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any

import psutil
import psycopg
from astrasync_data.challenge_reference import ChallengeReferenceAdapter
from astrasync_data.synthetic_scale import generate
from sqlalchemy import func, select

from astrasync_api import admin, library
from astrasync_api.authz import ObjectAccessPolicy
from astrasync_api.contract.enums import IssueDomain, JobType, SourceType, UsageClassification
from astrasync_api.db import build_engine, build_session_factory, run_migrations
from astrasync_api.identity import Principal
from astrasync_api.ingest import IncomingBytes, PipelineContext, process_artifact, register_bytes
from astrasync_api.jobs import LANE_INGESTION, enqueue
from astrasync_api.library_tables import RecordDatasetRow, SourceSearchRow
from astrasync_api.objectstore import LocalObjectStore
from astrasync_api.record_store import ParquetRecordStore

sys.path.insert(0, str(Path(__file__).parent))
from storage_breakdown import RECORD_TABLES, SOURCE, TENANT, _recreate  # noqa: E402

MIB = 1024 * 1024


class PeakRss:
    def __init__(self) -> None:
        self._process = psutil.Process()
        self.baseline = self._process.memory_info().rss
        self.peak = self.baseline
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.peak = max(self.peak, self._process.memory_info().rss)
            time.sleep(0.05)

    def __enter__(self) -> "PeakRss":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join()


def index(server: str, database: str, csvs: list[Path], work: Path, mode: str) -> dict[str, Any]:
    _recreate(server, database)
    url = f"{server.replace('postgresql://', 'postgresql+psycopg://')}/{database}"
    engine = build_engine(url)
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
    root = work / mode
    shutil.rmtree(root, ignore_errors=True)
    objects = LocalObjectStore(root / "objects")
    records = ParquetRecordStore(root / "records") if mode == "parquet" else None
    adapter = ChallengeReferenceAdapter()
    context = PipelineContext(
        sessions=sessions, store=objects, adapters={adapter.source_type: adapter}, records=records
    )
    artifact_ids: list[str] = []
    seconds = 0.0
    with PeakRss() as rss:
        for csv in csvs:
            staging = objects.new_staging_path()
            shutil.copyfile(csv, staging)
            staged = objects.hash_file(staging)
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
                requested_by="record-store-compare",
                payload={"artifact_id": artifact.artifact_id},
            )
            started = time.perf_counter()
            status = process_artifact(context, job.job_id, artifact.artifact_id)
            seconds += time.perf_counter() - started
            artifact_ids.append(artifact.artifact_id)
    return {
        "sessions": sessions,
        "engine": engine,
        "records": records,
        "artifact_id": artifact_ids[0],
        "artifact_ids": artifact_ids,
        "status": status.value,
        "index_seconds": round(seconds, 2),
        "peak_rss_mib": round(rss.peak / MIB, 1),
        "rss_growth_mib": round((rss.peak - rss.baseline) / MIB, 1),
    }


def storage(server: str, database: str, records: ParquetRecordStore | None) -> dict[str, Any]:
    with psycopg.connect(f"{server}/{database}", autocommit=True) as connection:
        connection.execute("VACUUM (ANALYZE)")
        tables = {
            table: int(
                connection.execute(
                    "SELECT pg_total_relation_size(%s::regclass)", (table,)
                ).fetchone()[0]  # type: ignore[index]
            )
            for table in (*RECORD_TABLES, "record_datasets")
        }
        database_bytes = int(
            connection.execute("SELECT pg_database_size(current_database())").fetchone()[0]  # type: ignore[index]
        )
    files = (
        {
            path.relative_to(records.root).as_posix(): path.stat().st_size
            for path in records.root.rglob("*")
            if path.is_file()
        }
        if records is not None
        else {}
    )
    return {
        "postgresql_record_tables_bytes": tables,
        "postgresql_database_bytes": database_bytes,
        "parquet_files_bytes": files,
        "record_bytes_total": sum(tables.values()) + sum(files.values()),
    }


def _normalized(value: Any, artifact_ids: list[str]) -> str:
    def strip(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                # Cursors are encoded record IDs, which hold the (per-database) artifact ID.
                k: base64.urlsafe_b64decode(v).decode() if k == "next_cursor" and v else strip(v)
                for k, v in item.items()
                if k != "generated_at_utc"
            }
        if isinstance(item, list):
            return [strip(v) for v in item]
        return item

    text = json.dumps(strip(value.model_dump(mode="json")), sort_keys=True)
    for number, artifact_id in enumerate(artifact_ids):
        text = text.replace(artifact_id, f"<artifact-{number}>")
    return text


def _cursor(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode()


def queries(run: dict[str, Any], rows: int, count: int, dump: Path | None = None) -> dict[str, Any]:
    sessions = run["sessions"]
    artifact_id = run["artifact_id"]
    runtime = library.LibraryRuntime(
        policy=ObjectAccessPolicy(sessions),
        identities=None,  # type: ignore[arg-type]
        store=None,
        max_upload_bytes=0,
        records=run["records"],
    )
    principal = Principal(
        user_id="bench", tenant_id=TENANT, roles=frozenset(), capabilities=frozenset()
    )
    rng = random.Random(6)  # noqa: S311 - the same query mix for both stores.

    def search(**kwargs: Any) -> Any:
        with sessions() as session:
            return library.search_records(
                runtime,
                session,
                principal,
                **{
                    "query_text": None,
                    "station_number": None,
                    "frequency_start_mhz": None,
                    "frequency_end_mhz": None,
                    "limit": 50,
                    "cursor": None,
                    **kwargs,
                },
            )

    def detail() -> Any:
        with sessions() as session:
            return library.get_record(
                runtime,
                None,
                session,
                principal,
                f"{artifact_id}-{rng.randrange(rows)}",  # type: ignore[arg-type]
            )

    def preview(cursor: str | None) -> Any:
        with sessions() as session:
            return library.get_preview(
                runtime,
                None,  # type: ignore[arg-type]
                session,
                principal,
                artifact_id,
                page=None,
                table=None,
                row=None,
                cursor=cursor,
            )

    def aggregate() -> Any:
        # Not an API: an analytical query of the kind that moves to DuckDB.
        if run["records"] is None:
            with sessions() as session:
                result = session.execute(
                    select(SourceSearchRow.record_status, func.count())
                    .where(SourceSearchRow.artifact_id == artifact_id)
                    .group_by(SourceSearchRow.record_status)
                    .order_by(SourceSearchRow.record_status)
                ).all()
            return [(status, int(n)) for status, n in result]
        with sessions() as session:
            dataset = session.get_one(RecordDatasetRow, artifact_id)
        rows_ = run["records"]._query(
            "SELECT record_status, count(*) AS n FROM read_parquet($file) "
            "GROUP BY record_status ORDER BY record_status",
            {"file": run["records"]._records_file(dataset)},
        )
        return [(row["record_status"], int(row["n"])) for row in rows_]

    cases = {
        "station_lookup": lambda: search(station_number=str(100_000 + rng.randint(1, rows))),
        "frequency_window_page": lambda: search(
            frequency_start_mhz=(f := rng.uniform(150, 11_000)), frequency_end_mhz=f + 0.05
        ),
        "frequency_wide_page": lambda: search(frequency_start_mhz=150.0, frequency_end_mhz=450.0),
        "text_search_page": lambda: search(
            query_text=str(rng.randint(10_000, 10_000 + rows // 10))
        ),
        "record_detail": detail,
        "preview_first_page": lambda: preview(None),
        "preview_deep_page": lambda: preview(_cursor(str(rng.randrange(rows)))),
        "aggregate_by_status": aggregate,
    }
    results: dict[str, Any] = {}
    for name, call in cases.items():
        call()  # One warm-up call, not timed.
        latencies, digest, answers = [], hashlib.sha256(), []
        for _ in range(count):
            started = time.perf_counter()
            answer = call()
            latencies.append((time.perf_counter() - started) * 1000)
            text = (
                json.dumps(answer)
                if name == "aggregate_by_status"
                else _normalized(answer, run["artifact_ids"])
            )
            digest.update(text.encode())
            answers.append(text)
        if dump is not None:
            dump.mkdir(parents=True, exist_ok=True)
            (dump / f"{name}.jsonl").write_text(chr(10).join(answers), encoding="utf-8")
        latencies.sort()
        results[name] = {
            "n": count,
            "p50_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(latencies[int(0.95 * (count - 1))], 1),
            "max_ms": round(latencies[-1], 1),
            "answers_sha256": digest.hexdigest(),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True, help="postgresql://user:pass@host:port")
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--modes", nargs="+", default=["postgresql", "parquet"])
    parser.add_argument(
        "--artifacts",
        type=int,
        default=1,
        help="split the rows over this many artifacts (answers are compared only for 1, because "
        "result order depends on the per-database artifact IDs)",
    )
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--dump", type=Path, help="write every answer here, per store")
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    csvs = []
    for number in range(args.artifacts):
        csv = args.work / f"compare-{args.rows}-{number}.csv"
        with csv.open("w", encoding="utf-8", newline="") as handle:
            summary = generate(handle, rows=args.rows // args.artifacts, seed=6 + number)
        csvs.append(csv)
    result: dict[str, Any] = {
        "rows": args.rows,
        "artifacts": args.artifacts,
        "source_bytes": sum(path.stat().st_size for path in csvs),
        "generated_last_artifact": summary.__dict__,
    }
    for mode in args.modes:
        database = f"bench_compare_{mode}"
        run = index(args.server, database, csvs, args.work, mode)
        entry = {k: run[k] for k in ("status", "index_seconds", "peak_rss_mib", "rss_growth_mib")}
        entry["records_per_s"] = round(args.rows / run["index_seconds"])
        entry["storage"] = storage(args.server, database, run["records"])
        entry["queries"] = queries(
            run, args.rows // args.artifacts, args.queries, args.dump / mode if args.dump else None
        )
        run["engine"].dispose()
        result[mode] = entry
        print(mode, json.dumps(entry, indent=2), flush=True)
    if {"postgresql", "parquet"} <= set(result):
        pg, pq = result["postgresql"], result["parquet"]
        result["comparison"] = {
            "storage_ratio_postgresql_over_parquet": round(
                pg["storage"]["record_bytes_total"] / pq["storage"]["record_bytes_total"], 1
            ),
            "postgresql_over_source": round(
                pg["storage"]["record_bytes_total"] / result["source_bytes"], 2
            ),
            "parquet_over_source": round(
                pq["storage"]["record_bytes_total"] / result["source_bytes"], 2
            ),
            "index_speedup": round(pg["index_seconds"] / pq["index_seconds"], 2),
            "identical_answers": {
                name: pg["queries"][name]["answers_sha256"] == pq["queries"][name]["answers_sha256"]
                for name in pg["queries"]
            },
        }
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result.get("comparison"), indent=2))


if __name__ == "__main__":
    main()
