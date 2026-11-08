import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";

// Made-up test values only: no real allocation or station is described here.
const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };

const match = (kind: "M4_ALLOCATION" | "SPECIAL_INTEREST_STATION", id: string, label: string | null) => ({
  source_record_id: id,
  source_id: "DEMO-SOURCE-001",
  artifact_id: "DEMO-ARTIFACT-001",
  reference_kind: kind,
  reference_field: kind === "M4_ALLOCATION" ? "SUB_BAND" : "TX_FREQUENCY",
  interval_basis: "TEST_BASIS",
  reference_start_mhz: 100,
  reference_end_mhz: 101,
  overlap_start_mhz: 100.5,
  overlap_end_mhz: 101,
  label,
  is_synthetic: true,
});

const screenReply = {
  ...envelope,
  query_start_mhz: 100.5,
  query_end_mhz: 102,
  gates: {
    label: "FREQUENCY_MATCH",
    reason_codes: ["M4_ALLOCATION_OVERLAP", "SERVICE_NOT_EVALUATED"],
    rule_version: "frequency-screen/1.0.0",
    overlap_start_mhz: 100.5,
    overlap_end_mhz: 101,
    frequency_match: true,
    service_match: null,
    geometry_match: null,
    technical_data_ready: null,
    criterion_available: null,
  },
  matches: [
    match("M4_ALLOCATION", "DEMO-ARTIFACT-001-1", "TEST ALLOCATION"),
    match("SPECIAL_INTEREST_STATION", "DEMO-ARTIFACT-001-2", "TEST STATION"),
  ],
  matches_truncated: false,
  sources_screened: [
    { source_id: "DEMO-SOURCE-001", source_type: "M4_ALLOCATION", artifact_id: "DEMO-ARTIFACT-001", revision: 1, is_synthetic: true },
  ],
  is_synthetic: true,
};

const metrics = {
  ...envelope,
  tenant_id: "DEMO-TENANT-001",
  queues: [{ lane: "ingestion", status: "QUEUED", count: 3, oldest_age_seconds: 125 }],
  failed_jobs_last_24h: 1,
  outbox_pending: 0,
  record_store: { enabled: true, datasets: 2, records: 260, bytes: 2_097_152 },
};

function backend(capabilities: string[], replies: Record<string, { status?: number; body: unknown }> = {}) {
  const routes: Record<string, { status?: number; body: unknown }> = {
    "/api/v1/me": { body: { ...meFixture, capabilities } },
    "/api/v1/finland-relevance/frequency-screen": { body: screenReply },
    "/api/v1/operations/metrics": { body: metrics },
    "/api/v1/cases": { body: { ...envelope, items: [], limit: 50, next_cursor: null, total_if_known: null } },
    ...replies,
  };
  return vi.fn(async (url: RequestInfo | URL) => {
    const reply = routes[new URL(String(url)).pathname];
    if (reply === undefined) {
      return new Response(
        JSON.stringify({ error: { code: "NOT_FOUND", message: "Not found.", details: {}, request_id: "r" } }),
        { status: 404 },
      );
    }
    return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 });
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/finland",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(fetchImpl: typeof fetch, path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("Finland relevance", () => {
  it("asks the server and keeps allocations, stations and unassessed stages apart", async () => {
    const fetchImpl = backend(["AUTHENTICATED", "SOURCE_READ"]);
    show(fetchImpl, "/finland");
    await userEvent.type(await screen.findByLabelText("Start (MHz)"), "100.5");
    await userEvent.type(screen.getByLabelText("End (MHz)"), "102");
    await userEvent.click(screen.getByRole("button", { name: "Screen range" }));
    const urls = vi.mocked(fetchImpl).mock.calls.map(([url]) => new URL(String(url)));
    await screen.findByText("Finnish allocation table (M4)", { exact: false });
    const call = urls.find((u) => u.pathname.endsWith("frequency-screen"));
    expect(call?.searchParams.get("start_mhz")).toBe("100.5");
    expect(call?.searchParams.get("end_mhz")).toBe("102");
    const allocations = screen.getByRole("region", { name: /Finnish allocation table/ });
    expect(within(allocations).getByText("TEST ALLOCATION")).toBeTruthy();
    expect(within(allocations).queryByText("TEST STATION")).toBeNull();
    const stations = screen.getByRole("region", { name: /Special-interest stations/ });
    expect(within(stations).getByText("TEST STATION")).toBeTruthy();
    expect(screen.getByText("Service: not assessed")).toBeTruthy();
    expect(screen.getByText("Frequency: match")).toBeTruthy();
    expect(screen.getByText(/not evidence of interference/)).toBeTruthy();
    expect(screen.queryByText(/violation/i)).toBeNull();
  });

  it("refuses an inverted range without calling the server", async () => {
    const fetchImpl = backend(["AUTHENTICATED", "SOURCE_READ"]);
    show(fetchImpl, "/finland");
    await userEvent.type(await screen.findByLabelText("Start (MHz)"), "200");
    await userEvent.type(screen.getByLabelText("End (MHz)"), "100");
    await userEvent.click(screen.getByRole("button", { name: "Screen range" }));
    expect(await screen.findByText(/end at or above the start/)).toBeTruthy();
    const screened = vi.mocked(fetchImpl).mock.calls.some(([url]) => String(url).includes("frequency-screen"));
    expect(screened).toBe(false);
  });

  it("shows the server's error instead of results", async () => {
    show(
      backend(["AUTHENTICATED", "SOURCE_READ"], {
        "/api/v1/finland-relevance/frequency-screen": {
          status: 503,
          body: { error: { code: "SERVICE_UNAVAILABLE", message: "Down.", details: {}, request_id: "req-9" } },
        },
      }),
      "/finland",
    );
    await userEvent.type(await screen.findByLabelText("Start (MHz)"), "1");
    await userEvent.type(screen.getByLabelText("End (MHz)"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Screen range" }));
    expect(await screen.findByText("req-9")).toBeTruthy();
    expect(screen.queryByRole("region", { name: /Finnish allocation table/ })).toBeNull();
  });
});

describe("overview processing panel", () => {
  it("shows server counts to users with JOB_READ", async () => {
    show(backend(["AUTHENTICATED", "JOB_READ"]), "/dashboard");
    expect(await screen.findByText("ingestion")).toBeTruthy();
    expect(screen.getByText("2 min")).toBeTruthy();
    expect(screen.getByText(/2 datasets, 260 records, 2.0 MiB/)).toBeTruthy();
  });

  it("is absent without JOB_READ and never requested", async () => {
    const fetchImpl = backend(["AUTHENTICATED"]);
    show(fetchImpl, "/dashboard");
    await screen.findByRole("heading", { name: "Dashboard" });
    expect(screen.queryByText("Processing")).toBeNull();
    const requested = vi.mocked(fetchImpl).mock.calls.some(([url]) => String(url).includes("operations"));
    expect(requested).toBe(false);
  });
});
