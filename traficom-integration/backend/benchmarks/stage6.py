"""Stage 6 benchmark harness (DATA_PIPELINE_AND_SCALABILITY.md section 6, profiles L1, L2, L5, L6).

Runs the real local stack as separate processes (identity provider, API, worker), against the
database and object store you name, and drives it over HTTP like a client:

    generate  write labelled synthetic scale data (astrasync_data.synthetic_scale)
    run       upload a file in parts, optionally interrupt and resume the upload, optionally kill
              the worker mid-parse and start a new one, then reconcile counts and time queries

Every result is measured, with the hardware recorded. Nothing is extrapolated. Example:

    python benchmarks/stage6.py generate --bytes 4294967296 --out D:/bench/l1.csv
    python benchmarks/stage6.py run --file D:/bench/l1.csv --work D:/bench/l1 \
        --database-url postgresql+psycopg://postgres:@127.0.0.1:54194/astrasync_bench \
        --interrupt-after-parts 3 --kill-worker-after-records 2000000 --out l1.json
"""

import argparse
import base64
import hashlib
import json
import os
import platform
import random
import secrets
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import psutil

BACKEND = Path(__file__).resolve().parents[1]
DEV_STACK = BACKEND / "tests" / "support" / "dev_stack.py"
API = "http://127.0.0.1:8800"
IDP = "http://127.0.0.1:8801"
REDIRECT = "fi.astrasync.app://auth/callback"
SOURCE_ID = "DEMO-SYNTHETIC"
ADAPTER = "astrasync_data.challenge_reference:ChallengeReferenceAdapter"
MIB = 1024 * 1024


# --- Stack ----------------------------------------------------------------------------------------


def _port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.3)
        return probe.connect_ex(("127.0.0.1", port)) == 0


class Stack:
    """The identity provider, API and worker as child processes, with memory sampling."""

    def __init__(self, database_url: str, store: Path, log: Path, *, parse: bool = True) -> None:
        self.env = {
            **os.environ,
            "ASTRASYNC_DEV_DATABASE_URL": database_url,
            "ASTRASYNC_DEV_OBJECT_STORE_PATH": str(store),
            "ASTRASYNC_DEV_MAX_UPLOAD_BYTES": str(12 * 1024**3),
        }
        if parse:
            self.env["ASTRASYNC_DEV_SOURCE_ADAPTERS"] = ADAPTER
        else:
            # Byte path only: transfer, assembly, hashing and archive, with no record parsing.
            self.env.pop("ASTRASYNC_DEV_SOURCE_ADAPTERS", None)
        self.log = log.open("w")
        self.parts: dict[str, subprocess.Popen[bytes]] = {}
        self.peak_rss: dict[str, int] = {}
        self._stop = threading.Event()
        self._sampler = threading.Thread(target=self._sample, daemon=True)

    def start_part(self, name: str) -> None:
        # "worker2" is a second worker process; dev_stack only knows the role, so strip the digits.
        role = name.rstrip("0123456789")
        self.parts[name] = subprocess.Popen(  # noqa: S603
            [sys.executable, str(DEV_STACK), role],
            cwd=BACKEND,
            env=self.env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )

    def start(self) -> None:
        if _port_open(8800) or _port_open(8801):
            raise SystemExit("Ports 8800/8801 are in use: stop the running stack first.")
        self.start_part("idp")
        self.start_part("api")
        for _ in range(240):
            if _port_open(8800) and _port_open(8801):
                break
            time.sleep(0.5)
        else:
            raise SystemExit("The stack did not start; see the log.")
        self.start_part("worker")
        self._sampler.start()

    def kill(self, name: str) -> None:
        process = self.parts[name]
        for child in psutil.Process(process.pid).children(recursive=True):
            child.kill()
        process.kill()
        process.wait()

    def _sample(self) -> None:
        while not self._stop.is_set():
            for name, process in list(self.parts.items()):
                try:
                    # On Windows a venv python.exe is a launcher; the work runs in its child.
                    root = psutil.Process(process.pid)
                    rss = sum(p.memory_info().rss for p in (root, *root.children(recursive=True)))
                except psutil.Error:
                    continue
                key = name.rstrip("0123456789")
                self.peak_rss[key] = max(self.peak_rss.get(key, 0), rss)
            time.sleep(0.5)

    def stop(self) -> None:
        self._stop.set()
        for name in list(self.parts):
            try:
                self.kill(name)
            except (psutil.Error, OSError):
                pass
        self.log.close()


def token(persona: str) -> str:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    approval = httpx.post(
        f"{IDP}/authorize",
        data={
            "subject": persona,
            "redirect_uri": REDIRECT,
            "code_challenge": challenge.rstrip(b"=").decode(),
            "state": "bench",
            "scope": "openid astrasync.api",
        },
        follow_redirects=False,
    )
    code = parse_qs(urlsplit(approval.headers["location"]).query)["code"][0]
    answer = httpx.post(
        f"{IDP}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "client_id": "astrasync-dev-ui",
        },
    )
    return str(answer.json()["access_token"])


class RenewingAuth(httpx.Auth):
    """Signs in again when the short-lived test token expires, then repeats the request once."""

    def __init__(self, persona: str) -> None:
        self.persona = persona
        self.current = token(persona)
        self.renewals = 0

    def auth_flow(self, request: httpx.Request) -> Any:
        request.headers["Authorization"] = f"Bearer {self.current}"
        response = yield request
        if response.status_code == 401:
            self.current = token(self.persona)
            self.renewals += 1
            request.headers["Authorization"] = f"Bearer {self.current}"
            yield request


# --- Upload ---------------------------------------------------------------------------------------


def upload(
    client: httpx.Client, path: Path, interrupt_after: int | None
) -> tuple[str, dict[str, Any]]:
    size = path.stat().st_size
    created = client.post(
        "/api/v1/uploads",
        json={
            "source_id": SOURCE_ID,
            "source_type": "CHALLENGE_SYNTHETIC_REFERENCE",
            "usage_classification": "INTERNAL",
            "filename_original": path.name,
            "expected_size_bytes": size,
        },
        headers={"Idempotency-Key": secrets.token_hex(16)},
    )
    created.raise_for_status()
    session = created.json()
    upload_id, part_size = session["upload_id"], session["part_size_bytes"]
    total_parts = -(-size // part_size)
    started = time.perf_counter()
    sent_first = _send_parts(
        client, path, upload_id, part_size, range(1, total_parts + 1), stop_after=interrupt_after
    )
    stats: dict[str, Any] = {"parts": total_parts, "part_size_bytes": part_size}
    if interrupt_after is not None:
        # A new client asks the server what arrived, and sends only the rest.
        state = client.get(f"/api/v1/uploads/{upload_id}").json()
        have = {p["part_number"] for p in state["parts"] if p["received"]}
        missing = [n for n in range(1, total_parts + 1) if n not in have]
        stats["resume"] = {
            "parts_before_interruption": len(sent_first),
            "parts_reported_by_server": len(have),
            "parts_resent": len(missing),
            "received_bytes_reported": state["received_size_bytes"],
        }
        _send_parts(client, path, upload_id, part_size, missing)
    transfer_seconds = time.perf_counter() - started

    hashing = time.perf_counter()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * MIB):
            digest.update(chunk)
    client_hash_seconds = time.perf_counter() - hashing
    state = client.get(f"/api/v1/uploads/{upload_id}").json()
    parts = [
        {"part_number": p["part_number"], "etag": p["etag"]}
        for p in state["parts"]
        if p["received"]
    ]
    completing = time.perf_counter()
    done = client.post(
        f"/api/v1/uploads/{upload_id}/complete",
        json={
            "parts": sorted(parts, key=lambda p: p["part_number"]),
            "content_sha256": digest.hexdigest(),
        },
        headers={"Idempotency-Key": secrets.token_hex(16)},
    )
    done.raise_for_status()
    stats.update(
        bytes=size,
        sha256=digest.hexdigest(),
        transfer_seconds=round(transfer_seconds, 2),
        transfer_mib_per_s=round(size / MIB / transfer_seconds, 1),
        client_hash_seconds=round(client_hash_seconds, 2),
        complete_call_seconds=round(time.perf_counter() - completing, 3),
    )
    return upload_id, stats


def _send_parts(
    client: httpx.Client,
    path: Path,
    upload_id: str,
    part_size: int,
    numbers: Any,
    stop_after: int | None = None,
) -> list[int]:
    sent: list[int] = []
    with path.open("rb") as handle:
        for number in numbers:
            if stop_after is not None and len(sent) >= stop_after:
                break  # Simulates the client losing its connection.
            handle.seek((number - 1) * part_size)
            body = handle.read(part_size)
            response = client.put(f"/api/v1/uploads/{upload_id}/parts/{number}", content=body)
            response.raise_for_status()
            sent.append(number)
    return sent


# --- Ingest, crash and reconciliation -------------------------------------------------------------


def wait_for_ingest(
    client: httpx.Client,
    stack: Stack,
    upload_id: str,
    kill_after_records: int | None,
    kill_during_verify: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    job_id = client.get(f"/api/v1/uploads/{upload_id}").json()["job_id"]
    samples: list[tuple[float, int]] = []
    crash: dict[str, Any] | None = None
    while True:
        job = client.get(f"/api/v1/jobs/{job_id}").json()
        processed = job.get("processed_records") or 0
        samples.append((time.perf_counter() - started, processed))
        verifying = kill_during_verify and job["status"] in ("VERIFYING", "INTEGRITY_CHECKING")
        due = kill_after_records is not None and processed >= kill_after_records
        if crash is None and (due or verifying):
            stack.kill("worker")
            crash = {
                "killed_in_status": job["status"],
                "killed_at_records": processed,
                "killed_at_s": round(samples[-1][0], 1),
            }
            stack.start_part("worker2")
        if crash is not None and "attempt_after_crash" not in crash and job.get("attempt", 0) > 1:
            crash["attempt_after_crash"] = job["attempt"]
            crash["reclaimed_at_s"] = round(time.perf_counter() - started, 1)
        if job["status"] in ("READY", "FAILED", "QUARANTINED", "PARTIAL", "CANCELLED"):
            samples.append((time.perf_counter() - started, processed))
            break
        time.sleep(1)
    elapsed = time.perf_counter() - started
    parse_window = [s for s in samples if s[1] > 0]
    rate = None
    if len(parse_window) >= 2:
        (t0, r0), (t1, r1) = parse_window[0], parse_window[-1]
        rate = round((r1 - r0) / (t1 - t0)) if t1 > t0 and r1 > r0 else None
    return {
        "final_status": job["status"],
        "attempt": job.get("attempt"),
        "seconds_from_complete_to_final": round(elapsed, 1),
        "processed_records": job.get("processed_records"),
        "records_per_s_while_parsing": rate,
        "crash": crash,
    }


def reconcile(client: httpx.Client, sha256: str, expected_rows: int | None) -> dict[str, Any]:
    artifacts = client.get("/api/v1/source-artifacts", params={"sha256": sha256}).json()["items"]
    if not artifacts:
        return {"artifact": None}
    artifact = artifacts[0]
    report = client.get(f"/api/v1/source-artifacts/{artifact['artifact_id']}/integrity").json()
    rows = report.get("row_reconciliation")
    return {
        "artifact_id": artifact["artifact_id"],
        "status": artifact["status"],
        "server_sha256_matches": artifact.get("raw_sha256") == sha256,
        "row_reconciliation": rows,
        "expected_rows": expected_rows,
        "rows_match": None
        if expected_rows is None or rows is None
        else rows["parsed"] == expected_rows,
    }


# --- Queries --------------------------------------------------------------------------------------


def time_queries(client: httpx.Client, stations: int, count: int, seed: int = 1) -> dict[str, Any]:
    rng = random.Random(seed)  # noqa: S311
    cases = {
        "station_lookup": lambda: client.get(
            "/api/v1/source-records",
            params={"station_number": str(100_000 + rng.randint(1, stations)), "limit": 50},
        ),
        "frequency_window_page": lambda: client.get(
            "/api/v1/source-records",
            params={
                "frequency_start_mhz": (f := rng.uniform(150, 11_000)),
                "frequency_end_mhz": f + 0.05,
                "limit": 50,
            },
        ),
        "text_search_page": lambda: client.get(
            "/api/v1/source-records", params={"query": "F3E", "limit": 50}
        ),
    }
    results: dict[str, Any] = {}
    for name, call in cases.items():
        latencies = []
        for _ in range(count):
            started = time.perf_counter()
            response = call()
            latencies.append((time.perf_counter() - started) * 1000)
            response.raise_for_status()
        latencies.sort()
        results[name] = {
            "n": count,
            "p50_ms": round(statistics.median(latencies), 1),
            "p95_ms": round(latencies[int(0.95 * (count - 1))], 1),
            "max_ms": round(latencies[-1], 1),
        }
    return results


# --- Commands -------------------------------------------------------------------------------------


def hardware() -> dict[str, Any]:
    return {
        "cpu": platform.processor(),
        "logical_cpus": psutil.cpu_count(),
        "ram_gib": round(psutil.virtual_memory().total / 1024**3, 1),
        "os": platform.platform(),
        "python": platform.python_version(),
    }


def command_generate(args: argparse.Namespace) -> None:
    from astrasync_data.synthetic_scale import generate

    started = time.perf_counter()
    with Path(args.out).open("w", encoding="utf-8", newline="") as handle:
        summary = generate(handle, target_bytes=args.bytes, rows=args.rows, seed=args.seed)
    result = {**summary.__dict__, "seconds": round(time.perf_counter() - started, 1)}
    Path(args.out + ".summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


def command_run(args: argparse.Namespace) -> None:
    path = Path(args.file)
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    summary_path = Path(args.file + ".summary.json")
    expected = json.loads(summary_path.read_text())["rows"] if summary_path.exists() else None
    stack = Stack(args.database_url, work / "objects", work / "stack.log", parse=not args.no_parse)
    stack.start()
    result: dict[str, Any] = {"hardware": hardware(), "file": path.name, "expected_rows": expected}
    try:
        auth = RenewingAuth("analyst-a")
        with httpx.Client(base_url=API, auth=auth, timeout=600) as client:
            upload_id, result["upload"] = upload(client, path, args.interrupt_after_parts)
            result["ingest"] = wait_for_ingest(
                client,
                stack,
                upload_id,
                args.kill_worker_after_records,
                kill_during_verify=args.kill_worker_during_verify,
            )
            result["reconciliation"] = reconcile(client, result["upload"]["sha256"], expected)
            if args.queries and not args.no_parse:
                result["queries"] = time_queries(client, expected or 1000, args.queries)
        result["token_renewals"] = auth.renewals
        result["peak_rss_mib"] = {k: round(v / MIB) for k, v in stack.peak_rss.items()}
    finally:
        stack.stop()
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--out", required=True)
    generate.add_argument("--bytes", type=int)
    generate.add_argument("--rows", type=int)
    generate.add_argument("--seed", type=int, default=6)
    generate.set_defaults(handler=command_generate)
    run = sub.add_parser("run")
    run.add_argument("--file", required=True)
    run.add_argument("--work", required=True)
    run.add_argument("--database-url", required=True)
    run.add_argument("--interrupt-after-parts", type=int)
    run.add_argument("--kill-worker-after-records", type=int)
    run.add_argument("--kill-worker-during-verify", action="store_true")
    run.add_argument("--no-parse", action="store_true", help="byte path only, no record parsing")
    run.add_argument("--queries", type=int, default=200)
    run.add_argument("--out", required=True)
    run.set_defaults(handler=command_run)
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
