"""Background worker. Run with ``python -m astrasync_api.worker`` (``--once`` drains and exits).

Adapters and connector clients are named in server settings, as ``module:attribute``. Both come
from their owners' packages; this process only orchestrates them.
"""

import argparse
import logging
import os
import socket
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import uuid4

import httpx

from .acquisition import (
    SourceUnavailable,
    UnsafeDownload,
    acquire,
    discover,
    enqueue_due_checks,
)
from .analysis import AnalysisPlugins, run_analysis
from .case_tables import AnalysisRunRow
from .config import Settings, SettingsError, load_named
from .contract.enums import AnalysisStatus, ErrorCode, JobType, PipelineStatus
from .contract.interfaces import CriterionResolver, RFMethod, SourceAdapter, SourceClient
from .db import build_engine, build_session_factory
from .ingest import PipelineContext, process_artifact, process_upload
from .jobs import PermanentJobError, claim, finish, retry_or_fail
from .library_tables import JobRunRow, UploadSessionRow
from .objectstore import LocalObjectStore
from .parser_sandbox import IsolatedAdapter, ParserLimits
from .record_store import ParquetRecordStore

logger = logging.getLogger("astrasync.worker")
_IDLE_SECONDS = 2.0


@dataclass(frozen=True)
class WorkerRuntime:
    context: PipelineContext
    clients: Mapping[str, SourceClient]
    worker_id: str
    analysis: AnalysisPlugins = field(default_factory=AnalysisPlugins)


def _dispatch(runtime: WorkerRuntime, job: JobRunRow) -> PipelineStatus:
    context = runtime.context
    payload = job.payload
    if job.job_type == JobType.INGEST.value:
        if "upload_id" in payload:
            return process_upload(context, job.job_id, payload["upload_id"])
        return process_artifact(context, job.job_id, payload["artifact_id"])
    if job.job_type == JobType.SOURCE_DISCOVERY.value:
        return discover(context.sessions, runtime.clients, payload["source_id"])
    if job.job_type == JobType.RF.value:
        return run_analysis(
            context.sessions, runtime.analysis, job.job_id, payload["analysis_run_id"]
        )
    if job.job_type == JobType.ACQUIRE.value:
        return acquire(context, runtime.clients, job.job_id, payload["observation_id"])
    if job.job_type == JobType.RELEVANCE.value:
        from .ific_pipeline import run_relevance

        return run_relevance(
            context, dict(runtime.analysis.methods), job.job_id, payload["artifact_id"]
        )
    raise PermanentJobError(
        ErrorCode.NOT_IMPLEMENTED, "This job type has no handler.", PipelineStatus.FAILED
    )


def run_one(runtime: WorkerRuntime) -> bool:
    """Runs one job. Returns False when nothing was runnable."""
    sessions = runtime.context.sessions
    job = claim(sessions, runtime.worker_id)
    if job is None:
        return False
    try:
        status = _dispatch(runtime, job)
    except PermanentJobError as exc:
        logger.warning("job_failed job_id=%s code=%s", job.job_id, exc.code.value)
        finish(sessions, job.job_id, exc.status, error_code=exc.code, detail=exc.detail)
        _close_failed_upload(runtime, job, exc.status, exc.code)
    except (SourceUnavailable, UnsafeDownload, httpx.HTTPError, OSError) as exc:
        _retry(runtime, job, type(exc).__name__)
    except Exception as exc:  # noqa: BLE001 - one bad job must not stop the worker.
        logger.exception("job_error job_id=%s", job.job_id)
        _retry(runtime, job, type(exc).__name__)
    else:
        failure = ErrorCode.PARSER_UNAVAILABLE if status is PipelineStatus.PARTIAL else None
        finish(sessions, job.job_id, status, error_code=failure)
    return True


def _retry(runtime: WorkerRuntime, job: JobRunRow, detail: str) -> None:
    status = retry_or_fail(runtime.context.sessions, job.job_id, detail)
    if status is PipelineStatus.FAILED:
        _close_failed_upload(runtime, job, status, ErrorCode.INTERNAL_ERROR)


def _close_failed_upload(
    runtime: WorkerRuntime, job: JobRunRow, status: PipelineStatus, code: ErrorCode
) -> None:
    run_id = job.payload.get("analysis_run_id")
    if run_id is not None:
        with runtime.context.sessions() as session:
            session.get_one(AnalysisRunRow, run_id).analysis_status = AnalysisStatus.FAILED.value
            session.commit()
        return
    upload_id = job.payload.get("upload_id")
    if upload_id is None:
        return
    with runtime.context.sessions() as session:
        upload = session.get_one(UploadSessionRow, upload_id)
        upload.status = status.value
        upload.failure_code = code.value
        session.commit()


def run_until_idle(runtime: WorkerRuntime) -> int:
    count = 0
    while run_one(runtime):
        count += 1
    return count


def load_adapters(
    specs: tuple[str, ...], limits: ParserLimits | None = None
) -> dict[str, SourceAdapter]:
    """With ``limits``, each adapter parses in a separate limited process (``parser_sandbox``)."""
    adapters: dict[str, SourceAdapter] = {}
    for spec in specs:
        adapter = load_named(spec)()
        if not isinstance(adapter, SourceAdapter):
            raise SettingsError(f"{spec} does not implement SourceAdapter")
        adapters[adapter.source_type] = (
            IsolatedAdapter(spec, adapter.source_type, adapter.parser_version, limits)
            if limits is not None
            else adapter
        )
    return adapters


def load_clients(specs: tuple[str, ...]) -> dict[str, SourceClient]:
    clients: dict[str, SourceClient] = {}
    for spec in specs:
        name, _, target = spec.partition("=")
        client = load_named(target)()
        if not isinstance(client, SourceClient):
            raise SettingsError(f"{target} does not implement SourceClient")
        clients[name] = client
    return clients


def load_analysis_plugins(settings: Settings) -> AnalysisPlugins:
    methods: dict[str, RFMethod] = {}
    for spec in settings.rf_methods:
        method = load_named(spec)()
        if not isinstance(method, RFMethod):
            raise SettingsError(f"{spec} does not implement RFMethod")
        methods[method.method_id] = method
    resolver: CriterionResolver | None = None
    if settings.criterion_resolver:
        resolver = load_named(settings.criterion_resolver)()
        if not isinstance(resolver, CriterionResolver):
            raise SettingsError("The criterion resolver does not implement CriterionResolver")
    return AnalysisPlugins(
        methods=methods, criterion_resolver=resolver, build_sha=settings.build_sha
    )


def build_runtime(settings: Settings) -> WorkerRuntime:
    if not settings.database_url or settings.object_store_path is None:
        raise SettingsError("The worker needs a database and an object store")
    return WorkerRuntime(
        context=PipelineContext(
            sessions=build_session_factory(build_engine(settings.database_url)),
            store=LocalObjectStore(settings.object_store_path),
            adapters=load_adapters(
                settings.source_adapters,
                ParserLimits(settings.parser_memory_mb, settings.parser_timeout_seconds)
                if settings.parser_isolation == "process"
                else None,
            ),
            records=(
                ParquetRecordStore(settings.record_store_path)
                if settings.record_store_path is not None
                else None
            ),
        ),
        clients=load_clients(settings.source_clients),
        worker_id=f"{socket.gethostname()}-{uuid4().hex[:8]}",
        analysis=load_analysis_plugins(settings),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="drain the queue, then exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)

    runtime = build_runtime(Settings.from_env(os.environ))
    if args.once:
        run_until_idle(runtime)
        return 0
    while True:
        enqueue_due_checks(runtime.context.sessions)
        if not run_one(runtime):
            time.sleep(_IDLE_SECONDS)


if __name__ == "__main__":
    sys.exit(main())
