import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import artifactFixture from "../../../contract/fixtures/valid/SourceArtifact.manifest_match_untrusted.json";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import recordFixture from "../../../contract/fixtures/valid/SourceRecordDetail.flagged_unit.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";

const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };

const hit = {
  source_record_id: "DEMO-RECORD-001",
  source_id: "DEMO-SOURCE-001",
  artifact_id: "DEMO-ARTIFACT-001",
  issue_key: null,
  publisher: "Demo publisher",
  filename_original: "demo-synthetic.xlsx",
  station_number: "DEMO-STATION-001",
  network_id: null,
  administration: null,
  frequency_start_mhz: null,
  frequency_end_mhz: null,
  classification: "UNVERIFIED",
  record_status: "REVIEW_REQUIRED",
  is_synthetic: true,
};

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

const page = (items: unknown[], next_cursor: string | null = null) => ({
  ...envelope,
  items,
  limit: 50,
  next_cursor,
  total_if_known: null,
});

const integrity = {
  ...envelope,
  artifact_id: "DEMO-ARTIFACT-001",
  raw_sha256: artifactFixture.raw_sha256,
  byte_length: artifactFixture.byte_length,
  publisher_auth_status: "HASH_MATCH_MANIFEST_UNTRUSTED",
  status: "INDEXED_WITH_WARNINGS",
  checks: [],
  row_reconciliation: { parsed: 2, accepted: 1, flagged: 1, rejected: 0 },
  is_synthetic: true,
};

type Reply = { status?: number; body: unknown };

function backend(overrides: Record<string, Reply> = {}) {
  const routes: Record<string, Reply> = {
    "/api/v1/me": {
      body: {
        ...meFixture,
        capabilities: ["AUTHENTICATED", "SOURCE_READ", "SOURCE_HEALTH_READ", "SOURCE_DOWNLOAD"],
      },
    },
    "/api/v1/sources": { body: page([source]) },
    "/api/v1/source-records": { body: page([hit]) },
    "/api/v1/source-records/DEMO-RECORD-001": { body: recordFixture },
    "/api/v1/source-artifacts/DEMO-ARTIFACT-001": { body: { ...envelope, ...artifactFixture } },
    "/api/v1/source-artifacts/DEMO-ARTIFACT-001/integrity": { body: integrity },
    ...overrides,
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
  completeSignIn: async () => "/sources",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(fetchImpl: typeof fetch) {
  render(
    <MemoryRouter initialEntries={["/sources"]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

function paths(fetchImpl: typeof fetch): string[] {
  return vi.mocked(fetchImpl).mock.calls.map(([url]) => {
    const parsed = new URL(String(url));
    return parsed.pathname + parsed.search;
  });
}

async function searchAndOpen() {
  await userEvent.click(await screen.findByRole("button", { name: "Search" }));
  await userEvent.click(await screen.findByRole("button", { name: "DEMO-STATION-001" }));
}

afterEach(cleanup);

describe("source library", () => {
  it("shows that a manual source has no automatic check", async () => {
    show(backend());
    expect(await screen.findByText("Manual import: no automatic check")).toBeTruthy();
    expect(screen.getByText("Access basis: Synthetic test data")).toBeTruthy();
  });

  it("sends typed search filters to the server, not a local filter", async () => {
    const fetchImpl = backend();
    show(fetchImpl);
    await userEvent.type(await screen.findByLabelText("Station number"), "DEMO");
    await userEvent.type(screen.getByLabelText("From (MHz)"), "100");
    await userEvent.click(screen.getByRole("button", { name: "Search" }));
    await screen.findByRole("button", { name: "DEMO-STATION-001" });
    expect(paths(fetchImpl)).toContain(
      "/api/v1/source-records?station_number=DEMO&frequency_start_mhz=100&limit=50",
    );
  });

  it("labels synthetic records and an unresolved frequency", async () => {
    show(backend());
    await userEvent.click(await screen.findByRole("button", { name: "Search" }));
    const row = (await screen.findByRole("button", { name: "DEMO-STATION-001" })).closest("tr")!;
    expect(within(row).getByText("SYNTHETIC")).toBeTruthy();
    expect(within(row).getByText("Unresolved")).toBeTruthy();
  });

  it("explains an empty result", async () => {
    show(backend({ "/api/v1/source-records": { body: page([]) } }));
    await userEvent.click(await screen.findByRole("button", { name: "Search" }));
    expect(await screen.findByText(/No records match/)).toBeTruthy();
  });

  it("loads further pages from the server cursor", async () => {
    const fetchImpl = backend({ "/api/v1/source-records": { body: page([hit], "NEXT") } });
    show(fetchImpl);
    await userEvent.click(await screen.findByRole("button", { name: "Search" }));
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));
    expect(paths(fetchImpl).some((path) => path.includes("cursor=NEXT"))).toBe(true);
  });

  it("shows the raw value and a finding, and never a guessed value", async () => {
    show(backend());
    await searchAndOpen();
    expect(await screen.findByText("UNIT_UNSPECIFIED")).toBeTruthy();
    expect(screen.queryByText("tx_frequency_hz")).toBeNull();
    expect(screen.getByText(/Unknown is never treated as zero/)).toBeTruthy();
    expect(screen.getAllByText("99").length).toBeGreaterThan(0);
    expect(screen.queryByText(/99 MHz/)).toBeNull();
  });

  it("does not present a manifest match as publisher verification", async () => {
    show(backend());
    await searchAndOpen();
    expect(
      await screen.findByText("Hash matches supplied manifest (publisher unverified)"),
    ).toBeTruthy();
    expect(screen.queryByText("Verified publisher")).toBeNull();
    expect(screen.getByText("Indexed with warnings")).toBeTruthy();
    expect(screen.getByText("2 parsed: 1 accepted, 1 flagged, 0 rejected")).toBeTruthy();
  });

  it("opening a record does not transfer the original file", async () => {
    const fetchImpl = backend();
    show(fetchImpl);
    await searchAndOpen();
    await screen.findByText("Hash matches supplied manifest (publisher unverified)");
    expect(paths(fetchImpl).some((path) => path.endsWith("/content"))).toBe(false);
  });

  it("warns about the transfer before downloading", async () => {
    const fetchImpl = backend();
    show(fetchImpl);
    await searchAndOpen();
    await userEvent.click(await screen.findByRole("button", { name: "Download full original" }));
    expect(screen.getByText(/transfers the whole file \(1\.0 KiB\)/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(paths(fetchImpl).some((path) => path.endsWith("/content"))).toBe(false);
  });

  it("refuses a browser download of a multi-GB file", async () => {
    show(
      backend({
        "/api/v1/source-artifacts/DEMO-ARTIFACT-001": {
          body: { ...envelope, ...artifactFixture, byte_length: 10 * 1024 ** 3 },
        },
      }),
    );
    await searchAndOpen();
    await userEvent.click(await screen.findByRole("button", { name: "Download full original" }));
    expect(screen.getByText(/too large to download in this web preview/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull();
  });

  it("shows a missing or unentitled record as not found", async () => {
    show(backend({ "/api/v1/source-records/DEMO-RECORD-001": { status: 404, body: { error: { code: "NOT_FOUND", message: "The requested resource was not found.", details: {}, request_id: "r" } } } }));
    await searchAndOpen();
    expect(await screen.findByText("The requested resource was not found.")).toBeTruthy();
  });

  it("gives an administrator source status but no record search", async () => {
    const fetchImpl = backend({
      "/api/v1/me": {
        body: { ...meFixture, roles: ["ADMINISTRATOR"], capabilities: ["AUTHENTICATED", "SOURCE_HEALTH_READ"] },
      },
    });
    show(fetchImpl);
    expect(await screen.findByText("Manual import: no automatic check")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Find a record" })).toBeNull();
    expect(paths(fetchImpl).some((path) => path.startsWith("/api/v1/source-records"))).toBe(false);
  });

  it("hides the library for a role without access, and the server still decides", async () => {
    const fetchImpl = backend({
      "/api/v1/me": { body: { ...meFixture, roles: ["ADMINISTRATOR"], capabilities: ["AUTHENTICATED"] } },
    });
    show(fetchImpl);
    expect((await screen.findByRole("alert")).textContent).toContain("not authorised");
    expect(screen.queryByRole("link", { name: "Source library" })).toBeNull();
    expect(paths(fetchImpl).filter((path) => path.startsWith("/api/v1/source"))).toEqual([]);
  });
});
