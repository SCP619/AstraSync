// Shared API client for Windows, Android and the web preview. The server stays authoritative:
// this client never decides permissions or results.
import type { components } from "./schema.gen";

export type Schemas = components["schemas"];
export type ErrorCode = Schemas["ErrorCode"];
export type Me = Schemas["Me"];
export type CaseList = Schemas["CaseList"];
export type SourceRecordList = Schemas["SourceRecordList"];

export interface CaseFilters {
  query?: string;
  domain?: Schemas["CaseDomain"];
  change_type?: Schemas["ChangeType"];
  finding_status?: Schemas["FindingStatus"];
  review_status?: Schemas["ReviewStatus"];
  sort?: Schemas["CaseSort"];
}

export interface RecordSearch {
  query?: string;
  station_number?: string;
  frequency_start_mhz?: number;
  frequency_end_mhz?: number;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: ErrorCode | "NETWORK_ERROR" | "INVALID_RESPONSE",
    message: string,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  getAccessToken: () => string | null;
  /** Called on a 401: the session is no longer valid and the user must sign in again. */
  onUnauthenticated: (error: ApiError) => void;
  fetch?: typeof fetch;
}

export interface ApiClient {
  getMe(signal?: AbortSignal): Promise<Me>;
  listCases(filters?: CaseFilters, cursor?: string, signal?: AbortSignal): Promise<CaseList>;
  getCase(caseId: string, signal?: AbortSignal): Promise<Schemas["CaseDetail"]>;
  getAnalysis(runId: string, signal?: AbortSignal): Promise<Schemas["AnalysisRun"]>;
  requestAnalysis(caseId: string): Promise<Schemas["AnalysisAccepted"]>;
  listDrafts(caseId: string, signal?: AbortSignal): Promise<Schemas["DraftList"]>;
  createDraft(
    caseId: string,
    draftType: Schemas["DraftType"],
    analysisRunId: string,
  ): Promise<Schemas["DraftCreated"]>;
  updateDraft(caseId: string, draftId: string, content: string): Promise<Schemas["Draft"]>;
  listReviews(caseId: string, signal?: AbortSignal): Promise<Schemas["ReviewEventList"]>;
  createReview(caseId: string, body: Schemas["ReviewCreateRequest"]): Promise<Schemas["ReviewEvent"]>;
  exportCase(caseId: string): Promise<Schemas["EvidencePack"]>;
  listAlerts(
    status?: Schemas["AlertStatus"],
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<Schemas["AlertList"]>;
  getAlert(alertId: string, signal?: AbortSignal): Promise<Schemas["AlertDetail"]>;
  acknowledgeAlert(alertId: string): Promise<Schemas["AlertAcknowledged"]>;
  getAlertPreferences(signal?: AbortSignal): Promise<Schemas["AlertPreferences"]>;
  updateAlertPreferences(body: Schemas["AlertPreferencesUpdate"]): Promise<Schemas["AlertPreferences"]>;
  registerDevice(platform: Schemas["DevicePlatform"], pushToken: string): Promise<Schemas["Device"]>;
  /** Reads Server-Sent Events until the connection ends. Uses fetch to keep the token in a header. */
  streamAlerts(
    onAlert: (alert: Schemas["AlertSummary"]) => void,
    signal: AbortSignal,
    onSessionEnded?: () => void,
  ): Promise<void>;
  listSources(signal?: AbortSignal): Promise<Schemas["SourceConnectorList"]>;
  createUpload(body: Schemas["UploadCreateRequest"]): Promise<Schemas["UploadSession"]>;
  putUploadPart(uploadId: string, partNumber: number, body: Blob): Promise<void>;
  getUpload(uploadId: string, signal?: AbortSignal): Promise<Schemas["UploadSession"]>;
  completeUpload(uploadId: string, body: Schemas["UploadCompleteRequest"]): Promise<Schemas["UploadSession"]>;
  getJob(jobId: string, signal?: AbortSignal): Promise<Schemas["JobRun"]>;
  screenFrequency(
    startMhz: number,
    endMhz: number,
    signal?: AbortSignal,
  ): Promise<Schemas["FrequencyRelevanceScreen"]>;
  getOperationsMetrics(signal?: AbortSignal): Promise<Schemas["OperationsMetrics"]>;
  searchRecords(search: RecordSearch, cursor?: string, signal?: AbortSignal): Promise<SourceRecordList>;
  getRecord(recordId: string, signal?: AbortSignal): Promise<Schemas["SourceRecordDetail"]>;
  getArtifact(artifactId: string, signal?: AbortSignal): Promise<Schemas["SourceArtifactDetail"]>;
  getIntegrity(artifactId: string, signal?: AbortSignal): Promise<Schemas["ArtifactIntegrityReport"]>;
  /** Transfers the whole original. Only ever called after the user confirms the size. */
  downloadArtifact(artifactId: string): Promise<Blob>;
  // User administration (ADMIN_USERS). The server enforces tenant scope and refuses self-changes.
  listIficAnalyses(signal?: AbortSignal): Promise<Schemas["IficAnalysisList"]>;
  listIficFindings(
    analysisId: string,
    tier?: "HIGH" | "MEDIUM" | "LOW",
    cursor?: string,
    signal?: AbortSignal,
  ): Promise<Schemas["IficFindingList"]>;
  listUsers(cursor?: string, signal?: AbortSignal): Promise<Schemas["AdminUserList"]>;
  getUser(userId: string, signal?: AbortSignal): Promise<Schemas["AdminUserDetail"]>;
  createUser(body: Schemas["AdminUserCreateRequest"]): Promise<Schemas["AdminUserDetail"]>;
  setUserRoles(userId: string, roles: Schemas["Role"][]): Promise<Schemas["AdminUserDetail"]>;
  setUserStatus(userId: string, active: boolean): Promise<Schemas["AdminUserDetail"]>;
  revokeUserSessions(userId: string): Promise<Schemas["AdminUserDetail"]>;
  grantEntitlement(
    userId: string,
    body: Schemas["AdminEntitlementGrantRequest"],
  ): Promise<Schemas["AdminUserDetail"]>;
  revokeEntitlement(userId: string, grantId: string): Promise<Schemas["AdminUserDetail"]>;
}

function isErrorResponse(body: unknown): body is Schemas["ErrorResponse"] {
  const error = (body as Schemas["ErrorResponse"] | null)?.error;
  return typeof error?.code === "string" && typeof error?.message === "string";
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const doFetch = options.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  async function send(
    path: string,
    accept: string,
    init: RequestInit = {},
    signal?: AbortSignal,
  ): Promise<Response> {
    const token = options.getAccessToken();
    if (token === null) {
      const error = new ApiError(401, "UNAUTHENTICATED", "Sign-in is required.");
      options.onUnauthenticated(error);
      throw error;
    }
    try {
      return await doFetch(`${options.baseUrl}${path}`, {
        ...init,
        headers: { ...init.headers, Authorization: `Bearer ${token}`, Accept: accept },
        // Bearer tokens only: never send ambient cookies, and never store responses.
        credentials: "omit",
        cache: "no-store",
        ...(signal ? { signal } : {}),
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") {
        throw cause;
      }
      throw new ApiError(0, "NETWORK_ERROR", "The AstraSync server could not be reached.");
    }
  }

  function failure(response: Response, body: unknown): ApiError {
    const error = isErrorResponse(body)
      ? new ApiError(response.status, body.error.code, body.error.message, body.error.request_id)
      : new ApiError(response.status, "INVALID_RESPONSE", "The server returned an unknown error.");
    if (response.status === 401) {
      options.onUnauthenticated(error);
    }
    return error;
  }

  async function readJson(response: Response): Promise<unknown> {
    try {
      return await response.json();
    } catch {
      return null; // A success needs a body, and an error falls back to its status.
    }
  }

  async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await send(path, "application/json", {}, signal);
    const body = await readJson(response);
    if (!response.ok) {
      throw failure(response, body);
    }
    if (body === null) {
      throw new ApiError(response.status, "INVALID_RESPONSE", "The server returned no data.");
    }
    return body as T;
  }

  async function write<T>(
    method: "POST" | "PUT" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<T> {
    const response = await send(path, "application/json", {
      method,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      headers: {
        "Content-Type": "application/json",
        // One key per user action, so a retry after a lost response cannot act twice.
        "Idempotency-Key": crypto.randomUUID(),
      },
    });
    const parsed = await readJson(response);
    if (!response.ok) {
      throw failure(response, parsed);
    }
    return parsed as T;
  }

  const userPath = (userId: string) => `/api/v1/admin/users/${encodeURIComponent(userId)}`;
  const casePath = (caseId: string) => `/api/v1/cases/${encodeURIComponent(caseId)}`;

  return {
    getMe: (signal) => get<Me>("/api/v1/me", signal),
    listCases: (filters = {}, cursor, signal) => {
      const params = new URLSearchParams();
      for (const [name, value] of Object.entries(filters)) {
        params.set(name, String(value));
      }
      params.set("limit", "50");
      if (cursor !== undefined) {
        params.set("cursor", cursor);
      }
      return get<CaseList>(`/api/v1/cases?${params}`, signal);
    },
    getCase: (caseId, signal) => get(casePath(caseId), signal),
    getAnalysis: (runId, signal) => get(`/api/v1/analyses/${encodeURIComponent(runId)}`, signal),
    requestAnalysis: (caseId) => write("POST", `${casePath(caseId)}/analyse`, {}),
    listDrafts: (caseId, signal) => get(`${casePath(caseId)}/drafts`, signal),
    createDraft: (caseId, draftType, analysisRunId) =>
      write("POST", `${casePath(caseId)}/drafts`, {
        draft_type: draftType,
        analysis_run_id: analysisRunId,
      }),
    updateDraft: (caseId, draftId, content) =>
      write("PUT", `${casePath(caseId)}/drafts/${encodeURIComponent(draftId)}`, {
        content_markdown: content,
      }),
    listReviews: (caseId, signal) => get(`${casePath(caseId)}/reviews`, signal),
    createReview: (caseId, body) => write("POST", `${casePath(caseId)}/reviews`, body),
    exportCase: (caseId) => get(`${casePath(caseId)}/export`),
    listAlerts: (status, cursor, signal) => {
      const params = new URLSearchParams();
      if (status !== undefined) {
        params.set("status", status);
      }
      params.set("limit", "50");
      if (cursor !== undefined) {
        params.set("cursor", cursor);
      }
      return get(`/api/v1/alerts?${params}`, signal);
    },
    getAlert: (alertId, signal) => get(`/api/v1/alerts/${encodeURIComponent(alertId)}`, signal),
    acknowledgeAlert: (alertId) =>
      write("POST", `/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {}),
    getAlertPreferences: (signal) => get("/api/v1/alerts/preferences", signal),
    updateAlertPreferences: (body) => write("PUT", "/api/v1/alerts/preferences", body),
    registerDevice: (platform, pushToken) =>
      write("POST", "/api/v1/devices", { platform, push_token: pushToken }),
    streamAlerts: async (onAlert, signal, onSessionEnded) => {
      const response = await send("/api/v1/alerts/stream", "text/event-stream", {}, signal);
      if (!response.ok) {
        throw failure(response, await readJson(response));
      }
      const reader = response.body?.getReader();
      if (reader === undefined) {
        throw new ApiError(0, "INVALID_RESPONSE", "The server returned no stream.");
      }
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) {
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        for (;;) {
          const end = buffer.indexOf("\n\n");
          if (end < 0) {
            break;
          }
          const block = buffer.slice(0, end);
          buffer = buffer.slice(end + 2);
          const lines = block.split("\n");
          const event = lines.find((line) => line.startsWith("event: "))?.slice(7);
          const data = lines.find((line) => line.startsWith("data: "))?.slice(6);
          if (event === "session-ended") {
            onSessionEnded?.();
            return;
          }
          if (event === "alert" && data !== undefined) {
            onAlert(JSON.parse(data) as Schemas["AlertSummary"]);
          }
        }
      }
    },
    listSources: (signal) => get("/api/v1/sources", signal),
    createUpload: (body) => write("POST", "/api/v1/uploads", body),
    putUploadPart: async (uploadId, partNumber, body) => {
      const response = await send(
        `/api/v1/uploads/${encodeURIComponent(uploadId)}/parts/${partNumber}`,
        "application/json",
        { method: "PUT", body, headers: { "Content-Type": "application/octet-stream" } },
      );
      if (!response.ok) {
        throw failure(response, await readJson(response));
      }
    },
    getUpload: (uploadId, signal) => get(`/api/v1/uploads/${encodeURIComponent(uploadId)}`, signal),
    completeUpload: (uploadId, body) =>
      write("POST", `/api/v1/uploads/${encodeURIComponent(uploadId)}/complete`, body),
    getJob: (jobId, signal) => get(`/api/v1/jobs/${encodeURIComponent(jobId)}`, signal),
    screenFrequency: (startMhz, endMhz, signal) => {
      const params = new URLSearchParams({ start_mhz: String(startMhz), end_mhz: String(endMhz) });
      return get(`/api/v1/finland-relevance/frequency-screen?${params.toString()}`, signal);
    },
    getOperationsMetrics: (signal) => get("/api/v1/operations/metrics", signal),
    searchRecords: (search, cursor, signal) => {
      const params = new URLSearchParams();
      for (const [name, value] of Object.entries(search)) {
        params.set(name, String(value));
      }
      params.set("limit", "50");
      if (cursor !== undefined) {
        params.set("cursor", cursor);
      }
      return get(`/api/v1/source-records?${params}`, signal);
    },
    getRecord: (id, signal) => get(`/api/v1/source-records/${encodeURIComponent(id)}`, signal),
    getArtifact: (id, signal) => get(`/api/v1/source-artifacts/${encodeURIComponent(id)}`, signal),
    getIntegrity: (id, signal) =>
      get(`/api/v1/source-artifacts/${encodeURIComponent(id)}/integrity`, signal),
    downloadArtifact: async (id) => {
      const response = await send(
        `/api/v1/source-artifacts/${encodeURIComponent(id)}/content`,
        "application/octet-stream",
      );
      if (!response.ok) {
        throw failure(response, await readJson(response));
      }
      return response.blob();
    },
    listIficAnalyses: (signal) => get("/api/v1/ific/analyses?limit=50", signal),
    listIficFindings: (analysisId, tier, cursor, signal) => {
      const params = new URLSearchParams({ limit: "50" });
      if (tier !== undefined) {
        params.set("tier", tier);
      }
      if (cursor !== undefined) {
        params.set("cursor", cursor);
      }
      return get(`/api/v1/ific/analyses/${encodeURIComponent(analysisId)}/findings?${params}`, signal);
    },
    listUsers: (cursor, signal) => {
      const params = new URLSearchParams({ limit: "50" });
      if (cursor !== undefined) {
        params.set("cursor", cursor);
      }
      return get(`/api/v1/admin/users?${params}`, signal);
    },
    getUser: (userId, signal) => get(userPath(userId), signal),
    createUser: (body) => write("POST", "/api/v1/admin/users", body),
    setUserRoles: (userId, roles) => write("PUT", `${userPath(userId)}/roles`, { roles }),
    setUserStatus: (userId, active) => write("PUT", `${userPath(userId)}/status`, { active }),
    revokeUserSessions: (userId) => write("POST", `${userPath(userId)}/revoke-sessions`),
    grantEntitlement: (userId, body) => write("POST", `${userPath(userId)}/entitlements`, body),
    revokeEntitlement: (userId, grantId) =>
      write("DELETE", `${userPath(userId)}/entitlements/${encodeURIComponent(grantId)}`),
  };
}
