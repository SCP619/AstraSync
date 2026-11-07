"""IPD stage 2: uploads, immutable masters, integrity, indexed preview and access control."""

import hashlib
import io
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from conftest import TENANT_A, TENANT_B, Users, oidc_settings
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from support.demo_adapter import FORMAT_HEADER, DemoAdapter

from astrasync_api import admin, jobs
from astrasync_api.acquisition import (
    RemotePublication,
    SourceAccessDenied,
    SourceUnavailable,
    UnsafeDownload,
    download_to_file,
    enqueue_due_checks,
)
from astrasync_api.config import Settings, SettingsError
from astrasync_api.contract.enums import (
    DiscoveryMode,
    Environment,
    IssueDomain,
    JobType,
    PipelineStatus,
    SourceType,
    UsageClassification,
)
from astrasync_api.contract.models import (
    ArtifactIntegrityReport,
    JobRun,
    SourceArtifactDetail,
    SourceHealth,
    SourcePreview,
    SourceRecordDetail,
    UploadSession,
)
from astrasync_api.db import AuditEvent, ResourceEntitlement
from astrasync_api.ingest import PipelineContext
from astrasync_api.library_tables import (
    JobRunRow,
    OutboxEventRow,
    SourceConnectorRow,
    SourceRecordLocationRow,
    UploadSessionRow,
)
from astrasync_api.objectstore import LocalObjectStore, ObjectKeyError
from astrasync_api.worker import WorkerRuntime, run_one, run_until_idle

Bearer = Callable[..., dict[str, str]]
SYNTHETIC = "SRC-SYNTHETIC"
RESTRICTED = "SRC-RESTRICTED"
OTHER_TENANT = "SRC-OTHER-TENANT"
REAL_INTERNAL = "SRC-REAL-INTERNAL"
AUTOMATED = "SRC-AUTOMATED"


def demo_file(*rows: str) -> bytes:
    body = rows or ("STATION-1,100.5 MHz,10", "STATION-2,99,20")
    return ("\n".join((FORMAT_HEADER, *body)) + "\n").encode()


@dataclass
class FakeSource:
    publications: list[RemotePublication] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    discover_error: Exception | None = None
    download_error: Exception | None = None
    downloads: int = 0

    def discover(self) -> list[RemotePublication]:
        if self.discover_error:
            raise self.discover_error
        return self.publications

    def download(self, key: str, version: str | None, destination: Any) -> None:
        self.downloads += 1
        if self.download_error:
            raise self.download_error
        destination.write(self.files[f"{key}:{version}"])


@pytest.fixture
def fake_source() -> FakeSource:
    return FakeSource()


@pytest.fixture
def adapters() -> dict[str, Any]:
    return {DemoAdapter.source_type: DemoAdapter()}


@pytest.fixture
def store(secure_app: FastAPI) -> LocalObjectStore:
    return secure_app.state.library.store


@pytest.fixture
def runtime(
    sessions: sessionmaker[Session],
    store: LocalObjectStore,
    adapters: dict[str, Any],
    fake_source: FakeSource,
) -> WorkerRuntime:
    return WorkerRuntime(
        context=PipelineContext(sessions=sessions, store=store, adapters=adapters),
        clients={"fake": fake_source},
        worker_id="test-worker",
    )


@pytest.fixture(autouse=True)
def registered_sources(request: pytest.FixtureRequest) -> None:
    if "users" not in request.fixturenames:
        return
    request.getfixturevalue("users")
    sessions = request.getfixturevalue("sessions")
    common: dict[str, Any] = {
        "publisher": "Demo publisher",
        "domain": IssueDomain.FINNISH_REFERENCE,
        "source_type": SourceType.CHALLENGE_SYNTHETIC_REFERENCE,
        "rights_basis": "Synthetic test data",
    }
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=SYNTHETIC,
        classification=UsageClassification.INTERNAL,
        is_synthetic=True,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=RESTRICTED,
        classification=UsageClassification.RESTRICTED,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=REAL_INTERNAL,
        classification=UsageClassification.INTERNAL,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_B,
        source_id=OTHER_TENANT,
        classification=UsageClassification.INTERNAL,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=AUTOMATED,
        classification=UsageClassification.INTERNAL,
        discovery_mode=DiscoveryMode.API_POLL,
        endpoint_ref="fake",
        poll_interval_seconds=3600,
        expected_cadence_seconds=3600,
        is_synthetic=True,
        **common,
    )


def entitle(
    sessions: sessionmaker[Session],
    users: Users,
    subject: str,
    source_id: str,
    *rights: str,
    classification: str = "RESTRICTED",
    expires_at: datetime | None = None,
) -> None:
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id=uuid4().hex,
                subject=users.ids[subject],
                tenant_id=TENANT_A,
                object_type="source",
                object_id=source_id,
                classification=classification,
                rights=list(rights),
                expires_at_utc=expires_at,
            )
        )
        session.commit()


def begin_upload(
    client: TestClient,
    headers: dict[str, str],
    size: int,
    *,
    source_id: str = SYNTHETIC,
    classification: str = "INTERNAL",
    filename: str = "demo.txt",
    manifest_sha256: str | None = None,
    key: str | None = None,
) -> Any:
    body: dict[str, Any] = {
        "source_id": source_id,
        "source_type": "CHALLENGE_SYNTHETIC_REFERENCE",
        "usage_classification": classification,
        "filename_original": filename,
        "expected_size_bytes": size,
    }
    if manifest_sha256:
        body["content_sha256"] = manifest_sha256
    return client.post(
        "/api/v1/uploads",
        json=body,
        headers={**headers, "Idempotency-Key": key or uuid4().hex},
    )


def send_all(
    client: TestClient,
    headers: dict[str, str],
    upload_id: str,
    data: bytes,
    *,
    client_sha256: str | None = None,
) -> Any:
    response = client.put(f"/api/v1/uploads/{upload_id}/parts/1", content=data, headers=headers)
    assert response.status_code == 200, response.text
    etag = response.headers["ETag"]
    return client.post(
        f"/api/v1/uploads/{upload_id}/complete",
        json={
            "parts": [{"part_number": 1, "etag": etag}],
            "content_sha256": client_sha256 or hashlib.sha256(data).hexdigest(),
        },
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )


def ingest(
    client: TestClient,
    runtime: WorkerRuntime,
    headers: dict[str, str],
    data: bytes,
    **kwargs: Any,
) -> dict[str, Any]:
    """Upload, run the worker, and return the finished upload."""
    client_sha256 = kwargs.pop("client_sha256", None)
    created = begin_upload(client, headers, len(data), **kwargs)
    assert created.status_code == 201, created.text
    upload_id = created.json()["upload_id"]
    completed = send_all(client, headers, upload_id, data, client_sha256=client_sha256)
    assert completed.status_code == 200, completed.text
    run_until_idle(runtime)
    return client.get(f"/api/v1/uploads/{upload_id}", headers=headers).json()


def artifact_of(
    client: TestClient, headers: dict[str, str], sessions: sessionmaker[Session], upload: dict
) -> SourceArtifactDetail:
    with sessions() as session:
        artifact_id = session.get_one(UploadSessionRow, upload["upload_id"]).artifact_id
    response = client.get(f"/api/v1/source-artifacts/{artifact_id}", headers=headers)
    assert response.status_code == 200, response.text
    return SourceArtifactDetail.model_validate(response.json())


# --- Ingestion and integrity ------------------------------------------------------------------


def test_upload_to_indexed_record_end_to_end(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = UploadSession.model_validate(ingest(secure_client, runtime, headers, data))
    assert upload.status is PipelineStatus.READY
    assert upload.content_sha256 == hashlib.sha256(data).hexdigest()

    job = secure_client.get(f"/api/v1/jobs/{upload.job_id}", headers=headers)
    parsed_job = JobRun.model_validate(job.json())
    assert parsed_job.status is PipelineStatus.READY
    assert parsed_job.processed_records == 2

    artifact = artifact_of(secure_client, headers, sessions, upload.model_dump())
    assert artifact.status == "INDEXED_WITH_WARNINGS"
    assert artifact.publisher_auth_status == "NO_PUBLISHER_DIGEST"
    assert artifact.byte_length == len(data)
    assert artifact.analysis_eligible is True
    assert artifact.is_synthetic is True

    report = ArtifactIntegrityReport.model_validate(
        secure_client.get(
            f"/api/v1/source-artifacts/{artifact.artifact_id}/integrity", headers=headers
        ).json()
    )
    assert report.row_reconciliation is not None
    assert report.row_reconciliation.model_dump() == {
        "parsed": 2,
        "accepted": 1,
        "flagged": 1,
        "rejected": 0,
    }


def test_flagged_values_stay_raw_and_are_never_guessed(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
) -> None:
    headers = bearer("analyst-a")
    ingest(secure_client, runtime, headers, demo_file())
    hits = secure_client.get(
        "/api/v1/source-records", params={"station_number": "STATION-2"}, headers=headers
    ).json()["items"]
    assert hits[0]["frequency_start_mhz"] is None
    detail = SourceRecordDetail.model_validate(
        secure_client.get(
            f"/api/v1/source-records/{hits[0]['source_record_id']}", headers=headers
        ).json()
    )
    assert detail.raw_fields["tx_frequency"] == "99"
    assert detail.reference_station is not None
    assert detail.reference_station.tx_frequency_hz is None
    assert detail.reference_station.radiation_power_value is None
    assert [finding.rule_id for finding in detail.quality_findings] == ["UNIT_UNSPECIFIED"]
    assert detail.location.source_row_or_key == "3"
    assert detail.location.raw_sha256


def test_matching_supplied_manifest_is_not_publisher_verification(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = ingest(
        secure_client, runtime, headers, data, manifest_sha256=hashlib.sha256(data).hexdigest()
    )
    artifact = artifact_of(secure_client, headers, sessions, upload)
    assert artifact.publisher_auth_status == "HASH_MATCH_MANIFEST_UNTRUSTED"
    assert artifact.expected_digest_origin == "uploader-supplied-manifest"


def test_changed_file_with_same_name_is_a_new_immutable_revision(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    first_bytes = demo_file("STATION-1,100.5 MHz,10")
    second_bytes = demo_file("STATION-1,101.5 MHz,10")
    first = artifact_of(
        secure_client,
        headers,
        sessions,
        ingest(secure_client, runtime, headers, first_bytes, filename="same-name.txt"),
    )
    second = artifact_of(
        secure_client,
        headers,
        sessions,
        ingest(secure_client, runtime, headers, second_bytes, filename="same-name.txt"),
    )
    assert (first.revision, second.revision) == (1, 2)
    assert first.artifact_id != second.artifact_id
    assert first.raw_sha256 != second.raw_sha256
    for artifact, data in ((first, first_bytes), (second, second_bytes)):
        response = secure_client.get(
            f"/api/v1/source-artifacts/{artifact.artifact_id}/content", headers=headers
        )
        assert response.content == data
        assert hashlib.sha256(response.content).hexdigest() == artifact.raw_sha256


def test_same_bytes_again_keep_one_artifact_and_record_the_receipt(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    first = artifact_of(
        secure_client, headers, sessions, ingest(secure_client, runtime, headers, data)
    )
    second = artifact_of(
        secure_client,
        headers,
        sessions,
        ingest(secure_client, runtime, headers, data, filename="renamed.txt"),
    )
    assert first.artifact_id == second.artifact_id
    with sessions() as session:
        count = session.scalar(
            select(func.count())
            .select_from(SourceRecordLocationRow)
            .where(SourceRecordLocationRow.artifact_id == first.artifact_id)
        )
    assert count == 2
    report = secure_client.get(
        f"/api/v1/source-artifacts/{first.artifact_id}/integrity", headers=headers
    ).json()
    assert "DUPLICATE_RECEIPT" in {check["check_type"] for check in report["checks"]}


@pytest.mark.parametrize("kind", ["transport", "manifest"])
def test_corrupted_bytes_are_quarantined_and_unusable(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    kind: str,
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    wrong = hashlib.sha256(b"different bytes").hexdigest()
    arguments = {"client_sha256": wrong} if kind == "transport" else {"manifest_sha256": wrong}
    upload = ingest(secure_client, runtime, headers, data, **arguments)
    assert upload["status"] == "QUARANTINED"
    assert upload["failure_code"] == "UPLOAD_CHECKSUM_MISMATCH"

    artifact = artifact_of(secure_client, headers, sessions, upload)
    assert artifact.status == "QUARANTINED"
    assert artifact.analysis_eligible is False
    path = f"/api/v1/source-artifacts/{artifact.artifact_id}"
    assert secure_client.get(f"{path}/preview", headers=headers).status_code == 409
    assert secure_client.get(f"{path}/content", headers=headers).status_code == 409
    results = secure_client.get("/api/v1/source-records", headers=headers).json()["items"]
    assert results == []
    reparse = secure_client.post(
        "/api/v1/ingest/ific",
        json={
            "artifact_id": artifact.artifact_id,
            "source_type": "CHALLENGE_SYNTHETIC_REFERENCE",
        },
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )
    assert reparse.status_code == 409
    with sessions() as session:
        kinds = session.scalars(select(OutboxEventRow.event_kind)).all()
    assert kinds.count("ARTIFACT_QUARANTINED") == 1


def test_unreadable_file_is_quarantined_with_no_partial_index(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    upload = ingest(secure_client, runtime, headers, b"not the expected format\n")
    assert upload["status"] == "QUARANTINED"
    artifact = artifact_of(secure_client, headers, sessions, upload)
    assert artifact.status == "QUARANTINED"
    assert secure_client.get("/api/v1/source-records", headers=headers).json()["items"] == []


def test_one_bad_record_does_not_discard_good_rows(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    adapters: dict[str, Any],
) -> None:
    class OneBadRecord(DemoAdapter):
        def _record(self, row: int, cells: list[str]) -> dict[str, Any]:
            record = super()._record(row, cells)
            if cells[0] == "BAD":
                record["frequency_start_mhz"] = "SECRET-VALUE"
            return record

    adapters[DemoAdapter.source_type] = OneBadRecord()
    headers = bearer("analyst-a")
    upload = ingest(
        secure_client, runtime, headers, demo_file("GOOD,100.5 MHz,10", "BAD,100.5 MHz,10")
    )
    artifact = artifact_of(secure_client, headers, sessions, upload)
    report = secure_client.get(
        f"/api/v1/source-artifacts/{artifact.artifact_id}/integrity", headers=headers
    )
    assert report.json()["row_reconciliation"] == {
        "parsed": 2,
        "accepted": 1,
        "flagged": 0,
        "rejected": 1,
    }
    assert "SECRET-VALUE" not in report.text
    assert artifact.status == "INDEXED_WITH_WARNINGS"
    hits = secure_client.get("/api/v1/source-records", headers=headers).json()["items"]
    assert [hit["station_number"] for hit in hits] == ["GOOD"]


def test_no_parser_keeps_verified_bytes_unindexed_until_one_exists(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    adapters: dict[str, Any],
) -> None:
    adapter = adapters.pop(DemoAdapter.source_type)
    headers = bearer("analyst-a")
    upload = ingest(secure_client, runtime, headers, demo_file())
    assert upload["status"] == "PARTIAL"
    assert upload["failure_code"] == "PARSER_UNAVAILABLE"
    artifact = artifact_of(secure_client, headers, sessions, upload)
    assert artifact.status == "VERIFIED_BYTES"
    assert artifact.analysis_eligible is False
    assert artifact.indexed_at_utc is None
    preview = secure_client.get(
        f"/api/v1/source-artifacts/{artifact.artifact_id}/preview", headers=headers
    )
    assert preview.status_code == 409

    adapters[DemoAdapter.source_type] = adapter
    accepted = secure_client.post(
        "/api/v1/ingest/ific",
        json={
            "artifact_id": artifact.artifact_id,
            "source_type": "CHALLENGE_SYNTHETIC_REFERENCE",
        },
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )
    assert accepted.status_code == 202
    run_until_idle(runtime)
    assert artifact_of(secure_client, headers, sessions, upload).status == "INDEXED_WITH_WARNINGS"


# --- Upload protocol --------------------------------------------------------------------------


def test_repeated_create_and_complete_start_only_one_job(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    first = begin_upload(secure_client, headers, len(data), key="repeat-key-1").json()
    again = begin_upload(secure_client, headers, len(data), key="repeat-key-1").json()
    assert first["upload_id"] == again["upload_id"]

    upload_id = first["upload_id"]
    etag = secure_client.put(
        f"/api/v1/uploads/{upload_id}/parts/1", content=data, headers=headers
    ).headers["ETag"]
    body = {
        "parts": [{"part_number": 1, "etag": etag}],
        "content_sha256": hashlib.sha256(data).hexdigest(),
    }
    for _ in range(2):
        response = secure_client.post(
            f"/api/v1/uploads/{upload_id}/complete",
            json=body,
            headers={**headers, "Idempotency-Key": "complete-key"},
        )
        assert response.status_code == 200
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(JobRunRow)) == 1


def test_short_or_oversized_part_is_rejected_and_can_be_resent(
    secure_client: TestClient, bearer: Bearer
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    path = f"/api/v1/uploads/{upload['upload_id']}/parts/1"
    assert secure_client.put(path, content=data[:-1], headers=headers).status_code == 409
    assert secure_client.put(path, content=data + b"x", headers=headers).status_code == 409
    state = secure_client.get(f"/api/v1/uploads/{upload['upload_id']}", headers=headers).json()
    assert state["received_size_bytes"] == 0
    assert secure_client.put(path, content=data, headers=headers).status_code == 200


def test_complete_requires_every_part_and_matching_etags(
    secure_client: TestClient, bearer: Bearer
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    upload_id = upload["upload_id"]
    body = {
        "parts": [{"part_number": 1, "etag": "x"}],
        "content_sha256": hashlib.sha256(data).hexdigest(),
    }
    complete = f"/api/v1/uploads/{upload_id}/complete"
    idempotency = {**headers, "Idempotency-Key": "complete-key"}
    missing = secure_client.post(complete, json=body, headers=idempotency)
    assert missing.status_code == 409
    assert missing.json()["error"]["code"] == "UPLOAD_INCOMPLETE"
    secure_client.put(f"/api/v1/uploads/{upload_id}/parts/1", content=data, headers=headers)
    wrong = secure_client.post(complete, json=body, headers=idempotency)
    assert wrong.status_code == 409
    assert wrong.json()["error"]["code"] == "UPLOAD_CHECKSUM_MISMATCH"


def test_part_urls_are_renewable_for_a_resumed_upload(
    secure_client: TestClient, bearer: Bearer
) -> None:
    headers = bearer("analyst-a")
    upload = begin_upload(secure_client, headers, 10).json()
    path = f"/api/v1/uploads/{upload['upload_id']}/parts"
    urls = secure_client.post(path, json={"part_numbers": [1]}, headers=headers)
    assert urls.status_code == 200
    assert urls.json()["parts"][0]["url"].endswith(f"{upload['upload_id']}/parts/1")
    beyond = secure_client.post(path, json={"part_numbers": [2]}, headers=headers)
    assert beyond.status_code == 422


def test_expired_and_aborted_uploads_stop_receiving(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    headers = bearer("analyst-a")
    expired = begin_upload(secure_client, headers, 5).json()
    with sessions() as session:
        row = session.get_one(UploadSessionRow, expired["upload_id"])
        row.expires_at_utc = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    response = secure_client.put(
        f"/api/v1/uploads/{expired['upload_id']}/parts/1", content=b"12345", headers=headers
    )
    assert response.status_code == 409

    aborted = begin_upload(secure_client, headers, 5).json()
    path = f"/api/v1/uploads/{aborted['upload_id']}"
    assert secure_client.post(f"{path}/abort", headers=headers).json()["status"] == "CANCELLED"
    late = secure_client.put(f"{path}/parts/1", content=b"12345", headers=headers)
    assert late.status_code == 409


def test_upload_rules_for_source_type_classification_and_size(
    secure_client: TestClient, bearer: Bearer, secure_app: FastAPI
) -> None:
    headers = bearer("analyst-a")
    relaxed = begin_upload(secure_client, headers, 5, classification="PUBLIC")
    assert relaxed.status_code == 409

    too_large = begin_upload(secure_client, headers, secure_app.state.library.max_upload_bytes + 1)
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "UPLOAD_TOO_LARGE"

    wrong_type = secure_client.post(
        "/api/v1/uploads",
        json={
            "source_id": SYNTHETIC,
            "source_type": "SPACE_IFIC",
            "usage_classification": "INTERNAL",
            "filename_original": "x",
            "expected_size_bytes": 5,
        },
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )
    assert wrong_type.status_code == 409


def test_restricted_import_needs_an_import_right(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = bearer("analyst-a")
    denied = begin_upload(
        secure_client, headers, 5, source_id=RESTRICTED, classification="RESTRICTED"
    )
    assert denied.status_code == 404
    entitle(sessions, users, "analyst-a", RESTRICTED, "IMPORT")
    allowed = begin_upload(
        secure_client, headers, 5, source_id=RESTRICTED, classification="RESTRICTED"
    )
    assert allowed.status_code == 201


def test_hostile_filename_cannot_reach_outside_the_store(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,
    tmp_path: Path,
) -> None:
    headers = bearer("analyst-a")
    hostile = "../../../../escape.txt"
    artifact = artifact_of(
        secure_client,
        headers,
        sessions,
        ingest(secure_client, runtime, headers, demo_file(), filename=hostile),
    )
    assert artifact.filename_original == hostile
    assert not (tmp_path / "escape.txt").exists()
    assert not list(tmp_path.parent.glob("escape*"))


def test_object_store_rejects_traversal_and_never_overwrites(tmp_path: Path) -> None:
    store = LocalObjectStore(tmp_path / "store")
    staged = tmp_path / "staged"
    with pytest.raises(ObjectKeyError):
        store.local_path("masters/../../outside")
    with pytest.raises(ObjectKeyError):
        store.promote(staged, ("..", "outside"))

    staged.write_bytes(b"original")
    key = store.promote(staged, ("t", "s", "a", "hash"))
    staged.write_bytes(b"different")
    assert store.promote(staged, ("t", "s", "a", "hash")) == key
    assert store.local_path(key).read_bytes() == b"original"
    assert not staged.exists()


# --- Durable jobs -----------------------------------------------------------------------------


def test_worker_crash_is_recovered_without_duplicate_records(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)

    crashed = jobs.claim(sessions, "dead-worker", lease=timedelta(seconds=-1))
    assert crashed is not None
    assert run_until_idle(runtime) == 1
    state = secure_client.get(f"/api/v1/jobs/{crashed.job_id}", headers=headers).json()
    assert state["status"] == "READY"
    assert state["attempt"] == 2
    with sessions() as session:
        assert session.scalar(select(func.count()).select_from(SourceRecordLocationRow)) == 2


def test_failure_mid_parse_retries_without_duplicates(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    adapters: dict[str, Any],
) -> None:
    class FailsOnce(DemoAdapter):
        failed = False

        def iter_record_batches(self, artifact_path: Path, *, batch_rows: int) -> Iterator[Any]:
            for batch in super().iter_record_batches(artifact_path, batch_rows=1):
                yield batch
                if not FailsOnce.failed:
                    FailsOnce.failed = True
                    raise OSError("disk hiccup")

    adapters[DemoAdapter.source_type] = FailsOnce()
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)
    assert run_one(runtime) is True
    with sessions() as session:
        row = session.scalars(select(JobRunRow)).one()
        assert row.status == "RETRYING"
        row.next_attempt_at_utc = datetime.now(UTC)
        session.commit()
    run_until_idle(runtime)
    with sessions() as session:
        assert session.scalars(select(JobRunRow)).one().status == "READY"
        assert session.scalar(select(func.count()).select_from(SourceRecordLocationRow)) == 2


def test_repeated_failures_stop_with_a_visible_state(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    adapters: dict[str, Any],
) -> None:
    class AlwaysFails(DemoAdapter):
        def iter_record_batches(self, artifact_path: Path, *, batch_rows: int) -> Iterator[Any]:
            raise OSError("always")
            yield

    adapters[DemoAdapter.source_type] = AlwaysFails()
    headers = bearer("analyst-a")
    data = demo_file()
    upload = begin_upload(secure_client, headers, len(data)).json()
    send_all(secure_client, headers, upload["upload_id"], data)
    for _ in range(3):
        run_one(runtime)
        with sessions() as session:
            row = session.scalars(select(JobRunRow)).one()
            row.next_attempt_at_utc = datetime.now(UTC)
            session.commit()
    with sessions() as session:
        job = session.scalars(select(JobRunRow)).one()
        assert job.status == "FAILED"
        assert job.error_detail == "OSError"
    state = secure_client.get(f"/api/v1/uploads/{upload['upload_id']}", headers=headers).json()
    assert state["status"] == "FAILED"


def test_claim_returns_nothing_while_a_lease_is_held(
    sessions: sessionmaker[Session], users: Users
) -> None:
    jobs.enqueue(
        sessions,
        tenant_id=TENANT_A,
        job_type=JobType.INGEST,
        lane=jobs.LANE_INGESTION,
        idempotency_key="k",
        requested_by="x",
        payload={},
    )
    assert jobs.claim(sessions, "w1") is not None
    assert jobs.claim(sessions, "w2") is None


# --- Indexed preview and search ---------------------------------------------------------------


def test_preview_search_and_record_never_touch_the_master(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    store: LocalObjectStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit test: viewing an indexed record does not re-download or open the original."""
    headers = bearer("analyst-a")
    padding = "x" * 200_000
    data = demo_file(f"STATION-1,100.5 MHz,{padding}", *[f"S-{n},101 MHz,1" for n in range(120)])
    artifact = artifact_of(
        secure_client, headers, sessions, ingest(secure_client, runtime, headers, data)
    )

    def forbidden(*_args: Any) -> None:
        raise AssertionError("the master file must not be opened")

    monkeypatch.setattr(store, "open_read", forbidden)
    monkeypatch.setattr(store, "local_path", forbidden)

    search = secure_client.get(
        "/api/v1/source-records",
        params={"station_number": "S-5"},
        headers=headers,
    )
    assert search.status_code == 200
    record_id = search.json()["items"][0]["source_record_id"]
    record = secure_client.get(f"/api/v1/source-records/{record_id}", headers=headers)
    assert record.status_code == 200
    location = secure_client.get(
        f"/api/v1/source-records/{record_id}/source-location", headers=headers
    )
    assert location.json()["raw_sha256"] == artifact.raw_sha256
    assert len(search.content) + len(record.content) + len(location.content) < len(data) / 10

    preview = secure_client.get(
        f"/api/v1/source-artifacts/{artifact.artifact_id}/preview",
        params={"table": "demo-sheet", "row": 10},
        headers=headers,
    )
    parsed = SourcePreview.model_validate(preview.json())
    assert [row.location.source_row_or_key for row in parsed.rows] == ["10"]


def test_preview_pages_are_bounded(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
) -> None:
    headers = bearer("analyst-a")
    data = demo_file(*[f"S-{n},101 MHz,1" for n in range(120)])
    artifact = artifact_of(
        secure_client, headers, sessions, ingest(secure_client, runtime, headers, data)
    )
    path = f"/api/v1/source-artifacts/{artifact.artifact_id}/preview"
    seen = 0
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else {}
        body = secure_client.get(path, params=params, headers=headers).json()
        assert len(body["rows"]) <= 50
        seen += len(body["rows"])
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == 120


def test_search_filters_pagination_and_literal_matching(
    secure_client: TestClient, bearer: Bearer, runtime: WorkerRuntime
) -> None:
    headers = bearer("analyst-a")
    ingest(
        secure_client,
        runtime,
        headers,
        demo_file("ALPHA,100 MHz,1", "BETA,200 MHz,1", "GAMMA,300 MHz,1", "DELTA,99,1"),
    )

    def stations(**params: Any) -> list[str | None]:
        response = secure_client.get("/api/v1/source-records", params=params, headers=headers)
        assert response.status_code == 200
        return sorted(item["station_number"] for item in response.json()["items"])

    assert stations(query="alpha") == ["ALPHA"]
    assert stations(frequency_start_mhz=150, frequency_end_mhz=250) == ["BETA"]
    # A record with an unusable frequency is never presented as a frequency match.
    assert "DELTA" not in stations(frequency_start_mhz=0, frequency_end_mhz=1000)
    assert stations(query="%") == []
    assert stations(query="' OR 1=1 --") == []

    first = secure_client.get("/api/v1/source-records", params={"limit": 3}, headers=headers).json()
    assert len(first["items"]) == 3
    assert first["total_if_known"] is None
    rest = secure_client.get(
        "/api/v1/source-records", params={"cursor": first["next_cursor"]}, headers=headers
    ).json()
    assert len(rest["items"]) == 1
    bad = secure_client.get("/api/v1/source-records", params={"cursor": "%%%"}, headers=headers)
    assert bad.status_code == 422


# --- Access control ---------------------------------------------------------------------------


@pytest.fixture
def restricted_artifact(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    sessions: sessionmaker[Session],
    users: Users,
) -> dict[str, str]:
    """A restricted artifact, ingested by an analyst with import and read rights."""
    headers = bearer("analyst-a")
    entitle(sessions, users, "analyst-a", RESTRICTED, "IMPORT", "READ")
    upload = ingest(
        secure_client,
        runtime,
        headers,
        demo_file(),
        source_id=RESTRICTED,
        classification="RESTRICTED",
        filename="secret-file-name.txt",
    )
    artifact = artifact_of(secure_client, headers, sessions, upload)
    hit = secure_client.get("/api/v1/source-records", headers=headers).json()["items"][0]
    return {"artifact_id": artifact.artifact_id, "record_id": hit["source_record_id"]}


def _object_paths(target: dict[str, str]) -> list[str]:
    artifact = f"/api/v1/source-artifacts/{target['artifact_id']}"
    record = f"/api/v1/source-records/{target['record_id']}"
    return [
        artifact,
        f"{artifact}/integrity",
        f"{artifact}/preview",
        record,
        f"{record}/source-location",
    ]


@pytest.mark.parametrize(
    "subject",
    ["reviewer-a", "demo-a", "analyst-b"],
    ids=["unentitled-same-tenant", "demo-viewer", "other-tenant"],
)
def test_unentitled_users_cannot_find_or_open_restricted_data(
    secure_client: TestClient,
    bearer: Bearer,
    restricted_artifact: dict[str, str],
    subject: str,
) -> None:
    headers = bearer(subject)
    for path in _object_paths(restricted_artifact):
        response = secure_client.get(path, headers=headers)
        assert response.status_code == 404, path
        assert "secret-file-name" not in response.text
    for path, params in (
        ("/api/v1/source-records", {}),
        ("/api/v1/source-records", {"query": "secret-file-name"}),
        ("/api/v1/source-artifacts", {}),
        ("/api/v1/source-artifacts", {"filename": "secret"}),
        ("/api/v1/source-publications", {}),
    ):
        response = secure_client.get(path, params=params, headers=headers)
        assert response.status_code == 200
        assert response.json()["items"] == [], path


def test_denied_object_looks_exactly_like_a_missing_one(
    secure_client: TestClient, bearer: Bearer, restricted_artifact: dict[str, str]
) -> None:
    headers = bearer("reviewer-a")
    denied = secure_client.get(
        f"/api/v1/source-artifacts/{restricted_artifact['artifact_id']}", headers=headers
    )
    absent = secure_client.get("/api/v1/source-artifacts/does-not-exist", headers=headers)
    assert denied.status_code == absent.status_code == 404
    denied_error, absent_error = denied.json()["error"], absent.json()["error"]
    assert {k: v for k, v in denied_error.items() if k != "request_id"} == {
        k: v for k, v in absent_error.items() if k != "request_id"
    }


def test_administrator_has_no_bypass_on_restricted_content(
    secure_client: TestClient,
    bearer: Bearer,
    restricted_artifact: dict[str, str],
) -> None:
    """Administrators lack the capability, so the route refuses before any object check."""
    headers = bearer("admin-a")
    for path in _object_paths(restricted_artifact):
        assert secure_client.get(path, headers=headers).status_code == 403
    sources = secure_client.get("/api/v1/sources", headers=headers)
    assert sources.status_code == 200


def test_entitlement_opens_records_but_download_is_a_separate_right(
    secure_client: TestClient,
    bearer: Bearer,
    restricted_artifact: dict[str, str],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = bearer("reviewer-a")
    entitle(sessions, users, "reviewer-a", RESTRICTED, "READ")
    for path in _object_paths(restricted_artifact):
        assert secure_client.get(path, headers=headers).status_code == 200, path
    hits = secure_client.get("/api/v1/source-records", headers=headers).json()["items"]
    assert len(hits) == 2

    artifact = f"/api/v1/source-artifacts/{restricted_artifact['artifact_id']}"
    link_body = {"acknowledge_transfer_size": True}
    denied = secure_client.post(f"{artifact}/download-link", json=link_body, headers=headers)
    assert denied.status_code == 404
    assert secure_client.get(f"{artifact}/content", headers=headers).status_code == 404

    entitle(sessions, users, "reviewer-a", RESTRICTED, "DOWNLOAD")
    link = secure_client.post(f"{artifact}/download-link", json=link_body, headers=headers).json()
    assert link["url"].endswith("/content")
    content = secure_client.get(link["url"], headers=headers)
    assert hashlib.sha256(content.content).hexdigest() == link["raw_sha256"]
    assert content.headers["X-Content-Type-Options"] == "nosniff"


def test_expired_entitlement_removes_restricted_results(
    secure_client: TestClient,
    bearer: Bearer,
    restricted_artifact: dict[str, str],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    headers = bearer("reviewer-a")
    entitle(
        sessions,
        users,
        "reviewer-a",
        RESTRICTED,
        "READ",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    assert secure_client.get("/api/v1/source-records", headers=headers).json()["items"] == []


def test_demo_viewer_sees_synthetic_records_only(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
) -> None:
    analyst = bearer("analyst-a")
    ingest(secure_client, runtime, analyst, demo_file("SYN,100 MHz,1"), source_id=SYNTHETIC)
    ingest(secure_client, runtime, analyst, demo_file("REAL,100 MHz,1"), source_id=REAL_INTERNAL)
    viewer = bearer("demo-a")
    hits = secure_client.get("/api/v1/source-records", headers=viewer).json()["items"]
    assert [hit["station_number"] for hit in hits] == ["SYN"]
    sources = secure_client.get("/api/v1/sources", headers=viewer).json()["items"]
    assert REAL_INTERNAL not in {source["source_id"] for source in sources}
    assert analyst != viewer


def test_uploads_and_jobs_belong_to_their_owner(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
) -> None:
    owner = bearer("analyst-a")
    data = demo_file()
    upload = ingest(secure_client, runtime, owner, data)
    upload_path = f"/api/v1/uploads/{upload['upload_id']}"
    job_path = f"/api/v1/jobs/{upload['job_id']}"
    for subject in ("reviewer-a", "analyst-b"):
        headers = bearer(subject)
        assert secure_client.get(upload_path, headers=headers).status_code == 404
        assert secure_client.get(job_path, headers=headers).status_code == 404
    other_owner = bearer("analyst-b")
    forged = secure_client.put(f"{upload_path}/parts/1", content=data, headers=other_owner)
    assert forged.status_code == 404
    assert secure_client.post(f"{upload_path}/abort", headers=other_owner).status_code == 404
    operator = bearer("admin-a")
    assert secure_client.get(upload_path, headers=operator).status_code == 200
    assert secure_client.get(job_path, headers=operator).status_code == 200
    assert secure_client.get(job_path, headers=bearer("analyst-a")).status_code == 200


def test_other_tenants_source_cannot_receive_an_upload(
    secure_client: TestClient, bearer: Bearer
) -> None:
    response = begin_upload(secure_client, bearer("analyst-a"), 5, source_id=OTHER_TENANT)
    assert response.status_code == 404


def test_object_denial_and_download_are_audited(
    secure_client: TestClient,
    bearer: Bearer,
    restricted_artifact: dict[str, str],
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    artifact_id = restricted_artifact["artifact_id"]
    secure_client.get(f"/api/v1/source-artifacts/{artifact_id}", headers=bearer("reviewer-a"))
    entitle(sessions, users, "analyst-a", RESTRICTED, "DOWNLOAD")
    secure_client.get(f"/api/v1/source-artifacts/{artifact_id}/content", headers=bearer())
    with sessions() as session:
        events = session.scalars(select(AuditEvent)).all()
    denied = [e for e in events if e.outcome == "DENIED_OBJECT"]
    assert denied and denied[0].actor == users.ids["reviewer-a"]
    assert any(
        e.action == "download_source_artifact" and e.outcome == "ALLOWED" for e in events
    )


# --- Sources, discovery and acquisition -------------------------------------------------------


def test_connector_views_hide_credentials_and_show_manual_status(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    with sessions() as session:
        row = session.get_one(SourceConnectorRow, AUTOMATED)
        row.auth_secret_ref = "vault://secret-reference"
        session.commit()
    headers = bearer("analyst-a")
    response = secure_client.get("/api/v1/sources", headers=headers)
    assert "vault://" not in response.text
    assert "endpoint_ref" not in response.text
    statuses = {item["source_id"]: item["status"] for item in response.json()["items"]}
    assert statuses[SYNTHETIC] == "MANUAL_REQUIRED"
    assert OTHER_TENANT not in statuses
    other = secure_client.get(f"/api/v1/sources/{OTHER_TENANT}/health", headers=headers)
    assert other.status_code == 404


def test_manual_source_has_no_automated_check(secure_client: TestClient, bearer: Bearer) -> None:
    response = secure_client.post(
        f"/api/v1/admin/sources/{SYNTHETIC}/check",
        headers={**bearer("admin-a"), "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "MANUAL_REQUIRED"


def _check(client: TestClient, bearer: Bearer, runtime: WorkerRuntime) -> None:
    response = client.post(
        f"/api/v1/admin/sources/{AUTOMATED}/check",
        headers={**bearer("admin-a"), "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 202, response.text


def _drain_new_check(sessions: sessionmaker[Session], runtime: WorkerRuntime) -> None:
    run_until_idle(runtime)
    # The per-minute check bucket would otherwise return the finished job in the same test.
    with sessions() as session:
        for row in session.scalars(select(JobRunRow)):
            if row.job_type == JobType.SOURCE_DISCOVERY.value:
                row.idempotency_key = uuid4().hex
        session.commit()


def test_discovery_detects_new_unchanged_and_revised_without_redownloading(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
    sessions: sessionmaker[Session],
) -> None:
    first = demo_file("S-1,100 MHz,1")
    second = demo_file("S-1,101 MHz,1")
    published = datetime(2026, 11, 1, tzinfo=UTC)
    fake_source.publications = [
        RemotePublication("ISSUE-1", "issue.txt", "v1", published_at_utc=published)
    ]
    fake_source.files = {"ISSUE-1:v1": first, "ISSUE-1:v2": second}

    _check(secure_client, bearer, runtime)
    _drain_new_check(sessions, runtime)
    assert fake_source.downloads == 1

    _check(secure_client, bearer, runtime)
    _drain_new_check(sessions, runtime)
    assert fake_source.downloads == 1

    fake_source.publications = [
        RemotePublication("ISSUE-1", "issue.txt", "v1", published_at_utc=published),
        RemotePublication("ISSUE-1", "issue.txt", "v2", published_at_utc=published),
    ]
    _check(secure_client, bearer, runtime)
    _drain_new_check(sessions, runtime)
    assert fake_source.downloads == 2

    headers = bearer("analyst-a")
    publications = secure_client.get("/api/v1/source-publications", headers=headers).json()["items"]
    states = sorted(item["observation_status"] for item in publications)
    assert states == ["REVISED", "UNCHANGED"]
    for item in publications:
        assert item["published_at_utc"] == "2026-11-01T00:00:00Z"
        assert item["first_seen_at_utc"] != item["published_at_utc"]
    artifacts = secure_client.get("/api/v1/source-artifacts", headers=headers).json()["items"]
    assert sorted(a["revision"] for a in artifacts) == [1, 2]
    with sessions() as session:
        kinds = session.scalars(select(OutboxEventRow.event_kind)).all()
    assert kinds.count("SOURCE_PUBLISHED") == 1
    assert kinds.count("SOURCE_REVISED") == 1


def test_access_denied_blocks_the_source_and_is_not_retried(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
    sessions: sessionmaker[Session],
) -> None:
    fake_source.discover_error = SourceAccessDenied()
    _check(secure_client, bearer, runtime)
    run_until_idle(runtime)
    with sessions() as session:
        job = session.scalars(select(JobRunRow)).one()
    assert (job.status, job.attempt, job.error_code) == ("FAILED", 1, "SOURCE_RESTRICTED")
    health = SourceHealth.model_validate(
        secure_client.get(f"/api/v1/sources/{AUTOMATED}/health", headers=bearer()).json()
    )
    assert health.status == "ACCESS_DENIED"
    assert enqueue_due_checks(sessions) == 0


def test_outage_never_reads_as_a_retraction(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
    sessions: sessionmaker[Session],
) -> None:
    fake_source.publications = [RemotePublication("ISSUE-1", "issue.txt", "v1")]
    fake_source.files = {"ISSUE-1:v1": demo_file()}
    _check(secure_client, bearer, runtime)
    _drain_new_check(sessions, runtime)

    fake_source.discover_error = SourceUnavailable("down")
    _check(secure_client, bearer, runtime)
    run_one(runtime)
    with sessions() as session:
        job = session.scalars(
            select(JobRunRow).where(JobRunRow.status == "RETRYING")
        ).one()
        assert job.job_type == JobType.SOURCE_DISCOVERY.value
    headers = bearer("analyst-a")
    items = secure_client.get("/api/v1/source-publications", headers=headers).json()["items"]
    assert [item["observation_status"] for item in items] == ["NEW"]
    health = secure_client.get(f"/api/v1/sources/{AUTOMATED}/health", headers=headers).json()
    assert health["status"] == "SOURCE_UNAVAILABLE"
    assert health["failure_summary"] == "The source could not be reached."


def test_stale_source_is_not_reported_as_healthy(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    with sessions() as session:
        row = session.get_one(SourceConnectorRow, AUTOMATED)
        row.last_success_at_utc = datetime.now(UTC) - timedelta(days=30)
        session.commit()
    health = secure_client.get(f"/api/v1/sources/{AUTOMATED}/health", headers=bearer()).json()
    assert health["status"] == "SOURCE_STALE"


@pytest.mark.parametrize(
    ("change", "expected_auth"),
    [
        ({"expected_digest": "0" * 64, "expected_digest_origin": "publisher"}, "MISMATCH"),
        ({"remote_size_bytes": 1}, "NO_PUBLISHER_DIGEST"),
    ],
    ids=["digest-mismatch", "size-mismatch"],
)
def test_bad_download_is_quarantined(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
    sessions: sessionmaker[Session],
    change: dict[str, Any],
    expected_auth: str,
) -> None:
    fake_source.publications = [RemotePublication("ISSUE-1", "issue.txt", "v1", **change)]
    fake_source.files = {"ISSUE-1:v1": demo_file()}
    _check(secure_client, bearer, runtime)
    run_until_idle(runtime)
    headers = bearer("analyst-a")
    artifacts = secure_client.get("/api/v1/source-artifacts", headers=headers).json()["items"]
    assert [a["status"] for a in artifacts] == ["QUARANTINED"]
    assert artifacts[0]["publisher_auth_status"] == expected_auth
    assert artifacts[0]["analysis_eligible"] is False
    assert secure_client.get("/api/v1/source-records", headers=headers).json()["items"] == []


def test_publisher_trust_needs_a_signed_digest(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
) -> None:
    data = demo_file()
    fake_source.publications = [
        RemotePublication(
            "ISSUE-1",
            "issue.txt",
            "v1",
            expected_digest=hashlib.sha256(data).hexdigest(),
            expected_digest_origin="publisher signed manifest",
            publisher_signed=True,
        )
    ]
    fake_source.files = {"ISSUE-1:v1": data}
    _check(secure_client, bearer, runtime)
    run_until_idle(runtime)
    artifact = secure_client.get("/api/v1/source-artifacts", headers=bearer()).json()["items"][0]
    assert artifact["publisher_auth_status"] == "VERIFIED_PUBLISHER"


def _http_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "url",
    ["http://files.example/a", "https://other.example/a", "file:///etc/passwd"],
    ids=["plain-http", "unlisted-host", "file-scheme"],
)
def test_download_refuses_unapproved_urls(url: str) -> None:
    called = []

    def handler(request: httpx.Request) -> httpx.Response:
        called.append(request)
        return httpx.Response(200, content=b"x")

    with pytest.raises(UnsafeDownload):
        download_to_file(
            url, io.BytesIO(), allowed_hosts={"files.example"}, client=_http_client(handler)
        )
    assert called == []


def test_download_does_not_follow_redirects_to_internal_hosts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"Location": "http://169.254.169.254/"})

    with pytest.raises(UnsafeDownload):
        download_to_file(
            "https://files.example/a",
            io.BytesIO(),
            allowed_hosts={"files.example"},
            client=_http_client(handler),
        )


def test_download_reports_denied_truncated_and_oversized() -> None:
    allowed = {"files.example"}
    url = "https://files.example/a"
    with pytest.raises(SourceAccessDenied):
        download_to_file(
            url,
            io.BytesIO(),
            allowed_hosts=allowed,
            client=_http_client(lambda _r: httpx.Response(403)),
        )
    with pytest.raises(SourceUnavailable):
        download_to_file(
            url,
            io.BytesIO(),
            allowed_hosts=allowed,
            client=_http_client(lambda _r: httpx.Response(503)),
        )
    with pytest.raises(UnsafeDownload, match="ended early"):
        download_to_file(
            url,
            io.BytesIO(),
            allowed_hosts=allowed,
            client=_http_client(
                lambda _r: httpx.Response(
                    200, headers={"Content-Length": "9"}, stream=httpx.ByteStream(b"abc")
                )
            ),
        )
    with pytest.raises(UnsafeDownload, match="size limit"):
        download_to_file(
            url,
            io.BytesIO(),
            allowed_hosts=allowed,
            client=_http_client(
                lambda _r: httpx.Response(200, stream=httpx.ByteStream(b"abcdef"))
            ),
            max_bytes=3,
        )


def test_interrupted_download_leaves_no_artifact_and_retries(
    secure_client: TestClient,
    bearer: Bearer,
    runtime: WorkerRuntime,
    fake_source: FakeSource,
    sessions: sessionmaker[Session],
) -> None:
    fake_source.publications = [RemotePublication("ISSUE-1", "issue.txt", "v1")]
    fake_source.files = {"ISSUE-1:v1": demo_file()}
    fake_source.download_error = UnsafeDownload("Download ended early")
    _check(secure_client, bearer, runtime)
    run_one(runtime)
    run_one(runtime)
    headers = bearer("analyst-a")
    assert secure_client.get("/api/v1/source-artifacts", headers=headers).json()["items"] == []
    fake_source.download_error = None
    with sessions() as session:
        row = session.scalars(select(JobRunRow).where(JobRunRow.status == "RETRYING")).one()
        row.next_attempt_at_utc = datetime.now(UTC)
        session.commit()
    run_until_idle(runtime)
    artifacts = secure_client.get("/api/v1/source-artifacts", headers=headers).json()["items"]
    assert len(artifacts) == 1
    assert artifacts[0]["status"].startswith("INDEXED")


def test_local_object_store_is_refused_outside_demo(tmp_path: Path) -> None:
    with pytest.raises(SettingsError, match="demo only"):
        Settings(
            environment=Environment.PRODUCTION,
            database_url="postgresql+psycopg://db/app",
            oidc=oidc_settings(),
            object_store_path=tmp_path,
        )

