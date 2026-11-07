"""Operational state for TR-NFR-004/009: queue backlog, failures, outbox and record storage.

Everything is scoped to the caller's tenant and reports counts only: no job payloads, file
names or error details. Liveness and readiness probes for orchestration are in ``app.py``.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .contract import CONTRACT_VERSION
from .contract.enums import PipelineStatus
from .contract.models import OperationsMetrics, QueueBacklog, RecordStoreUsage
from .identity import Principal
from .jobs import TERMINAL_VALUES, utc_now
from .library_tables import JobRunRow, OutboxEventRow, RecordDatasetRow


def metrics(
    session: Session, principal: Principal, record_store_enabled: bool
) -> OperationsMetrics:
    now = utc_now()
    tenant = principal.tenant_id
    rows = session.execute(
        select(
            JobRunRow.lane,
            JobRunRow.status,
            func.count(),
            # Keep the column type so the result is a timezone-aware UTC datetime.
            func.min(JobRunRow.created_at_utc, type_=JobRunRow.created_at_utc.type),
        )
        .where(JobRunRow.tenant_id == tenant, JobRunRow.status.not_in(sorted(TERMINAL_VALUES)))
        .group_by(JobRunRow.lane, JobRunRow.status)
        .order_by(JobRunRow.lane, JobRunRow.status)
    ).all()
    queues = [
        QueueBacklog(
            lane=lane,
            status=status,
            count=int(count),
            oldest_age_seconds=max(0.0, (now - oldest).total_seconds()) if oldest else None,
        )
        for lane, status, count, oldest in rows
    ]
    since = now - timedelta(hours=24)
    failed = session.scalar(
        select(func.count()).where(
            JobRunRow.tenant_id == tenant,
            JobRunRow.status == PipelineStatus.FAILED.value,
            JobRunRow.finished_at_utc >= since,
        )
    )
    outbox = session.scalar(
        select(func.count()).where(
            OutboxEventRow.tenant_id == tenant, OutboxEventRow.consumed_at_utc.is_(None)
        )
    )
    datasets, records, stored = session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(RecordDatasetRow.record_count), 0),
            func.coalesce(
                func.sum(RecordDatasetRow.records_bytes + RecordDatasetRow.findings_bytes), 0
            ),
        ).where(RecordDatasetRow.tenant_id == tenant)
    ).one()
    return OperationsMetrics(
        schema_version=CONTRACT_VERSION,
        generated_at_utc=now,
        tenant_id=tenant,
        queues=queues,
        failed_jobs_last_24h=int(failed or 0),
        outbox_pending=int(outbox or 0),
        record_store=RecordStoreUsage(
            enabled=record_store_enabled,
            datasets=int(datasets),
            records=int(records),
            bytes=int(stored),
        ),
    )
