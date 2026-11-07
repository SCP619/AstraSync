// Shared API client for Windows, Android and the web preview. The server stays authoritative:
// this client never decides permissions or results.
import type { components } from "./schema.gen";

export type Schemas = components["schemas"];
export type ErrorCode = Schemas["ErrorCode"];
export type Me = Schemas["Me"];
export type CaseList = Schemas["CaseList"];

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
  listCases(signal?: AbortSignal): Promise<CaseList>;
}

function isErrorResponse(body: unknown): body is Schemas["ErrorResponse"] {
  const error = (body as Schemas["ErrorResponse"] | null)?.error;
  return typeof error?.code === "string" && typeof error?.message === "string";
}

export function createApiClient(options: ApiClientOptions): ApiClient {
  const doFetch = options.fetch ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const token = options.getAccessToken();
    if (token === null) {
      const error = new ApiError(401, "UNAUTHENTICATED", "Sign-in is required.");
      options.onUnauthenticated(error);
      throw error;
    }

    let response: Response;
    try {
      response = await doFetch(`${options.baseUrl}${path}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
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

    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // Handled below: a success needs a body, and an error falls back to its status.
    }

    if (!response.ok) {
      const error = isErrorResponse(body)
        ? new ApiError(response.status, body.error.code, body.error.message, body.error.request_id)
        : new ApiError(response.status, "INVALID_RESPONSE", "The server returned an unknown error.");
      if (response.status === 401) {
        options.onUnauthenticated(error);
      }
      throw error;
    }
    if (body === null) {
      throw new ApiError(response.status, "INVALID_RESPONSE", "The server returned no data.");
    }
    return body as T;
  }

  return {
    getMe: (signal) => get<Me>("/api/v1/me", signal),
    listCases: (signal) => get<CaseList>("/api/v1/cases", signal),
  };
}
