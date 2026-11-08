"""Canonical request/response models for the AstraSync REST API, version 1.

Rules enforced here so that a server bug fails closed instead of reaching a client:

* Unknown fields are rejected, so clients cannot supply ``tenant_id``, ``role`` or computed values.
* Missing values are ``null``, never zero. Non-finite numbers are rejected.
* A failed, skipped or ineligible method has no numeric value.
* A margin needs a verified criterion and matching conditions.
* Only commensurate method results can share a comparison group, so PFD and EPFD never do.

Units are part of field names: ``_mhz``, ``_hz``, ``_db``, ``_m``, ``_deg``, ``_utc``.
Storage-only locators (object URIs, secret references, checkpoints) are deliberately not exposed.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from . import SchemaVersion
from .enums import (
    AlertChannel,
    AlertDeliveryState,
    AlertEvidenceRequirement,
    AlertSeverity,
    AlertStatus,
    AlertTriggerKind,
    AnalysisStatus,
    ArtifactStatus,
    CaseDomain,
    ChangeType,
    ComparisonOperator,
    ComparisonStatus,
    CriterionApplicability,
    DevicePlatform,
    DeviceStatus,
    DiscoveryMode,
    DomainEventKind,
    DraftStatus,
    DraftType,
    Environment,
    ErrorCode,
    FindingStatus,
    IntegrityCheckResult,
    IssueDomain,
    JobType,
    MethodApplicability,
    MethodExecution,
    MethodRole,
    MetricKind,
    ObservationStatus,
    PipelineStatus,
    PublisherAuthStatus,
    PushCategory,
    QualitySeverity,
    RecordStatus,
    ReviewAction,
    ReviewStatus,
    SourceHealthStatus,
    SourceType,
    UsageClassification,
    ValidationStatus,
)
from .permissions import Capability, Role

MARGIN_TOLERANCE_DB = 1e-9


def _require_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must be UTC")
    return value.astimezone(UTC)


FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
NonNegativeFloat = Annotated[float, Field(allow_inf_nan=False, ge=0)]
PositiveFloat = Annotated[float, Field(allow_inf_nan=False, gt=0)]
Percentage = Annotated[float, Field(allow_inf_nan=False, ge=0, le=100)]
Latitude = Annotated[float, Field(allow_inf_nan=False, ge=-90, le=90)]
Longitude = Annotated[float, Field(allow_inf_nan=False, ge=-180, le=180)]
NonNegativeInt = Annotated[int, Field(ge=0)]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_require_utc)]
Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
StableId = Annotated[str, Field(min_length=1, max_length=128)]
StableCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$", max_length=64)]

T = TypeVar("T")


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Envelope(ContractModel):
    """Metadata on every top-level response."""

    schema_version: SchemaVersion
    generated_at_utc: UtcDatetime


class Page(Envelope, Generic[T]):
    """Cursor page. ``total_if_known`` stays null rather than holding a guessed total."""

    items: list[T]
    limit: Annotated[int, Field(ge=1, le=200)]
    next_cursor: str | None
    total_if_known: NonNegativeInt | None


# --- Errors -----------------------------------------------------------------------------------


class ApiErrorBody(ContractModel):
    code: ErrorCode
    message: str
    details: dict[str, Any]
    request_id: str


class ErrorResponse(ContractModel):
    error: ApiErrorBody


# --- Identity ---------------------------------------------------------------------------------


class Me(Envelope):
    user_id: StableId
    tenant_id: StableId
    environment: Environment
    roles: list[Role]
    capabilities: list[Capability]


# --- Issues and changes -----------------------------------------------------------------------


class SourceIssue(ContractModel):
    source_issue_id: StableId
    domain: IssueDomain
    publisher: str
    source_type: SourceType
    issue_number: str | None
    published_on: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    effective_from: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    content_sha256: Sha256Hex
    ingested_at_utc: UtcDatetime
    usage_classification: UsageClassification
    parser_version: str | None
    validation_status: ValidationStatus
    is_synthetic: bool


class IssueList(Page[SourceIssue]):
    pass


class NoticeChange(ContractModel):
    change_id: StableId
    previous_notice_uid: StableId | None
    current_notice_uid: StableId | None
    previous_issue_id: StableId | None
    current_issue_id: StableId
    change_type: ChangeType
    changed_fields: dict[str, Any]
    matching_strategy: str
    identity_confidence: Annotated[float, Field(allow_inf_nan=False, ge=0, le=1)] | None
    comparison_run_id: StableId


class NoticeChangeList(Page[NoticeChange]):
    pass


# --- Cases ------------------------------------------------------------------------------------


class MethodSummary(ContractModel):
    succeeded: NonNegativeInt
    candidates: NonNegativeInt

    @model_validator(mode="after")
    def _succeeded_within_candidates(self) -> MethodSummary:
        if self.succeeded > self.candidates:
            raise ValueError("succeeded cannot exceed candidates")
        return self


class LeadMetric(ContractModel):
    metric_kind: MetricKind | None
    numeric_value: FiniteFloat | None
    unit: str | None

    @model_validator(mode="after")
    def _value_is_labelled(self) -> LeadMetric:
        if self.numeric_value is not None and (self.metric_kind is None or self.unit is None):
            raise ValueError("a lead value needs a named metric and unit")
        return self


class CaseSummary(ContractModel):
    case_id: StableId
    is_synthetic: bool
    domain: CaseDomain
    notice_id: StableId
    source_issue_id: StableId
    administration: str | None
    change_type: ChangeType
    frequency_start_mhz: NonNegativeFloat
    frequency_end_mhz: NonNegativeFloat
    relevance_label: StableCode
    method_summary: MethodSummary
    lead_metric: LeadMetric
    margin_db: FiniteFloat | None
    criterion_status: CriterionApplicability | None
    finding_status: FindingStatus
    review_status: ReviewStatus

    @model_validator(mode="after")
    def _finding_is_supported(self) -> CaseSummary:
        if self.frequency_start_mhz > self.frequency_end_mhz:
            raise ValueError("frequency_start_mhz must not exceed frequency_end_mhz")
        verified = self.criterion_status is CriterionApplicability.VERIFIED
        if self.margin_db is not None and not verified:
            raise ValueError("margin_db requires a verified criterion")
        if self.finding_status is FindingStatus.POTENTIAL_LIMIT_EXCEEDANCE and (
            not verified or self.margin_db is None
        ):
            raise ValueError("potential limit exceedance requires a verified margin")
        return self


class CaseList(Page[CaseSummary]):
    pass


class RelevanceGates(ContractModel):
    """Separate gates. A frequency match alone never implies interference."""

    label: StableCode
    reason_codes: list[StableCode]
    rule_version: str | None
    overlap_start_mhz: NonNegativeFloat | None
    overlap_end_mhz: NonNegativeFloat | None
    frequency_match: bool
    service_match: bool | None
    geometry_match: bool | None
    technical_data_ready: bool | None
    criterion_available: bool | None


class EvidenceLink(ContractModel):
    evidence_id: StableId
    label: str
    entity_type: str
    entity_id: StableId
    source_issue_id: StableId | None
    reference_id: StableId | None
    source_locator: str
    sha256: Sha256Hex
    verified_at_utc: UtcDatetime | None
    note: str | None


class CaseDetail(CaseSummary, Envelope):
    """Method runs load from ``GET /analyses/{id}`` so values have one canonical source."""

    relevance: RelevanceGates
    evidence: list[EvidenceLink]
    latest_analysis_run_id: StableId | None
    priority: StableCode | None
    priority_reason: str | None
    owner: StableId | None
    reviewer_decision: ReviewAction | None
    created_at_utc: UtcDatetime
    updated_at_utc: UtcDatetime


# --- Analysis ---------------------------------------------------------------------------------


class MethodRun(ContractModel):
    """One row per candidate method per scenario, even when the method did not run (BSD 3.7)."""

    method_run_id: StableId
    analysis_run_id: StableId
    scenario_id: StableId
    method_id: StableCode
    method_version: str
    standard_ref_id: StableId | None
    role: MethodRole
    applicability: MethodApplicability
    execution_status: MethodExecution
    reason_codes: list[StableCode]
    missing_fields: list[str]
    metric_kind: MetricKind | None
    numeric_value: FiniteFloat | None
    unit: str | None
    reference_bandwidth_hz: PositiveFloat | None
    time_percentage: Percentage | None
    location_percentage: Percentage | None
    receiver_site_id: StableId | None
    satellite_epoch_utc: UtcDatetime | None
    inputs: dict[str, Any]
    assumptions: list[str]
    diagnostics: dict[str, Any]
    result_trace: dict[str, Any]
    implementation_sha: str | None
    calculation_sha256: Sha256Hex | None

    @model_validator(mode="after")
    def _status_matches_result(self) -> MethodRun:
        if self.execution_status is MethodExecution.SUCCEEDED:
            if self.applicability is not MethodApplicability.APPLICABLE:
                raise ValueError("only an applicable method can succeed")
            if self.numeric_value is None or self.metric_kind is None or self.unit is None:
                raise ValueError("a successful method needs a value, named metric and unit")
            if self.calculation_sha256 is None or self.implementation_sha is None:
                raise ValueError("a successful method needs replay fingerprints")
        elif self.numeric_value is not None:
            raise ValueError("numeric_value must be null unless the method succeeded")
        if (
            self.execution_status is MethodExecution.FAILED
            and self.applicability is not MethodApplicability.APPLICABLE
        ):
            raise ValueError("only an applicable method can fail in execution")
        if self.applicability is MethodApplicability.INSUFFICIENT_DATA and not self.missing_fields:
            raise ValueError("INSUFFICIENT_DATA must list missing_fields")
        if self.applicability in (
            MethodApplicability.NOT_APPLICABLE,
            MethodApplicability.NOT_IMPLEMENTED,
        ) and not self.reason_codes:
            raise ValueError("an ineligible method must give reason_codes")
        return self


class CriterionCitation(ContractModel):
    reference_id: StableId
    section_id: str
    source_url: str


class CriterionCheck(ContractModel):
    """Separate from the method run. Positive upper-bound margins are potential exceedances only."""

    criterion_check_id: StableId
    method_run_id: StableId
    criterion_ref_id: StableId | None
    regulatory_scope: str | None
    applicable: CriterionApplicability
    matching_conditions: dict[str, Any]
    limit_value: FiniteFloat | None
    limit_unit: str | None
    limit_reference_bandwidth_hz: PositiveFloat | None
    comparison_operator: ComparisonOperator | None
    margin_db: FiniteFloat | None
    comparison_status: ComparisonStatus
    review_note: str | None
    citation: CriterionCitation | None

    @model_validator(mode="after")
    def _margin_requires_verified_criterion(self) -> CriterionCheck:
        if self.margin_db is None:
            return self
        if self.applicable is not CriterionApplicability.VERIFIED:
            raise ValueError("margin_db requires a verified criterion")
        if self.citation is None or self.limit_value is None or self.limit_unit is None:
            raise ValueError("margin_db requires a cited limit with a unit")
        if self.comparison_operator is not ComparisonOperator.UPPER_BOUND:
            raise ValueError("only upper-bound margins have a documented sign convention")
        if self.comparison_status is not ComparisonStatus.COMPARED:
            raise ValueError("margin_db requires comparison_status COMPARED")
        return self


class AnalysisRun(Envelope):
    """Immutable: a rerun creates a new ``analysis_run_id``."""

    analysis_run_id: StableId
    case_id: StableId
    scenario_id: StableId
    is_synthetic: bool
    run_created_at_utc: UtcDatetime
    input_snapshot_sha256: Sha256Hex
    software_commit_sha: str
    method_registry_version: str
    reference_snapshot_sha256: Sha256Hex | None
    analysis_status: AnalysisStatus
    created_by: StableId
    method_runs: list[MethodRun]
    criterion_checks: list[CriterionCheck]

    @model_validator(mode="after")
    def _margins_match_their_method(self) -> AnalysisRun:
        runs = {run.method_run_id: run for run in self.method_runs}
        for check in self.criterion_checks:
            if check.method_run_id not in runs:
                raise ValueError("criterion check references an unknown method run")
            if check.margin_db is None:
                continue
            run = runs[check.method_run_id]
            if run.numeric_value is None or run.unit != check.limit_unit:
                raise ValueError("margin_db requires a result in the same unit as the limit")
            if run.reference_bandwidth_hz != check.limit_reference_bandwidth_hz:
                raise ValueError("margin_db requires the same reference bandwidth as the limit")
            limit = check.limit_value
            if limit is None or not math.isclose(
                check.margin_db, run.numeric_value - limit, abs_tol=MARGIN_TOLERANCE_DB
            ):
                raise ValueError("upper-bound margin_db must equal predicted minus limit")
        return self


class AnalysisAccepted(Envelope):
    analysis_run_id: StableId
    job_id: StableId


class AnalyseRequest(ContractModel):
    scenario_id: StableId | None = None


class ComparisonGroup(ContractModel):
    group_id: StableId
    metric_kind: MetricKind
    method_run_ids: Annotated[list[StableId], Field(min_length=2)]
    preferred_method_run_id: StableId | None
    preferred_reason: str | None

    @model_validator(mode="after")
    def _preferred_has_reason(self) -> ComparisonGroup:
        if self.preferred_method_run_id is not None and not self.preferred_reason:
            raise ValueError("a preferred method needs a stated reason")
        return self


class MethodMatrix(Envelope):
    analysis_run_id: StableId
    is_synthetic: bool
    method_runs: list[MethodRun]
    comparison_groups: list[ComparisonGroup]

    @model_validator(mode="after")
    def _groups_are_commensurate(self) -> MethodMatrix:
        runs = {run.method_run_id: run for run in self.method_runs}
        for group in self.comparison_groups:
            conditions: set[tuple[Any, ...]] = set()
            for run_id in group.method_run_ids:
                run = runs.get(run_id)
                if run is None or run.execution_status is not MethodExecution.SUCCEEDED:
                    raise ValueError("comparison groups may only contain successful method runs")
                if run.metric_kind is not group.metric_kind:
                    raise ValueError("comparison group members must share one metric kind")
                conditions.add(
                    (
                        run.scenario_id,
                        run.unit,
                        run.reference_bandwidth_hz,
                        run.time_percentage,
                        run.location_percentage,
                        run.receiver_site_id,
                    )
                )
            if len(conditions) > 1:
                raise ValueError("comparison group members must share units and conditions")
            preferred = group.preferred_method_run_id
            if preferred is not None and preferred not in group.method_run_ids:
                raise ValueError("preferred method must belong to the group")
        return self


# --- Drafts and review ------------------------------------------------------------------------


class DraftCreateRequest(ContractModel):
    draft_type: DraftType
    analysis_run_id: StableId


class Draft(Envelope):
    draft_id: StableId
    case_id: StableId
    draft_type: DraftType
    source_analysis_run_id: StableId
    content_markdown: str
    citations: list[StableId]
    warnings: list[str]
    ai_model_id: str | None
    generation_provenance: str
    status: DraftStatus
    requires_human_review: Literal[True]
    created_at_utc: UtcDatetime


class DraftCreated(Draft):
    """A new draft is always unapproved. Only a review event can change that."""

    status: Literal[DraftStatus.DRAFT]


class DraftUpdateRequest(ContractModel):
    """Text only: an edit cannot change status or citations, so it can never approve."""

    content_markdown: Annotated[str, Field(min_length=1, max_length=200_000)]


class DraftList(Page[Draft]):
    pass


class ReviewCreateRequest(ContractModel):
    action: ReviewAction
    decision_reason: Annotated[str, Field(min_length=1, max_length=4000)]
    analysis_run_id: StableId | None = None
    draft_id: StableId | None = None

    @model_validator(mode="after")
    def _draft_action_names_draft(self) -> ReviewCreateRequest:
        if self.action in (ReviewAction.APPROVE_DRAFT, ReviewAction.REJECT_DRAFT) and (
            self.draft_id is None
        ):
            raise ValueError("a draft decision must name draft_id")
        return self


class ReviewEvent(Envelope):
    """Append-only. The actor comes from the validated identity, never the request."""

    review_event_id: StableId
    case_id: StableId
    actor_id: StableId
    action: ReviewAction
    decision_reason: str
    analysis_run_id: StableId | None
    draft_id: StableId | None
    occurred_at_utc: UtcDatetime


class ReviewEventList(Page[ReviewEvent]):
    pass


class EvidencePack(Envelope):
    case_id: StableId
    is_synthetic: bool
    evidence: list[EvidenceLink]
    analysis_runs: list[AnalysisRun]
    drafts: list[Draft]
    review_events: list[ReviewEvent]


class ReferenceDocument(ContractModel):
    reference_id: StableId
    authority: str
    document_title: str
    edition: str | None
    publication_date: str | None
    effective_date: str | None
    source_url: str | None
    snapshot_sha256: Sha256Hex | None
    section_id: str | None
    reviewed_by: StableId | None
    last_verified_at_utc: UtcDatetime | None
    usage_classification: UsageClassification


class ReferenceList(Page[ReferenceDocument]):
    pass


# --- Uploads and jobs -------------------------------------------------------------------------


class UploadCreateRequest(ContractModel):
    """``content_sha256`` is a digest supplied with a manifest. It is never publisher proof."""

    source_id: StableId
    source_type: SourceType
    usage_classification: UsageClassification
    filename_original: Annotated[str, Field(min_length=1, max_length=512)]
    expected_size_bytes: Annotated[int, Field(gt=0)]
    content_sha256: Sha256Hex | None = None


class UploadPartState(ContractModel):
    part_number: Annotated[int, Field(ge=1)]
    size_bytes: NonNegativeInt
    etag: str | None
    received: bool


class UploadSession(Envelope):
    upload_id: StableId
    status: PipelineStatus
    source_type: SourceType
    usage_classification: UsageClassification
    filename_original: str
    expected_size_bytes: NonNegativeInt
    received_size_bytes: NonNegativeInt
    part_size_bytes: Annotated[int, Field(gt=0)]
    max_size_bytes: Annotated[int, Field(gt=0)]
    parts: list[UploadPartState]
    content_sha256: Sha256Hex | None
    job_id: StableId | None
    failure_code: ErrorCode | None
    created_at_utc: UtcDatetime
    expires_at_utc: UtcDatetime
    completed_at_utc: UtcDatetime | None


class UploadPartUrlsRequest(ContractModel):
    part_numbers: Annotated[list[Annotated[int, Field(ge=1)]], Field(min_length=1, max_length=100)]


class UploadPartUrl(ContractModel):
    part_number: Annotated[int, Field(ge=1)]
    url: str
    expires_at_utc: UtcDatetime


class UploadPartUrls(Envelope):
    upload_id: StableId
    parts: list[UploadPartUrl]


class UploadCompletedPart(ContractModel):
    part_number: Annotated[int, Field(ge=1)]
    etag: Annotated[str, Field(min_length=1)]


class UploadCompleteRequest(ContractModel):
    """The server hashes the final assembled bytes; the client digest is only compared to it."""

    parts: Annotated[list[UploadCompletedPart], Field(min_length=1)]
    content_sha256: Sha256Hex


class IngestRequest(ContractModel):
    """Refers to an already staged artifact. Arbitrary URLs and paths are not accepted."""

    artifact_id: StableId
    source_type: SourceType


class JobRun(Envelope):
    """Progress is bytes, records and stage. There is no percent field to invent."""

    job_id: StableId
    job_type: JobType
    resource_id: StableId | None
    status: PipelineStatus
    progress_stage: str | None
    processed_bytes: NonNegativeInt | None
    processed_records: NonNegativeInt | None
    total_records_if_known: NonNegativeInt | None
    attempt: Annotated[int, Field(ge=0)]
    max_attempts: Annotated[int, Field(ge=1)]
    started_at_utc: UtcDatetime | None
    finished_at_utc: UtcDatetime | None
    error_code: ErrorCode | None


class JobAccepted(Envelope):
    job_id: StableId
    status: PipelineStatus


# --- Source library ---------------------------------------------------------------------------


class SourceConnector(ContractModel):
    """Connector status for clients. Endpoint and credential references stay server-side."""

    source_id: StableId
    publisher: str
    domain: IssueDomain
    source_type: SourceType
    discovery_mode: DiscoveryMode
    rights_basis: str
    usage_classification: UsageClassification
    poll_interval_seconds: Annotated[int, Field(gt=0)] | None
    last_checked_at_utc: UtcDatetime | None
    last_success_at_utc: UtcDatetime | None
    status: SourceHealthStatus
    is_synthetic: bool


class SourceConnectorList(Page[SourceConnector]):
    pass


SourceRight = Literal["READ", "DOWNLOAD", "IMPORT"]


class AdminEntitlement(ContractModel):
    """A source entitlement. Its classification is the source's, set by the server."""

    grant_id: StableId
    object_type: Literal["source"]
    object_id: StableId
    classification: UsageClassification
    rights: list[SourceRight]
    expires_at_utc: UtcDatetime | None


class AdminUser(ContractModel):
    user_id: StableId
    issuer: Annotated[str, Field(min_length=1, max_length=512)]
    oidc_subject: Annotated[str, Field(min_length=1, max_length=255)]
    active: bool
    roles: list[Role]
    sessions_revoked_before_utc: UtcDatetime | None
    last_verified_at_utc: UtcDatetime | None


class AdminUserList(Page[AdminUser]):
    pass


class AdminUserDetail(Envelope):
    """A user in the administrator's tenant with what the server would grant them now."""

    user: AdminUser
    effective_capabilities: list[Capability]
    entitlements: list[AdminEntitlement]


class AdminUserCreateRequest(ContractModel):
    """Provisions an identity in the administrator's own tenant. Issuer plus subject is the key;
    an email address is never used as the identity."""

    issuer: Annotated[str, Field(min_length=1, max_length=512, pattern=r"^https?://\S+$")]
    oidc_subject: Annotated[str, Field(min_length=1, max_length=255)]
    roles: Annotated[list[Role], Field(max_length=4)]


class AdminRolesUpdate(ContractModel):
    roles: Annotated[list[Role], Field(max_length=4)]


class AdminStatusUpdate(ContractModel):
    active: bool


class AdminEntitlementGrantRequest(ContractModel):
    source_id: StableId
    rights: Annotated[list[SourceRight], Field(min_length=1, max_length=3)]
    expires_at_utc: UtcDatetime | None = None


class IficAnalysis(ContractModel):
    """One analysed IFIC issue (DECISIONS G27). Priority is for ordering work, not a finding."""

    analysis_id: StableId
    source_id: StableId
    artifact_id: StableId
    previous_artifact_id: StableId | None
    kind: SourceType
    issue: NonNegativeInt
    rule_version: str
    status: str
    findings_count: NonNegativeInt
    cases_created: NonNegativeInt
    findings_sha256: Sha256Hex | None
    summary: dict[str, Any]
    created_at_utc: UtcDatetime


class IficAnalysisList(Page[IficAnalysis]):
    pass


class IficFinding(ContractModel):
    """One screened notice. ``detail`` holds every stage result, calculation and assumption."""

    rank: Annotated[int, Field(ge=1)]
    notice_id: StableId
    domain: CaseDomain
    administration: str | None
    label: str | None
    change_type: str
    priority_score: int
    priority_tier: str
    finding_status: str
    max_value: float | None
    max_value_unit: str | None
    detail: dict[str, Any]


class IficFindingList(Page[IficFinding]):
    analysis_id: StableId


class QueueBacklog(ContractModel):
    lane: Annotated[str, Field(min_length=1, max_length=32)]
    status: StableCode
    count: NonNegativeInt
    oldest_age_seconds: Annotated[float, Field(ge=0)] | None


class RecordStoreUsage(ContractModel):
    enabled: bool
    datasets: NonNegativeInt
    records: NonNegativeInt
    bytes: NonNegativeInt


class OperationsMetrics(Envelope):
    """Tenant-scoped counts for operators (TR-NFR-004/009). No payloads or error details."""

    tenant_id: StableId
    queues: list[QueueBacklog]
    failed_jobs_last_24h: NonNegativeInt
    outbox_pending: NonNegativeInt
    record_store: RecordStoreUsage


class SourceHealth(Envelope):
    source_id: StableId
    status: SourceHealthStatus
    discovery_mode: DiscoveryMode
    latest_known_issue_key: str | None
    last_checked_at_utc: UtcDatetime | None
    last_success_at_utc: UtcDatetime | None
    expected_cadence_seconds: Annotated[int, Field(gt=0)] | None
    pending_index_jobs: NonNegativeInt
    failure_code: ErrorCode | None
    failure_summary: str | None


class SourcePublication(ContractModel):
    publication_id: StableId
    source_id: StableId
    provider_issue_key: str
    provider_version: str | None
    published_at_utc: UtcDatetime | None
    first_seen_at_utc: UtcDatetime
    last_seen_at_utc: UtcDatetime
    remote_size_bytes: NonNegativeInt | None
    observation_status: ObservationStatus
    is_synthetic: bool


class SourcePublicationList(Page[SourcePublication]):
    pass


class SourceArtifact(ContractModel):
    artifact_id: StableId
    source_id: StableId
    publication_id: StableId | None
    filename_original: str
    artifact_type: str
    raw_sha256: Sha256Hex
    expected_digest: Sha256Hex | None
    expected_digest_origin: str | None
    publisher_auth_status: PublisherAuthStatus
    byte_length: NonNegativeInt
    revision: Annotated[int, Field(ge=1)]
    usage_classification: UsageClassification
    status: ArtifactStatus
    analysis_eligible: bool
    published_at_utc: UtcDatetime | None
    first_seen_at_utc: UtcDatetime
    download_completed_at_utc: UtcDatetime | None
    indexed_at_utc: UtcDatetime | None
    parser_version: str | None
    is_synthetic: bool

    @model_validator(mode="after")
    def _trust_and_eligibility_are_earned(self) -> SourceArtifact:
        if (
            self.publisher_auth_status is PublisherAuthStatus.VERIFIED_PUBLISHER
            and not self.expected_digest_origin
        ):
            raise ValueError("VERIFIED_PUBLISHER requires a recorded digest origin")
        if self.analysis_eligible and self.status not in (
            ArtifactStatus.INDEXED,
            ArtifactStatus.INDEXED_WITH_WARNINGS,
        ):
            raise ValueError("only an indexed artifact can be analysis eligible")
        if self.analysis_eligible and self.publisher_auth_status is PublisherAuthStatus.MISMATCH:
            raise ValueError("an artifact with a digest mismatch cannot be analysis eligible")
        return self


class SourceArtifactDetail(SourceArtifact, Envelope):
    pass


class SourceArtifactList(Page[SourceArtifact]):
    pass


class ArtifactIntegrityCheck(ContractModel):
    check_id: StableId
    check_type: str
    value_expected: str | None
    value_observed: str | None
    trust_level: PublisherAuthStatus | None
    result: IntegrityCheckResult
    tool_version: str
    checked_at_utc: UtcDatetime
    diagnostic: str | None


class RowReconciliation(ContractModel):
    parsed: NonNegativeInt
    accepted: NonNegativeInt
    flagged: NonNegativeInt
    rejected: NonNegativeInt


class ArtifactIntegrityReport(Envelope):
    artifact_id: StableId
    raw_sha256: Sha256Hex
    byte_length: NonNegativeInt
    publisher_auth_status: PublisherAuthStatus
    status: ArtifactStatus
    checks: list[ArtifactIntegrityCheck]
    row_reconciliation: RowReconciliation | None
    is_synthetic: bool


class SourceLocation(ContractModel):
    source_record_id: StableId | None
    artifact_id: StableId
    raw_sha256: Sha256Hex
    source_table_or_sheet: str | None
    source_row_or_key: str | None
    source_page: Annotated[int, Field(ge=1)] | None
    notice_id: str | None
    raw_record_sha256: Sha256Hex | None
    parser_version: str | None
    record_schema_version: str | None
    is_synthetic: bool


class SourceLocationDetail(SourceLocation, Envelope):
    pass


class SourcePreviewRow(ContractModel):
    location: SourceLocation
    cells: dict[str, str | None]


class SourcePreview(Envelope):
    """A bounded read-only slice of the original. It never carries the whole archive."""

    artifact_id: StableId
    rows: list[SourcePreviewRow]
    next_cursor: str | None
    is_synthetic: bool


class DownloadLinkRequest(ContractModel):
    """The client must confirm it warned the user about a potentially multi-GB transfer."""

    acknowledge_transfer_size: Literal[True]


class DownloadLink(Envelope):
    artifact_id: StableId
    url: str
    expires_at_utc: UtcDatetime
    byte_length: NonNegativeInt
    raw_sha256: Sha256Hex


class SourceRecordHit(ContractModel):
    source_record_id: StableId
    source_id: StableId
    artifact_id: StableId
    issue_key: str | None
    publisher: str
    filename_original: str
    station_number: str | None
    network_id: str | None
    administration: str | None
    frequency_start_mhz: NonNegativeFloat | None
    frequency_end_mhz: NonNegativeFloat | None
    classification: UsageClassification
    record_status: RecordStatus
    is_synthetic: bool

    @model_validator(mode="after")
    def _frequency_order(self) -> SourceRecordHit:
        start, end = self.frequency_start_mhz, self.frequency_end_mhz
        if start is not None and end is not None and start > end:
            raise ValueError("frequency_start_mhz must not exceed frequency_end_mhz")
        return self


class SourceRecordList(Page[SourceRecordHit]):
    pass


class FrequencyReferenceMatch(ContractModel):
    """One Finnish reference interval that a screened range overlaps. A screening signal only."""

    source_record_id: StableId
    source_id: StableId
    artifact_id: StableId
    reference_kind: Literal["M4_ALLOCATION", "SPECIAL_INTEREST_STATION"]
    reference_field: Literal["SUB_BAND", "TX_FREQUENCY", "RX_FREQUENCY"]
    # How the reference interval was formed. Station intervals are an assumption, named here.
    interval_basis: StableCode
    reference_start_mhz: NonNegativeFloat
    reference_end_mhz: NonNegativeFloat
    overlap_start_mhz: NonNegativeFloat
    overlap_end_mhz: NonNegativeFloat
    label: str | None
    is_synthetic: bool


class ScreenedReferenceSource(ContractModel):
    source_id: StableId
    source_type: str
    artifact_id: StableId
    revision: int
    is_synthetic: bool


class FrequencyRelevanceScreen(Envelope):
    """Stage one of TR-REL-004 (frequency). Service, geometry and technical stages stay null."""

    query_start_mhz: NonNegativeFloat
    query_end_mhz: NonNegativeFloat
    gates: RelevanceGates
    matches: list[FrequencyReferenceMatch]
    matches_truncated: bool
    sources_screened: list[ScreenedReferenceSource]
    is_synthetic: bool


class RecordQualityFinding(ContractModel):
    finding_id: StableId
    source_record_id: StableId
    field_key: str
    raw_value: str | None
    normalized_value: str | None
    rule_id: StableCode
    severity: QualitySeverity
    status: str
    reviewer_override_id: StableId | None


STATION_FIELDS_ADDED_LATER = (
    "effective_bandwidth_hz",
    "effective_bandwidth_rule",
    "licence_class_normalized",
)


class ReferenceStationRecord(ContractModel):
    """Normalized national reference row. Unknown values are null, never zero or a guessed unit."""

    source_record_id: StableId
    station_number_raw: str | None
    licence_class_code: str | None
    longitude_deg: Longitude | None
    latitude_deg: Latitude | None
    ground_elevation_m: FiniteFloat | None
    mast_height_m: FiniteFloat | None
    antenna_height_agl_m: FiniteFloat | None
    antenna_height_asl_m: FiniteFloat | None
    antenna_gain_db: FiniteFloat | None
    tx_frequency_hz: PositiveFloat | None
    rx_frequency_hz: PositiveFloat | None
    channel_bandwidth_hz: PositiveFloat | None
    emission_bandwidth_hz: PositiveFloat | None
    # Screening bandwidth beside the raw widths: the smaller valid value on a mismatch (C3).
    effective_bandwidth_hz: PositiveFloat | None
    effective_bandwidth_rule: str | None
    # Published licence class if known (BC, BT, FX, MVV, MUUT), otherwise MUUT; raw kept above.
    # Null for records parsed before these fields existed.
    licence_class_normalized: str | None
    polarization_code: str | None
    radiation_power_value: FiniteFloat | None
    radiation_power_unit: str | None
    radiation_power_itu_code_raw: str | None
    transmission_line_db: FiniteFloat | None
    directivity_code: str | None
    is_synthetic: bool
    parse_status: RecordStatus


class SourceRecordDetail(Envelope):
    """Original values beside their interpretation, for the indexed-record view."""

    source_record_id: StableId
    location: SourceLocation
    record_status: RecordStatus
    field_aliases: dict[str, list[str]]
    raw_fields: dict[str, str | None]
    reference_station: ReferenceStationRecord | None
    quality_findings: list[RecordQualityFinding]
    analysis_eligibility: dict[str, RecordStatus]
    is_synthetic: bool


# --- Alerts and devices -----------------------------------------------------------------------


class AlertSummary(ContractModel):
    """Inbox item. Severity is an operational priority, not a legal status."""

    alert_id: StableId
    event_id: StableId
    case_id: StableId | None
    rule_id: StableId
    rule_version: Annotated[int, Field(ge=1)]
    severity: AlertSeverity
    safe_title: str
    safe_preview: str
    status: AlertStatus
    created_at_utc: UtcDatetime
    expires_at_utc: UtcDatetime | None
    is_synthetic: bool


class AlertList(Page[AlertSummary]):
    pass


class AlertDelivery(ContractModel):
    delivery_id: StableId
    channel: AlertChannel
    attempt: Annotated[int, Field(ge=1)]
    state: AlertDeliveryState
    last_attempt_at_utc: UtcDatetime | None
    delivered_at_utc: UtcDatetime | None
    failure_code: str | None


class AlertAcknowledgment(ContractModel):
    ack_id: StableId
    alert_id: StableId
    actor_id: StableId
    comment: str | None
    acknowledged_at_utc: UtcDatetime


class AlertDetail(AlertSummary, Envelope):
    evidence_refs: list[StableId]
    deliveries: list[AlertDelivery]
    acknowledgments: list[AlertAcknowledgment]


class AlertAcknowledgeRequest(ContractModel):
    comment: Annotated[str, Field(max_length=2000)] | None = None


class AlertAcknowledged(AlertAcknowledgment, Envelope):
    pass


class AlertPreferencesUpdate(ContractModel):
    enabled_channels: list[AlertChannel]
    quiet_hours_start_utc: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quiet_hours_end_utc: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class AlertPreferences(Envelope):
    enabled_channels: list[AlertChannel]
    quiet_hours_start_utc: str | None
    quiet_hours_end_utc: str | None


class DeviceRegistrationRequest(ContractModel):
    """The push token is write-only: it never appears in a response."""

    platform: DevicePlatform
    push_token: Annotated[str, Field(min_length=1, max_length=4096)]


class Device(Envelope):
    device_id: StableId
    platform: DevicePlatform
    status: DeviceStatus
    last_seen_at_utc: UtcDatetime | None


class AlertRuleUpsert(ContractModel):
    rule_id: StableId | None = None
    trigger_kind: AlertTriggerKind
    severity: AlertSeverity
    enabled: bool
    evidence_requirement: AlertEvidenceRequirement
    routing_roles: Annotated[list[Role], Field(min_length=1)]
    dedupe_window_seconds: Annotated[int, Field(ge=0)]
    ack_timeout_seconds: Annotated[int, Field(gt=0)] | None = None
    escalation_policy: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _exceedance_needs_verified_gate(self) -> AlertRuleUpsert:
        if (
            self.trigger_kind is AlertTriggerKind.POTENTIAL_EXCEEDANCE
            and self.evidence_requirement
            is not AlertEvidenceRequirement.VERIFIED_CRITERION_AND_METHOD_RUN
        ):
            raise ValueError("exceedance alerts require a verified criterion and method run")
        return self


class AlertRule(ContractModel):
    rule_id: StableId
    version: Annotated[int, Field(ge=1)]
    trigger_kind: AlertTriggerKind
    severity: AlertSeverity
    enabled: bool
    evidence_requirement: AlertEvidenceRequirement
    routing_roles: list[Role]
    dedupe_window_seconds: NonNegativeInt
    ack_timeout_seconds: Annotated[int, Field(gt=0)] | None
    escalation_policy: dict[str, Any]


class AlertRuleList(Page[AlertRule]):
    pass


class AlertRuleSaved(AlertRule, Envelope):
    pass


# --- Non-REST integration payloads, published in the OpenAPI components -----------------------


class AdapterQualityFinding(ContractModel):
    field_key: str
    raw_value: str | None
    normalized_value: str | None
    rule_id: StableCode
    severity: QualitySeverity


class AdapterRecord(ContractModel):
    """One record from ``SourceAdapter.iter_record_batches``, validated at the worker boundary.

    ``raw_fields`` holds original values as text. Normalized values are nullable: an unknown
    unit stays null with a quality finding, and is never guessed.
    """

    source_table_or_sheet: str | None
    source_row_or_key: str | None
    source_page: Annotated[int, Field(ge=1)] | None
    notice_id: str | None
    issue_key: str | None
    station_number: str | None
    network_id: str | None
    administration: str | None
    frequency_start_mhz: NonNegativeFloat | None
    frequency_end_mhz: NonNegativeFloat | None
    record_status: RecordStatus
    schema_version: str
    raw_fields: dict[str, str | None]
    field_aliases: dict[str, list[str]]
    analysis_eligibility: dict[str, RecordStatus]
    quality_findings: list[AdapterQualityFinding]
    reference_station: dict[str, Any] | None

    @model_validator(mode="after")
    def _frequency_order(self) -> AdapterRecord:
        start, end = self.frequency_start_mhz, self.frequency_end_mhz
        if start is not None and end is not None and start > end:
            raise ValueError("frequency_start_mhz must not exceed frequency_end_mhz")
        return self


class CaseCandidate(ContractModel):
    """Passed to ``cases.upsert_candidate`` by the relevance pipeline, one per notice version."""

    case_id: StableId | None = None
    notice_uid: StableId
    notice_id: StableId
    source_id: StableId
    source_issue_id: StableId
    source_record_id: StableId | None = None
    administration: str | None = None
    domain: CaseDomain
    change_type: ChangeType
    frequency_start_mhz: NonNegativeFloat
    frequency_end_mhz: NonNegativeFloat
    relevance: RelevanceGates
    scenario_id: StableId
    scenario: dict[str, Any]

    @model_validator(mode="after")
    def _frequency_order(self) -> CaseCandidate:
        if self.frequency_start_mhz > self.frequency_end_mhz:
            raise ValueError("frequency_start_mhz must not exceed frequency_end_mhz")
        return self


class PushPayload(ContractModel):
    """All an OS notification may carry. Details are fetched only after re-authorization."""

    alert_id: StableId
    category: PushCategory
    created_at_utc: UtcDatetime


class DomainEvent(ContractModel):
    """Immutable event written to the outbox and consumed by the versioned alert rules."""

    schema_version: SchemaVersion
    event_id: StableId
    event_kind: DomainEventKind
    tenant_id: StableId
    occurred_at_utc: UtcDatetime
    correlation_id: StableId
    resource_type: str
    resource_id: StableId
    dedupe_key: str
    payload: dict[str, Any]


class MethodAssessment(ContractModel):
    """What ``RFMethod.assess_applicability`` must return, validated at the worker boundary."""

    method_id: StableCode
    method_version: str
    applicability: MethodApplicability
    reason_codes: list[StableCode]
    missing_fields: list[str]
    metric_kind: MetricKind | None


class MethodCalculation(ContractModel):
    """What ``RFMethod.calculate`` must return, validated at the worker boundary."""

    method_id: StableCode
    method_version: str
    metric_kind: MetricKind
    numeric_value: FiniteFloat
    unit: str
    reference_bandwidth_hz: PositiveFloat | None
    time_percentage: Percentage | None
    location_percentage: Percentage | None
    inputs: dict[str, Any]
    assumptions: list[str]
    diagnostics: dict[str, Any]
    result_trace: dict[str, Any]
    implementation_sha: str
    calculation_sha256: Sha256Hex


class AgentDraftResponse(ContractModel):
    """Structured agent output. The server still validates citations before using it."""

    draft_type: DraftType
    analysis_run_id: StableId
    explanation_markdown: str
    uncertainties: list[str]
    cited_evidence_ids: list[StableId]
    draft_markdown: str
    requires_human_review: Literal[True]
