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
  listSources(signal?: AbortSignal): Promise<Schemas["SourceConnectorList"]>;
  searchRecords(search: RecordSearch, cursor?: string, signal?: AbortSignal): Promise<SourceRecordList>;
  getRecord(recordId: string, signal?: AbortSignal): Promise<Schemas["SourceRecordDetail"]>;
  getArtifact(artifactId: string, signal?: AbortSignal): Promise<Schemas["SourceArtifactDetail"]>;
  getIntegrity(artifactId: string, signal?: AbortSignal): Promise<Schemas["ArtifactIntegrityReport"]>;
  /** Transfers the whole original. Only ever called after the user confirms the size. */
  downloadArtifact(artifactId: string): Promise<Blob>;
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

  async function write<T>(method: "POST" | "PUT", path: string, body: unknown): Promise<T> {
    const response = await send(path, "application/json", {
      method,
      body: JSON.stringify(body),
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
    listSources: (signal) => get("/api/v1/sources", signal),
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
  };
}
