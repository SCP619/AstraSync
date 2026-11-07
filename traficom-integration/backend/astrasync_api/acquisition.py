"""Discovery and authorised download for registered sources.

Connector clients are server code registered by name, so a connector row can never point the
worker at an arbitrary URL. Sources without a permitted automated route stay ``MANUAL_REQUIRED``.
No real ITU or Traficom client exists yet: that needs confirmed access and formats.
"""

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session

from .contract.enums import (
    ArtifactStatus,
    DiscoveryMode,
    DomainEventKind,
    ErrorCode,
    JobType,
    ObservationStatus,
    PipelineStatus,
    SourceHealthStatus,
)
from .contract.interfaces import SourceClient
from .ingest import IncomingBytes, PipelineContext, process_artifact, register_bytes
from .jobs import LANE_ACQUISITION, PermanentJobError, emit_event, enqueue, utc_now
from .library_tables import SourceConnectorRow, SourceObservationRow

SYSTEM_ACTOR = "system:scheduler"
_MAX_DOWNLOAD_BYTES = 64 * 1024**3


class SourceAccessDenied(Exception):
    """The source refused the configured identity. Never retried, and never worked around."""


class SourceUnavailable(Exception):
    """A temporary failure. It says nothing about whether a publication still exists."""


class UnsafeDownload(Exception):
    """A download broke the transfer policy: scheme, host, redirect, size or truncation."""


@dataclass(frozen=True)
class RemotePublication:
    provider_issue_key: str
    filename: str
    provider_version: str | None = None
    published_at_utc: datetime | None = None
    remote_size_bytes: int | None = None
    expected_digest: str | None = None
    expected_digest_origin: str | None = None
    publisher_signed: bool = False


def download_to_file(
    url: str,
    destination: BinaryIO,
    *,
    allowed_hosts: Collection[str],
    client: httpx.Client,
    max_bytes: int = _MAX_DOWNLOAD_BYTES,
) -> int:
    """Streams one allow-listed HTTPS URL to disk. For use by ``SourceClient`` implementations."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in allowed_hosts:
        raise UnsafeDownload("URL is not an allowed HTTPS host")
    written = 0
    # Redirects are refused, so a source cannot steer the worker to an internal address.
    with client.stream("GET", url, follow_redirects=False) as response:
        if response.status_code in (401, 403):
            raise SourceAccessDenied
        if response.is_redirect:
            raise UnsafeDownload("Redirects are not followed")
        if response.status_code != 200:
            raise SourceUnavailable(f"HTTP {response.status_code}")
        declared = response.headers.get("Content-Length")
        for chunk in response.iter_raw():
            written += len(chunk)
            if written > max_bytes:
                raise UnsafeDownload("Download exceeds the size limit")
            destination.write(chunk)
    if declared is not None and int(declared) != written:
        raise UnsafeDownload("Download ended early")
    return written


def request_check(
    sessions: sessionmaker[Session], connector: SourceConnectorRow, requested_by: str
) -> str:
    """One discovery job per minute at most: repeated checks return the same job."""
    bucket = int(utc_now().timestamp()) // 60
    job = enqueue(
        sessions,
        tenant_id=connector.tenant_id,
        job_type=JobType.SOURCE_DISCOVERY,
        lane=LANE_ACQUISITION,
        idempotency_key=f"discover:{connector.source_id}:{bucket}",
        requested_by=requested_by,
        resource_id=connector.source_id,
        payload={"source_id": connector.source_id},
    )
    return job.job_id


def enqueue_due_checks(sessions: sessionmaker[Session]) -> int:
    """Permitted polling only: each connector's own interval, automated modes only."""
    now = utc_now()
    with sessions() as session:
        connectors = session.scalars(
            select(SourceConnectorRow).where(
                SourceConnectorRow.poll_interval_seconds.is_not(None),
                SourceConnectorRow.discovery_mode != DiscoveryMode.MANUAL_TRANSFER.value,
                SourceConnectorRow.status != SourceHealthStatus.DISABLED.value,
                SourceConnectorRow.status != SourceHealthStatus.ACCESS_DENIED.value,
            )
        ).all()
    queued = 0
    for connector in connectors:
        last = connector.last_checked_at_utc
        interval = connector.poll_interval_seconds or 0
        if last is None or (now - last).total_seconds() >= interval:
            request_check(sessions, connector, SYSTEM_ACTOR)
            queued += 1
    return queued


def _record_failure(
    sessions: sessionmaker[Session],
    source_id: str,
    status: SourceHealthStatus,
    code: ErrorCode,
    summary: str,
) -> None:
    now = utc_now()
    with sessions() as session:
        connector = session.get_one(SourceConnectorRow, source_id)
        connector.last_checked_at_utc = now
        connector.status = status.value
        connector.failure_code = code.value
        connector.failure_summary = summary
        emit_event(
            session,
            tenant_id=connector.tenant_id,
            event_kind=DomainEventKind.SOURCE_FAILED.value,
            resource_type="source_connector",
            resource_id=source_id,
            dedupe_key=f"source-failed:{source_id}:{status.value}:{now.date().isoformat()}",
            correlation_id=source_id,
        )
        session.commit()


def discover(
    sessions: sessionmaker[Session], clients: Mapping[str, SourceClient], source_id: str
) -> PipelineStatus:
    with sessions() as session:
        connector = session.get_one(SourceConnectorRow, source_id)
    client = clients.get(connector.endpoint_ref or "")
    if client is None:
        _record_failure(
            sessions,
            source_id,
            SourceHealthStatus.MANUAL_REQUIRED,
            ErrorCode.CONFLICT,
            "No authorised connector client is available. Use a manual import.",
        )
        raise PermanentJobError(
            ErrorCode.CONFLICT, "No connector client is registered.", PipelineStatus.FAILED
        )

    try:
        publications = client.discover()
    except SourceAccessDenied as exc:
        _record_failure(
            sessions,
            source_id,
            SourceHealthStatus.ACCESS_DENIED,
            ErrorCode.SOURCE_RESTRICTED,
            "The source refused the configured access. An operator must review it.",
        )
        raise PermanentJobError(
            ErrorCode.SOURCE_RESTRICTED, "Source access was denied.", PipelineStatus.FAILED
        ) from exc
    except SourceUnavailable as exc:
        # An outage is not a retraction: every known observation is left untouched.
        _record_failure(
            sessions,
            source_id,
            SourceHealthStatus.SOURCE_UNAVAILABLE,
            ErrorCode.SERVICE_UNAVAILABLE,
            "The source could not be reached.",
        )
        raise SourceUnavailable("source unavailable") from exc

    now = utc_now()
    to_acquire: list[str] = []
    with sessions() as session:
        connector = session.get_one(SourceConnectorRow, source_id)
        for publication in publications:
            version_key = publication.provider_version or "-"
            existing = session.scalar(
                select(SourceObservationRow).where(
                    SourceObservationRow.source_id == source_id,
                    SourceObservationRow.provider_issue_key == publication.provider_issue_key,
                    SourceObservationRow.version_key == version_key,
                )
            )
            if existing is not None:
                existing.last_seen_at_utc = now
                existing.observation_status = ObservationStatus.UNCHANGED.value
                continue
            earlier = session.scalar(
                select(SourceObservationRow.observation_id)
                .where(
                    SourceObservationRow.source_id == source_id,
                    SourceObservationRow.provider_issue_key == publication.provider_issue_key,
                )
                .limit(1)
            )
            status = ObservationStatus.REVISED if earlier else ObservationStatus.NEW
            observation_id = uuid4().hex
            session.add(
                SourceObservationRow(
                    observation_id=observation_id,
                    tenant_id=connector.tenant_id,
                    source_id=source_id,
                    provider_issue_key=publication.provider_issue_key,
                    provider_version=publication.provider_version,
                    version_key=version_key,
                    published_at_utc=publication.published_at_utc,
                    first_seen_at_utc=now,
                    last_seen_at_utc=now,
                    remote_size_bytes=publication.remote_size_bytes,
                    observation_status=status.value,
                    usage_classification=connector.usage_classification,
                    is_synthetic=connector.is_synthetic,
                    remote={
                        "filename": publication.filename,
                        "expected_digest": publication.expected_digest,
                        "expected_digest_origin": publication.expected_digest_origin,
                        "publisher_signed": publication.publisher_signed,
                    },
                )
            )
            emit_event(
                session,
                tenant_id=connector.tenant_id,
                event_kind=(
                    DomainEventKind.SOURCE_REVISED
                    if status is ObservationStatus.REVISED
                    else DomainEventKind.SOURCE_PUBLISHED
                ).value,
                resource_type="source_publication",
                resource_id=observation_id,
                dedupe_key=(
                    f"publication:{source_id}:{publication.provider_issue_key}:{version_key}"
                ),
                correlation_id=observation_id,
            )
            to_acquire.append(observation_id)
        connector.last_checked_at_utc = now
        connector.last_success_at_utc = now
        connector.status = SourceHealthStatus.HEALTHY.value
        connector.failure_code = None
        connector.failure_summary = None
        tenant_id = connector.tenant_id
        session.commit()

    for observation_id in to_acquire:
        enqueue(
            sessions,
            tenant_id=tenant_id,
            job_type=JobType.ACQUIRE,
            lane=LANE_ACQUISITION,
            idempotency_key=f"acquire:{observation_id}",
            requested_by=SYSTEM_ACTOR,
            resource_id=observation_id,
            payload={"observation_id": observation_id},
        )
    return PipelineStatus.READY


def acquire(
    context: PipelineContext,
    clients: Mapping[str, SourceClient],
    job_id: str,
    observation_id: str,
) -> PipelineStatus:
    with context.sessions() as session:
        observation = session.get_one(SourceObservationRow, observation_id)
        connector = session.get_one(SourceConnectorRow, observation.source_id)
    client = clients.get(connector.endpoint_ref or "")
    if client is None:
        raise PermanentJobError(
            ErrorCode.CONFLICT, "No connector client is registered.", PipelineStatus.FAILED
        )

    staged_path: Path = context.store.new_staging_path()
    remote = observation.remote
    try:
        with staged_path.open("wb") as destination:
            client.download(
                observation.provider_issue_key, observation.provider_version, destination
            )
    except SourceAccessDenied as exc:
        staged_path.unlink(missing_ok=True)
        _record_failure(
            context.sessions,
            connector.source_id,
            SourceHealthStatus.ACCESS_DENIED,
            ErrorCode.SOURCE_RESTRICTED,
            "The source refused the download. An operator must review it.",
        )
        raise PermanentJobError(
            ErrorCode.SOURCE_RESTRICTED, "Source access was denied.", PipelineStatus.FAILED
        ) from exc
    except (SourceUnavailable, UnsafeDownload, httpx.HTTPError):
        # Incomplete bytes never become a master. The retry starts again from byte zero.
        staged_path.unlink(missing_ok=True)
        raise

    artifact = register_bytes(
        context,
        IncomingBytes(
            tenant_id=connector.tenant_id,
            source_id=connector.source_id,
            filename_original=remote["filename"],
            classification=connector.usage_classification,
            staged=context.store.hash_file(staged_path),
            expected_size_bytes=observation.remote_size_bytes,
            transport_sha256=None,
            expected_digest=remote["expected_digest"],
            expected_digest_origin=remote["expected_digest_origin"],
            publisher_signed=remote["publisher_signed"],
            publication_id=observation_id,
            published_at_utc=observation.published_at_utc,
            first_seen_at_utc=observation.first_seen_at_utc,
        ),
    )
    if artifact.status == ArtifactStatus.QUARANTINED.value:
        raise PermanentJobError(
            ErrorCode.UPLOAD_CHECKSUM_MISMATCH,
            "The downloaded bytes failed verification.",
            PipelineStatus.QUARANTINED,
        )
    return process_artifact(context, job_id, artifact.artifact_id)

