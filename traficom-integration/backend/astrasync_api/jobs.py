"""Durable job queue on the transactional database.

Claiming uses ``FOR UPDATE SKIP LOCKED`` on PostgreSQL, so workers can scale without a separate
broker. Retries are idempotent through keys, and a crashed worker's lease expires.
"""

from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .contract.enums import ErrorCode, JobType, PipelineStatus
from .library_tables import JobRunRow, OutboxEventRow

_TERMINAL = frozenset(
    {
        PipelineStatus.READY,
        PipelineStatus.PARTIAL,
        PipelineStatus.FAILED,
        PipelineStatus.CANCELLED,
        PipelineStatus.QUARANTINED,
    }
)
TERMINAL_VALUES = frozenset(status.value for status in _TERMINAL)
LANE_INGESTION = "ingestion"
LANE_ACQUISITION = "acquisition"
LANE_ANALYSIS = "analysis"
DEFAULT_LEASE = timedelta(minutes=5)
_BASE_BACKOFF_SECONDS = 30


class PermanentJobError(Exception):
    """Retrying cannot help, for example when access was denied or bytes do not match."""

    def __init__(self, code: ErrorCode, detail: str, status: PipelineStatus) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


def utc_now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    sessions: sessionmaker[Session],
    *,
    tenant_id: str,
    job_type: JobType,
    lane: str,
    idempotency_key: str,
    requested_by: str,
    payload: dict[str, Any],
    resource_id: str | None = None,
    max_attempts: int = 3,
) -> JobRunRow:
    """Returns the existing job for a repeated key, so that a retry never creates a duplicate."""
    with sessions() as session:
        row = JobRunRow(
            job_id=uuid4().hex,
            tenant_id=tenant_id,
            job_type=job_type.value,
            lane=lane,
            resource_id=resource_id,
            status=PipelineStatus.QUEUED.value,
            idempotency_key=idempotency_key,
            attempt=0,
            max_attempts=max_attempts,
            next_attempt_at_utc=utc_now(),
            payload=payload,
            requested_by=requested_by,
            created_at_utc=utc_now(),
        )
        session.add(row)
        try:
            session.commit()
            return row
        except IntegrityError:
            session.rollback()
        existing = session.scalar(
            select(JobRunRow).where(
                JobRunRow.tenant_id == tenant_id,
                JobRunRow.job_type == job_type.value,
                JobRunRow.idempotency_key == idempotency_key,
            )
        )
        if existing is None:
            raise RuntimeError("job idempotency conflict without an existing job")
        return existing


def claim(
    sessions: sessionmaker[Session],
    worker_id: str,
    *,
    lanes: Collection[str] = (LANE_INGESTION, LANE_ACQUISITION, LANE_ANALYSIS),
    lease: timedelta = DEFAULT_LEASE,
    now: datetime | None = None,
) -> JobRunRow | None:
    """Claims the oldest runnable job, including one whose worker's lease has expired."""
    now = now or utc_now()
    with sessions() as session:
        row = session.scalar(
            select(JobRunRow)
            .where(
                JobRunRow.lane.in_(list(lanes)),
                JobRunRow.status.not_in(sorted(TERMINAL_VALUES)),
                JobRunRow.next_attempt_at_utc <= now,
                or_(JobRunRow.lease_expires_at_utc.is_(None), JobRunRow.lease_expires_at_utc < now),
            )
            .order_by(JobRunRow.next_attempt_at_utc)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return None
        if row.attempt >= row.max_attempts:
            # The previous worker died on the final attempt, so nothing else will close this.
            row.status = PipelineStatus.FAILED.value
            row.error_code = ErrorCode.INTERNAL_ERROR.value
            row.error_detail = "Worker stopped during the final attempt."
            row.finished_at_utc = now
            row.lease_owner = None
            row.lease_expires_at_utc = None
            session.commit()
            return None
        row.attempt += 1
        row.lease_owner = worker_id
        row.lease_expires_at_utc = now + lease
        row.started_at_utc = row.started_at_utc or now
        session.commit()
        return row


def update_progress(
    sessions: sessionmaker[Session],
    job_id: str,
    *,
    status: PipelineStatus,
    processed_bytes: int | None = None,
    processed_records: int | None = None,
    lease: timedelta = DEFAULT_LEASE,
) -> None:
    """Records actual progress and extends the lease."""
    with sessions() as session:
        row = session.get_one(JobRunRow, job_id)
        row.status = status.value
        row.progress_stage = status.value
        if processed_bytes is not None:
            row.processed_bytes = processed_bytes
        if processed_records is not None:
            row.processed_records = processed_records
        row.lease_expires_at_utc = utc_now() + lease
        session.commit()


def finish(
    sessions: sessionmaker[Session],
    job_id: str,
    status: PipelineStatus,
    *,
    error_code: ErrorCode | None = None,
    detail: str | None = None,
) -> None:
    with sessions() as session:
        row = session.get_one(JobRunRow, job_id)
        row.status = status.value
        row.progress_stage = status.value
        row.error_code = error_code.value if error_code else None
        row.error_detail = detail
        row.finished_at_utc = utc_now()
        row.lease_owner = None
        row.lease_expires_at_utc = None
        session.commit()


def retry_or_fail(sessions: sessionmaker[Session], job_id: str, detail: str) -> PipelineStatus:
    """Exponential backoff, then a terminal failure that keeps its diagnostics."""
    with sessions() as session:
        row = session.get_one(JobRunRow, job_id)
        row.lease_owner = None
        row.lease_expires_at_utc = None
        row.error_detail = detail[:1024]
        if row.attempt >= row.max_attempts:
            row.status = PipelineStatus.FAILED.value
            row.progress_stage = PipelineStatus.FAILED.value
            row.error_code = ErrorCode.INTERNAL_ERROR.value
            row.finished_at_utc = utc_now()
        else:
            delay = _BASE_BACKOFF_SECONDS * 2 ** (row.attempt - 1)
            row.status = PipelineStatus.RETRYING.value
            row.next_attempt_at_utc = utc_now() + timedelta(seconds=delay)
        session.commit()
        return PipelineStatus(row.status)


def emit_event(
    session: Session,
    *,
    tenant_id: str,
    event_kind: str,
    resource_type: str,
    resource_id: str,
    dedupe_key: str,
    correlation_id: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Adds to the caller's transaction. A repeated dedupe key adds nothing."""
    existing = session.scalar(
        select(OutboxEventRow.event_id).where(
            OutboxEventRow.tenant_id == tenant_id, OutboxEventRow.dedupe_key == dedupe_key
        )
    )
    if existing is None:
        session.add(
            OutboxEventRow(
                event_id=uuid4().hex,
                tenant_id=tenant_id,
                event_kind=event_kind,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                dedupe_key=dedupe_key,
                payload=payload or {},
                occurred_at_utc=utc_now(),
            )
        )
