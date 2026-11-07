import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";

// Made-up test values only.
const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };
const source = {
  source_id: "DEMO-SOURCE-001",
  publisher: "Demo publisher",
  domain: "FINNISH_REFERENCE",
  source_type: "CHALLENGE_SYNTHETIC_REFERENCE",
  discovery_mode: "MANUAL_TRANSFER",
  rights_basis: "Synthetic test data",
  usage_classification: "INTERNAL",
  poll_interval_seconds: null,
  last_checked_at_utc: null,
  last_success_at_utc: null,
  status: "MANUAL_REQUIRED",
  is_synthetic: true,
};
const session = (status: string, parts: unknown[], sha: string | null = null, job: string | null = null) => ({
  ...envelope,
  upload_id: "DEMO-UPLOAD-1",
  status,
  source_type: "CHALLENGE_SYNTHETIC_REFERENCE",
  usage_classification: "INTERNAL",
  filename_original: "test.txt",
  expected_size_bytes: 5,
  received_size_bytes: 5,
  part_size_bytes: 67108864,
  max_size_bytes: 1024,
  parts,
  content_sha256: sha,
  job_id: job,
  failure_code: null,
  created_at_utc: envelope.generated_at_utc,
  expires_at_utc: envelope.generated_at_utc,
  completed_at_utc: null,
});
const job = {
  ...envelope,
  job_id: "DEMO-JOB-1",
  job_type: "INGEST",
  status: "READY",
  progress_stage: "READY",
  processed_bytes: null,
  processed_records: 2,
  total_records_if_known: null,
  attempt: 1,
  max_attempts: 3,
  resource_id: "DEMO-UPLOAD-1",
  started_at_utc: null,
  finished_at_utc: null,
  error_code: null,
};

function backend() {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(url)).pathname;
    const method = init?.method ?? "GET";
    const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
    if (path === "/api/v1/me") return reply({ ...meFixture, capabilities: ["AUTHENTICATED", "UPLOAD_MANAGE", "JOB_READ"] });
    if (path === "/api/v1/sources") return reply({ ...envelope, items: [source], limit: 50, next_cursor: null, total_if_known: null });
    if (path === "/api/v1/uploads" && method === "POST") return reply(session("CREATED", []), 201);
    if (path === "/api/v1/uploads/DEMO-UPLOAD-1/parts/1" && method === "PUT") return reply({ ...envelope, upload_id: "DEMO-UPLOAD-1", parts: [] });
    if (path === "/api/v1/uploads/DEMO-UPLOAD-1" && method === "GET") {
      return reply(session("UPLOADING", [{ part_number: 1, size_bytes: 5, etag: "etag-1", received: true }]));
    }
    if (path === "/api/v1/uploads/DEMO-UPLOAD-1/complete") return reply(session("QUEUED", [], "abc", "DEMO-JOB-1"));
    if (path === "/api/v1/jobs/DEMO-JOB-1") return reply(job);
    return reply({ error: { code: "NOT_FOUND", message: "Not found.", details: {}, request_id: "r" } }, 404);
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/uploads",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

afterEach(cleanup);

describe("upload", () => {
  it("sends the file through the real upload protocol and reports the server's result", async () => {
    const fetchImpl = backend();
    render(
      <MemoryRouter initialEntries={["/uploads"]}>
        <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
      </MemoryRouter>,
    );
    await userEvent.selectOptions(await screen.findByLabelText("Source"), "DEMO-SOURCE-001");
    const file = new File(["hello"], "test.txt");
    // jsdom's File lacks arrayBuffer(), which every supported browser provides.
    Object.defineProperty(file, "arrayBuffer", {
      value: async () => new TextEncoder().encode("hello").buffer,
    });
    await userEvent.upload(screen.getByLabelText("File"), file);
    // jsdom's constraint validation does not see files set by userEvent on a required input
    // (the browser check submits normally), so submit the form directly.
    fireEvent.submit(screen.getByRole("form", { name: "Upload" }));
    expect(await screen.findByText(/Ready: verified, archived and indexed/)).toBeTruthy();
    const calls = vi.mocked(fetchImpl).mock.calls.map(([url, init]) => `${init?.method ?? "GET"} ${new URL(String(url)).pathname}`);
    expect(calls).toContain("POST /api/v1/uploads");
    expect(calls).toContain("PUT /api/v1/uploads/DEMO-UPLOAD-1/parts/1");
    const complete = vi.mocked(fetchImpl).mock.calls.find(([url]) => String(url).endsWith("/complete"));
    const body = JSON.parse(String(complete?.[1]?.body));
    expect(body.parts).toEqual([{ part_number: 1, etag: "etag-1" }]);
    // SHA-256 of "hello", computed on the device and checked again by the server.
    expect(body.content_sha256).toBe("2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
  });
});
