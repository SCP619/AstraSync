"""REST API v1 surface (BSD sections 5, 6.4 and 9).

Every operation declares a required capability, enforced by ``AuthorizedRoute``. Handlers return
501 until implemented: a route must never answer with sample data. Routes that touch stored
objects must also call ``ObjectAccessPolicy`` (see authz.py).
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import library
from .contract import CONTRACT_VERSION
from .contract.enums import (
    AlertSeverity,
    AlertStatus,
    ArtifactStatus,
    CaseDomain,
    CaseSort,
    ChangeType,
    ErrorCode,
    FindingStatus,
    ImplementationStatus,
    IssueDomain,
    ObservationStatus,
    ReviewStatus,
)
from .contract.models import (
    AlertAcknowledged,
    AlertAcknowledgeRequest,
    AlertDetail,
    AlertList,
    AlertPreferences,
    AlertPreferencesUpdate,
    AlertRuleList,
    AlertRuleSaved,
    AlertRuleUpsert,
    AnalyseRequest,
    AnalysisAccepted,
    AnalysisRun,
    ArtifactIntegrityReport,
    CaseDetail,
    CaseList,
    Device,
    DeviceRegistrationRequest,
    DownloadLink,
    DownloadLinkRequest,
    DraftCreated,
    DraftCreateRequest,
    ErrorResponse,
    EvidencePack,
    IngestRequest,
    IssueList,
    JobAccepted,
    JobRun,
    Me,
    MethodMatrix,
    NoticeChangeList,
    ReferenceList,
    ReviewCreateRequest,
    ReviewEvent,
    SourceArtifactDetail,
    SourceArtifactList,
    SourceConnectorList,
    SourceHealth,
    SourceLocationDetail,
    SourcePreview,
    SourcePublicationList,
    SourceRecordDetail,
    SourceRecordList,
    UploadCompleteRequest,
    UploadCreateRequest,
    UploadPartUrl,
    UploadPartUrls,
    UploadPartUrlsRequest,
    UploadSession,
)
from .contract.permissions import Capability
from .errors import ApiError
from .security import AuthorizedRoute, CurrentPrincipal, current_principal

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 429, 500, 501, 503)
}

router = APIRouter(
    prefix="/api/v1",
    route_class=AuthorizedRoute,
    responses=_ERROR_RESPONSES,
)

ResourceId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
Limit = Annotated[int, Query(ge=1, le=200)]
Cursor = Annotated[str | None, Query(max_length=1024)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
FrequencyMhz = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]
_IMPLEMENTED = ImplementationStatus.IMPLEMENTED


def _library(request: Request) -> library.LibraryRuntime:
    runtime: library.LibraryRuntime | None = request.app.state.library
    if runtime is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE, "The service is not configured.")
    return runtime


def _session(request: Request) -> Iterator[Session]:
    with _library(request).identities.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(_session)]


def _policy(
    capability: Capability, status: ImplementationStatus = ImplementationStatus.DESIGNED
) -> dict[str, Any]:
    return {
        "openapi_extra": {
            "x-required-capability": capability.value,
            "x-implementation-status": status.value,
        }
    }


def _not_implemented() -> ApiError:
    return ApiError(501, ErrorCode.NOT_IMPLEMENTED, "This operation is not implemented yet.")


@router.get(
    "/me",
    response_model=Me,
    **_policy(Capability.AUTHENTICATED, ImplementationStatus.IMPLEMENTED),
)
async def get_me(request: Request, principal: CurrentPrincipal) -> Any:
    return Me(
        schema_version=CONTRACT_VERSION,
        generated_at_utc=datetime.now(UTC),
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        environment=request.app.state.security.environment,
        roles=sorted(principal.roles),
        capabilities=sorted(principal.capabilities),
    )


# --- Ingestion, jobs, issues ------------------------------------------------------------------


@router.post(
    "/ingest/ific",
    response_model=JobAccepted,
    status_code=202,
    **_policy(Capability.INGEST_TRIGGER, _IMPLEMENTED),
)
def ingest_ific(
    request: Request,
    body: IngestRequest,
    idempotency_key: IdempotencyKey,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.ingest_artifact(_library(request), request, session, principal, body.artifact_id)


@router.get("/jobs/{job_id}", response_model=JobRun, **_policy(Capability.JOB_READ, _IMPLEMENTED))
def get_job(job_id: ResourceId, principal: CurrentPrincipal, session: DbSession) -> Any:
    return library.get_job(session, principal, job_id)


@router.get("/issues", response_model=IssueList, **_policy(Capability.ISSUE_READ))
async def list_issues(
    domain: IssueDomain | None = None, limit: Limit = 50, cursor: Cursor = None
) -> Any:
    raise _not_implemented()


@router.get(
    "/issues/{issue_id}/changes",
    response_model=NoticeChangeList,
    **_policy(Capability.ISSUE_READ),
)
async def list_issue_changes(
    issue_id: ResourceId,
    change_type: ChangeType | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


# --- Cases and analysis -----------------------------------------------------------------------


@router.get("/cases", response_model=CaseList, **_policy(Capability.CASE_READ))
async def list_cases(
    domain: CaseDomain | None = None,
    source_issue_id: Annotated[str | None, Query(max_length=128)] = None,
    change_type: ChangeType | None = None,
    finding_status: FindingStatus | None = None,
    review_status: ReviewStatus | None = None,
    query: Annotated[str | None, Query(max_length=256)] = None,
    sort: CaseSort = CaseSort.CASE_ID,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.get("/cases/{case_id}", response_model=CaseDetail, **_policy(Capability.CASE_READ))
async def get_case(case_id: ResourceId) -> Any:
    raise _not_implemented()


@router.post(
    "/cases/{case_id}/analyse",
    response_model=AnalysisAccepted,
    status_code=202,
    **_policy(Capability.ANALYSIS_RUN),
)
async def analyse_case(
    case_id: ResourceId, body: AnalyseRequest, idempotency_key: IdempotencyKey
) -> Any:
    raise _not_implemented()


@router.get(
    "/analyses/{analysis_run_id}",
    response_model=AnalysisRun,
    **_policy(Capability.ANALYSIS_READ),
)
async def get_analysis(analysis_run_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get(
    "/analyses/{analysis_run_id}/methods",
    response_model=MethodMatrix,
    **_policy(Capability.ANALYSIS_READ),
)
async def get_analysis_methods(analysis_run_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get("/references", response_model=ReferenceList, **_policy(Capability.REFERENCE_READ))
async def list_references(limit: Limit = 50, cursor: Cursor = None) -> Any:
    raise _not_implemented()


@router.post(
    "/cases/{case_id}/drafts",
    response_model=DraftCreated,
    status_code=201,
    **_policy(Capability.DRAFT_CREATE),
)
async def create_draft(
    case_id: ResourceId, body: DraftCreateRequest, idempotency_key: IdempotencyKey
) -> Any:
    raise _not_implemented()


@router.post(
    "/cases/{case_id}/reviews",
    response_model=ReviewEvent,
    status_code=201,
    **_policy(Capability.REVIEW_DECIDE),
)
async def create_review(
    case_id: ResourceId, body: ReviewCreateRequest, idempotency_key: IdempotencyKey
) -> Any:
    raise _not_implemented()


@router.get(
    "/cases/{case_id}/export", response_model=EvidencePack, **_policy(Capability.CASE_EXPORT)
)
async def export_case(case_id: ResourceId) -> Any:
    raise _not_implemented()


# --- Uploads ----------------------------------------------------------------------------------


@router.post(
    "/uploads",
    response_model=UploadSession,
    status_code=201,
    **_policy(Capability.UPLOAD_MANAGE, _IMPLEMENTED),
)
def create_upload(
    request: Request,
    body: UploadCreateRequest,
    idempotency_key: IdempotencyKey,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.create_upload(
        _library(request), request, session, principal, body, idempotency_key
    )


@router.get(
    "/uploads/{upload_id}",
    response_model=UploadSession,
    **_policy(Capability.JOB_READ, _IMPLEMENTED),
)
def get_upload(upload_id: ResourceId, principal: CurrentPrincipal, session: DbSession) -> Any:
    return library.get_upload(session, principal, upload_id)


@router.post(
    "/uploads/{upload_id}/parts",
    response_model=UploadPartUrls,
    **_policy(Capability.UPLOAD_MANAGE, _IMPLEMENTED),
)
def create_upload_part_urls(
    upload_id: ResourceId,
    body: UploadPartUrlsRequest,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.part_urls(session, principal, upload_id, body)


@router.put(
    "/uploads/{upload_id}/parts/{part_number}",
    response_model=UploadPartUrl,
    openapi_extra={
        "x-required-capability": Capability.UPLOAD_MANAGE.value,
        "x-implementation-status": _IMPLEMENTED.value,
        "requestBody": {"content": {"application/octet-stream": {"schema": {"type": "string"}}}},
    },
)
async def put_upload_part(
    request: Request, upload_id: ResourceId, part_number: Annotated[int, Path(ge=1)]
) -> Any:
    """Local object store only. Streams to disk, so a part never sits in process memory."""
    runtime = _library(request)
    store = runtime.store
    if store is None:
        raise ApiError(503, ErrorCode.SERVICE_UNAVAILABLE, "Object storage is not configured.")
    principal = current_principal(request)
    factory = runtime.identities.session_factory

    def prepare() -> int:
        with factory() as session:
            row = library.open_part_upload(session, principal, upload_id, part_number)
            return library.expected_part_size(row, part_number)

    expected = await run_in_threadpool(prepare)
    writer = store.begin_part(upload_id, part_number)
    try:
        async for chunk in request.stream():
            if writer.size_bytes + len(chunk) > expected:
                raise ApiError(
                    409, ErrorCode.UPLOAD_INCOMPLETE, "This part is larger than expected."
                )
            await run_in_threadpool(writer.write, chunk)
        if writer.size_bytes != expected:
            raise ApiError(
                409,
                ErrorCode.UPLOAD_INCOMPLETE,
                "This part ended early. Send it again.",
                {"expected_bytes": expected, "received_bytes": writer.size_bytes},
            )
    except BaseException:
        writer.discard()
        raise
    etag = await run_in_threadpool(writer.commit)

    def record() -> UploadPartUrl:
        with factory() as session:
            return library.record_part(session, upload_id, part_number, expected, etag)

    saved = await run_in_threadpool(record)
    return Response(
        content=saved.model_dump_json(),
        media_type="application/json",
        headers={"ETag": etag},
    )


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=UploadSession,
    **_policy(Capability.UPLOAD_MANAGE, _IMPLEMENTED),
)
def complete_upload(
    request: Request,
    upload_id: ResourceId,
    body: UploadCompleteRequest,
    idempotency_key: IdempotencyKey,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.complete_upload(_library(request), session, principal, upload_id, body)


@router.post(
    "/uploads/{upload_id}/abort",
    response_model=UploadSession,
    **_policy(Capability.UPLOAD_MANAGE, _IMPLEMENTED),
)
def abort_upload(
    request: Request, upload_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.abort_upload(_library(request), session, principal, upload_id)


# --- Alerts and devices -----------------------------------------------------------------------


@router.get("/alerts", response_model=AlertList, **_policy(Capability.ALERT_READ))
async def list_alerts(
    status: AlertStatus | None = None,
    severity: AlertSeverity | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.get(
    "/alerts/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
    **_policy(Capability.ALERT_READ),
)
async def stream_alerts() -> Any:
    raise _not_implemented()


@router.get("/alerts/{alert_id}", response_model=AlertDetail, **_policy(Capability.ALERT_READ))
async def get_alert(alert_id: ResourceId) -> Any:
    raise _not_implemented()


@router.post(
    "/alerts/{alert_id}/acknowledge",
    response_model=AlertAcknowledged,
    **_policy(Capability.ALERT_ACKNOWLEDGE),
)
async def acknowledge_alert(
    alert_id: ResourceId, body: AlertAcknowledgeRequest, idempotency_key: IdempotencyKey
) -> Any:
    raise _not_implemented()


@router.put(
    "/alerts/preferences",
    response_model=AlertPreferences,
    **_policy(Capability.ALERT_PREFERENCES),
)
async def update_alert_preferences(body: AlertPreferencesUpdate) -> Any:
    raise _not_implemented()


@router.post(
    "/devices", response_model=Device, status_code=201, **_policy(Capability.DEVICE_MANAGE)
)
async def register_device(body: DeviceRegistrationRequest) -> Any:
    raise _not_implemented()


@router.delete(
    "/devices/{device_id}",
    status_code=204,
    response_class=Response,
    response_model=None,
    **_policy(Capability.DEVICE_MANAGE),
)
async def revoke_device(device_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get(
    "/admin/alert-rules", response_model=AlertRuleList, **_policy(Capability.ADMIN_ALERT_RULES)
)
async def list_alert_rules(limit: Limit = 50, cursor: Cursor = None) -> Any:
    raise _not_implemented()


@router.put(
    "/admin/alert-rules", response_model=AlertRuleSaved, **_policy(Capability.ADMIN_ALERT_RULES)
)
async def save_alert_rule(body: AlertRuleUpsert) -> Any:
    raise _not_implemented()


# --- Source library and monitoring ------------------------------------------------------------


@router.get(
    "/sources",
    response_model=SourceConnectorList,
    **_policy(Capability.SOURCE_HEALTH_READ, _IMPLEMENTED),
)
def list_sources(
    principal: CurrentPrincipal, session: DbSession, limit: Limit = 50, cursor: Cursor = None
) -> Any:
    return library.list_sources(session, principal, limit, cursor)


@router.get(
    "/sources/{source_id}/health",
    response_model=SourceHealth,
    **_policy(Capability.SOURCE_HEALTH_READ, _IMPLEMENTED),
)
def get_source_health(
    source_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.source_health(session, principal, source_id)


@router.post(
    "/admin/sources/{source_id}/check",
    response_model=JobAccepted,
    status_code=202,
    **_policy(Capability.ADMIN_SOURCE_CHECK, _IMPLEMENTED),
)
def check_source(
    source_id: ResourceId,
    idempotency_key: IdempotencyKey,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.check_source(session, principal, source_id)


@router.get(
    "/source-publications",
    response_model=SourcePublicationList,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def list_source_publications(
    request: Request,
    principal: CurrentPrincipal,
    session: DbSession,
    source_id: Annotated[str | None, Query(max_length=128)] = None,
    issue: Annotated[str | None, Query(max_length=128)] = None,
    status: ObservationStatus | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    return library.list_publications(
        _library(request),
        session,
        principal,
        source_id=source_id,
        issue=issue,
        status=status,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/source-artifacts",
    response_model=SourceArtifactList,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def list_source_artifacts(
    request: Request,
    principal: CurrentPrincipal,
    session: DbSession,
    source_id: Annotated[str | None, Query(max_length=128)] = None,
    filename: Annotated[str | None, Query(max_length=512)] = None,
    sha256: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
    status: ArtifactStatus | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    return library.list_artifacts(
        _library(request),
        session,
        principal,
        source_id=source_id,
        filename=filename,
        sha256=sha256,
        status=status,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/source-artifacts/{artifact_id}",
    response_model=SourceArtifactDetail,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def get_source_artifact(
    request: Request, artifact_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.get_artifact(_library(request), request, session, principal, artifact_id)


@router.get(
    "/source-artifacts/{artifact_id}/integrity",
    response_model=ArtifactIntegrityReport,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def get_source_artifact_integrity(
    request: Request, artifact_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.get_integrity(_library(request), request, session, principal, artifact_id)


@router.get(
    "/source-artifacts/{artifact_id}/preview",
    response_model=SourcePreview,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def get_source_artifact_preview(
    request: Request,
    artifact_id: ResourceId,
    principal: CurrentPrincipal,
    session: DbSession,
    page: Annotated[int | None, Query(ge=1)] = None,
    table: Annotated[str | None, Query(max_length=256)] = None,
    row: Annotated[int | None, Query(ge=1)] = None,
    cursor: Cursor = None,
) -> Any:
    return library.get_preview(
        _library(request),
        request,
        session,
        principal,
        artifact_id,
        page=page,
        table=table,
        row=row,
        cursor=cursor,
    )


@router.get(
    "/source-artifacts/{artifact_id}/content",
    response_class=StreamingResponse,
    responses={200: {"content": {"application/octet-stream": {"schema": {"type": "string"}}}}},
    **_policy(Capability.SOURCE_DOWNLOAD, _IMPLEMENTED),
)
def download_source_artifact(
    request: Request, artifact_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    """Re-checks identity and entitlement on every call. The original bytes, unchanged."""
    artifact, content = library.open_artifact_content(
        _library(request), request, session, principal, artifact_id
    )

    def chunks() -> Iterator[bytes]:
        with content:
            while chunk := content.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(artifact.byte_length),
            "Content-Disposition": "attachment",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/source-artifacts/{artifact_id}/download-link",
    response_model=DownloadLink,
    **_policy(Capability.SOURCE_DOWNLOAD, _IMPLEMENTED),
)
def create_download_link(
    request: Request,
    artifact_id: ResourceId,
    body: DownloadLinkRequest,
    principal: CurrentPrincipal,
    session: DbSession,
) -> Any:
    return library.create_download_link(_library(request), request, session, principal, artifact_id)


@router.get(
    "/source-records",
    response_model=SourceRecordList,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def search_source_records(
    request: Request,
    principal: CurrentPrincipal,
    session: DbSession,
    query: Annotated[str | None, Query(max_length=256)] = None,
    station_number: Annotated[str | None, Query(max_length=64)] = None,
    frequency_start_mhz: FrequencyMhz = None,
    frequency_end_mhz: FrequencyMhz = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    return library.search_records(
        _library(request),
        session,
        principal,
        query_text=query,
        station_number=station_number,
        frequency_start_mhz=frequency_start_mhz,
        frequency_end_mhz=frequency_end_mhz,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/source-records/{source_record_id}",
    response_model=SourceRecordDetail,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def get_source_record(
    request: Request, source_record_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.get_record(_library(request), request, session, principal, source_record_id)


@router.get(
    "/source-records/{source_record_id}/source-location",
    response_model=SourceLocationDetail,
    **_policy(Capability.SOURCE_READ, _IMPLEMENTED),
)
def get_source_record_location(
    request: Request, source_record_id: ResourceId, principal: CurrentPrincipal, session: DbSession
) -> Any:
    return library.get_record_location(
        _library(request), request, session, principal, source_record_id
    )
