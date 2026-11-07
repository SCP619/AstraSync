"""TR-NFR-006: case-list latency on a declared synthetic dataset (target p95 <= 2 s).

Seeds labelled synthetic cases through the real ``cases.upsert_candidate`` into a scratch
PostgreSQL database, then times ``cases.list_cases`` (the function behind ``GET /cases``) for
the API's filters, sorts and cursor pages. Nothing here is real data.

    python benchmarks/case_list.py --server postgresql://postgres:@127.0.0.1:54194 \
        --cases 50000 --out case-list.json
"""

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from astrasync_api import admin, cases
from astrasync_api.authz import ObjectAccessPolicy
from astrasync_api.contract.enums import (
    CaseDomain,
    CaseSort,
    FindingStatus,
    IssueDomain,
    ReviewStatus,
    SourceType,
    UsageClassification,
)
from astrasync_api.contract.models import CaseCandidate
from astrasync_api.contract.permissions import Role
from astrasync_api.db import build_engine, build_session_factory, run_migrations
from astrasync_api.identity import Principal
from astrasync_api.library import LibraryRuntime

sys.path.insert(0, str(Path(__file__).parent))
from storage_breakdown import SOURCE, TENANT, _recreate  # noqa: E402

DATABASE = "bench_cases"


def seed(sessions: Any, count: int, seed_value: int) -> float:
    rng = random.Random(seed_value)  # noqa: S311 - synthetic data.
    started = time.perf_counter()
    for number in range(count):
        start = rng.uniform(30.0, 30_000.0)
        cases.upsert_candidate(
            sessions,
            TENANT,
            CaseCandidate(
                notice_uid=f"SYNTHETIC-UID-{number}",
                notice_id=f"SYNTHETIC-NOTICE-{number:07d}",
                source_id=SOURCE,
                source_issue_id=f"SYNTHETIC-IFIC-{number % 52:03d}",
                administration=rng.choice(("XXA", "XXB", "XXC")),
                domain=rng.choice(("SPACE", "TERRESTRIAL")),
                change_type=rng.choice(("NEW", "MODIFIED", "WITHDRAWN")),
                frequency_start_mhz=start,
                frequency_end_mhz=start + rng.uniform(0.01, 50.0),
                relevance={
                    "label": "FREQUENCY_MATCH",
                    "reason_codes": ["SYNTHETIC_BENCHMARK"],
                    "rule_version": "benchmark",
                    "overlap_start_mhz": start,
                    "overlap_end_mhz": start + 0.01,
                    "frequency_match": True,
                    "service_match": None,
                    "geometry_match": None,
                    "technical_data_ready": False,
                    "criterion_available": False,
                },
                scenario_id=f"SYNTHETIC-SCENARIO-{number}",
                scenario={},
            ),
        )
    return time.perf_counter() - started


def time_cases(
    runtime: LibraryRuntime, sessions: Any, principal: Principal, n: int
) -> dict[str, Any]:
    def run(cursor: str | None = None, **kwargs: Any) -> Any:
        options: dict[str, Any] = {
            "domain": None,
            "source_issue_id": None,
            "change_type": None,
            "finding_status": None,
            "review_status": None,
            "query_text": None,
            "sort": CaseSort.CASE_ID,
            "limit": 50,
            "cursor": cursor,
            **kwargs,
        }
        with sessions() as session:
            return cases.list_cases(runtime, session, principal, **options)

    deep: dict[str, str | None] = {}

    def deep_page() -> Any:
        # Ten cursor pages in, re-read each time from a fixed cursor.
        if "cursor" not in deep:
            page = run(sort=CaseSort.FREQUENCY_START)
            for _ in range(9):
                page = run(cursor=page.next_cursor, sort=CaseSort.FREQUENCY_START)
            deep["cursor"] = page.next_cursor
        return run(cursor=deep["cursor"], sort=CaseSort.FREQUENCY_START)

    scenarios = {
        "default_page": lambda: run(),
        "sort_frequency": lambda: run(sort=CaseSort.FREQUENCY_START),
        "sort_updated": lambda: run(sort=CaseSort.UPDATED_AT),
        "sort_priority": lambda: run(sort=CaseSort.PRIORITY),
        "filter_finding": lambda: run(finding_status=FindingStatus.INSUFFICIENT_DATA),
        "filter_review_and_domain": lambda: run(
            review_status=ReviewStatus.NEW, domain=CaseDomain.SPACE
        ),
        "filter_issue": lambda: run(source_issue_id="SYNTHETIC-IFIC-017"),
        "text_search": lambda: run(query_text="NOTICE-00123"),
        "page_11_by_frequency": deep_page,
    }
    results = {}
    for name, call in scenarios.items():
        call()
        latencies = []
        for _ in range(n):
            started = time.perf_counter()
            call()
            latencies.append((time.perf_counter() - started) * 1000)
        latencies.sort()
        results[name] = {
            "n": n,
            "p50_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(latencies[int(0.95 * (n - 1))], 1),
            "max_ms": round(latencies[-1], 1),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--server", required=True)
    parser.add_argument("--cases", type=int, default=50_000)
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    _recreate(args.server, DATABASE)
    engine = build_engine(
        f"{args.server.replace('postgresql://', 'postgresql+psycopg://')}/{DATABASE}"
    )
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
    seconds = seed(sessions, args.cases, 7)
    runtime = LibraryRuntime(
        policy=ObjectAccessPolicy(sessions),
        identities=None,  # type: ignore[arg-type]
        store=None,
        max_upload_bytes=0,
    )
    principal = Principal(
        user_id="bench",
        tenant_id=TENANT,
        roles=frozenset({Role.ANALYST}),
        capabilities=frozenset(),
    )
    result = {
        "cases": args.cases,
        "seed_seconds": round(seconds, 1),
        "target": "p95 <= 2000 ms (TR-NFR-006)",
        "queries": time_cases(runtime, sessions, principal, args.queries),
    }
    result["all_within_target"] = all(q["p95_ms"] <= 2000 for q in result["queries"].values())
    engine.dispose()
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
