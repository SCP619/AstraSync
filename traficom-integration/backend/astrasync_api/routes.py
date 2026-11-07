"""REST API v1 surface (BSD sections 5, 6.4 and 9).

Every operation declares a required capability. Handlers return 501 until implemented: a route
must never answer with sample data.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, Response
from fastapi.responses import StreamingResponse

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
    UploadPartUrls,
    UploadPartUrlsRequest,
    UploadSession,
)
from .contract.permissions import Capability
from .errors import ApiError
from .security import require_authenticated_principal

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 422, 429, 500, 501)
}

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_authenticated_principal)],
    responses=_ERROR_RESPONSES,
)

ResourceId = Annotated[str, Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
Limit = Annotated[int, Query(ge=1, le=200)]
Cursor = Annotated[str | None, Query(max_length=1024)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=128)]
FrequencyMhz = Annotated[float | None, Query(ge=0, allow_inf_nan=False)]


def _policy(capability: Capability) -> dict[str, Any]:
    return {
        "openapi_extra": {
            "x-required-capability": capability.value,
            "x-implementation-status": ImplementationStatus.DESIGNED.value,
        }
    }


def _not_implemented() -> ApiError:
    return ApiError(501, ErrorCode.NOT_IMPLEMENTED, "This operation is not implemented yet.")


@router.get("/me", response_model=Me, **_policy(Capability.AUTHENTICATED))
async def get_me() -> Any:
    raise _not_implemented()


# --- Ingestion, jobs, issues ------------------------------------------------------------------


@router.post(
    "/ingest/ific",
    response_model=JobAccepted,
    status_code=202,
    **_policy(Capability.INGEST_TRIGGER),
)
async def ingest_ific(body: IngestRequest, idempotency_key: IdempotencyKey) -> Any:
    raise _not_implemented()


@router.get("/jobs/{job_id}", response_model=JobRun, **_policy(Capability.JOB_READ))
async def get_job(job_id: ResourceId) -> Any:
    raise _not_implemented()


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
    **_policy(Capability.UPLOAD_MANAGE),
)
async def create_upload(body: UploadCreateRequest, idempotency_key: IdempotencyKey) -> Any:
    raise _not_implemented()


@router.get("/uploads/{upload_id}", response_model=UploadSession, **_policy(Capability.JOB_READ))
async def get_upload(upload_id: ResourceId) -> Any:
    raise _not_implemented()


@router.post(
    "/uploads/{upload_id}/parts",
    response_model=UploadPartUrls,
    **_policy(Capability.UPLOAD_MANAGE),
)
async def create_upload_part_urls(upload_id: ResourceId, body: UploadPartUrlsRequest) -> Any:
    raise _not_implemented()


@router.post(
    "/uploads/{upload_id}/complete",
    response_model=UploadSession,
    **_policy(Capability.UPLOAD_MANAGE),
)
async def complete_upload(
    upload_id: ResourceId, body: UploadCompleteRequest, idempotency_key: IdempotencyKey
) -> Any:
    raise _not_implemented()


@router.post(
    "/uploads/{upload_id}/abort",
    response_model=UploadSession,
    **_policy(Capability.UPLOAD_MANAGE),
)
async def abort_upload(upload_id: ResourceId) -> Any:
    raise _not_implemented()


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
    "/sources", response_model=SourceConnectorList, **_policy(Capability.SOURCE_HEALTH_READ)
)
async def list_sources(limit: Limit = 50, cursor: Cursor = None) -> Any:
    raise _not_implemented()


@router.get(
    "/sources/{source_id}/health",
    response_model=SourceHealth,
    **_policy(Capability.SOURCE_HEALTH_READ),
)
async def get_source_health(source_id: ResourceId) -> Any:
    raise _not_implemented()


@router.post(
    "/admin/sources/{source_id}/check",
    response_model=JobAccepted,
    status_code=202,
    **_policy(Capability.ADMIN_SOURCE_CHECK),
)
async def check_source(source_id: ResourceId, idempotency_key: IdempotencyKey) -> Any:
    raise _not_implemented()


@router.get(
    "/source-publications",
    response_model=SourcePublicationList,
    **_policy(Capability.SOURCE_READ),
)
async def list_source_publications(
    source_id: Annotated[str | None, Query(max_length=128)] = None,
    issue: Annotated[str | None, Query(max_length=128)] = None,
    status: ObservationStatus | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.get(
    "/source-artifacts", response_model=SourceArtifactList, **_policy(Capability.SOURCE_READ)
)
async def list_source_artifacts(
    source_id: Annotated[str | None, Query(max_length=128)] = None,
    filename: Annotated[str | None, Query(max_length=512)] = None,
    sha256: Annotated[str | None, Query(pattern=r"^[0-9a-f]{64}$")] = None,
    status: ArtifactStatus | None = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.get(
    "/source-artifacts/{artifact_id}",
    response_model=SourceArtifactDetail,
    **_policy(Capability.SOURCE_READ),
)
async def get_source_artifact(artifact_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get(
    "/source-artifacts/{artifact_id}/integrity",
    response_model=ArtifactIntegrityReport,
    **_policy(Capability.SOURCE_READ),
)
async def get_source_artifact_integrity(artifact_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get(
    "/source-artifacts/{artifact_id}/preview",
    response_model=SourcePreview,
    **_policy(Capability.SOURCE_READ),
)
async def get_source_artifact_preview(
    artifact_id: ResourceId,
    page: Annotated[int | None, Query(ge=1)] = None,
    table: Annotated[str | None, Query(max_length=256)] = None,
    row: Annotated[int | None, Query(ge=1)] = None,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.post(
    "/source-artifacts/{artifact_id}/download-link",
    response_model=DownloadLink,
    **_policy(Capability.SOURCE_DOWNLOAD),
)
async def create_download_link(artifact_id: ResourceId, body: DownloadLinkRequest) -> Any:
    raise _not_implemented()


@router.get("/source-records", response_model=SourceRecordList, **_policy(Capability.SOURCE_READ))
async def search_source_records(
    query: Annotated[str | None, Query(max_length=256)] = None,
    station_number: Annotated[str | None, Query(max_length=64)] = None,
    frequency_start_mhz: FrequencyMhz = None,
    frequency_end_mhz: FrequencyMhz = None,
    limit: Limit = 50,
    cursor: Cursor = None,
) -> Any:
    raise _not_implemented()


@router.get(
    "/source-records/{source_record_id}",
    response_model=SourceRecordDetail,
    **_policy(Capability.SOURCE_READ),
)
async def get_source_record(source_record_id: ResourceId) -> Any:
    raise _not_implemented()


@router.get(
    "/source-records/{source_record_id}/source-location",
    response_model=SourceLocationDetail,
    **_policy(Capability.SOURCE_READ),
)
async def get_source_record_location(source_record_id: ResourceId) -> Any:
    raise _not_implemented()
