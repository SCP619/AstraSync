import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import runFixture from "../../../contract/fixtures/valid/AnalysisRun.mixed_method_states.json";
import detailFixture from "../../../contract/fixtures/valid/CaseDetail.insufficient_data.json";
import summaryFixture from "../../../contract/fixtures/valid/CaseSummary.frequency_match_insufficient_data.json";
import negativeFixture from "../../../contract/fixtures/valid/CaseSummary.verified_negative_margin.json";
import positiveFixture from "../../../contract/fixtures/valid/CaseSummary.verified_positive_margin.json";
import draftFixture from "../../../contract/fixtures/valid/DraftCreated.unapproved.json";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";
import { formatMargin } from "./labels";

const envelope = {
  schema_version: meFixture.schema_version,
  generated_at_utc: meFixture.generated_at_utc,
};
const page = (items: unknown[], next_cursor: string | null = null) => ({
  ...envelope,
  items,
  limit: 50,
  next_cursor,
  total_if_known: null,
});
const error = (code: string, message = code) => ({
  error: { code, message, details: {}, request_id: "demo-request" },
});

const ANALYST = ["AUTHENTICATED", "CASE_READ", "ANALYSIS_READ", "ANALYSIS_RUN", "DRAFT_CREATE", "DRAFT_READ"];
const REVIEWER = ["AUTHENTICATED", "CASE_READ", "ANALYSIS_READ", "DRAFT_READ", "REVIEW_DECIDE", "CASE_EXPORT"];
const CASE = "/api/v1/cases/DEMO-SPACE-001";
const analysed = { ...detailFixture, latest_analysis_run_id: runFixture.analysis_run_id };

type Reply = { status?: number; body: unknown };

function backend(capabilities: string[], overrides: Record<string, Reply> = {}) {
  const routes: Record<string, Reply> = {
    "GET /api/v1/me": { body: { ...meFixture, capabilities } },
    "GET /api/v1/cases": { body: page([summaryFixture]) },
    [`GET ${CASE}`]: { body: analysed },
    [`GET /api/v1/analyses/${runFixture.analysis_run_id}`]: { body: runFixture },
    [`GET ${CASE}/drafts`]: { body: page([]) },
    [`GET ${CASE}/reviews`]: { body: page([]) },
    ...overrides,
  };
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${new URL(String(url)).pathname}`;
    const reply = routes[key];
    if (reply === undefined) {
      return new Response(JSON.stringify(error("NOT_FOUND", "Not found.")), { status: 404 });
    }
    return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 });
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/cases",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(fetchImpl: typeof fetch, path = "/cases/DEMO-SPACE-001") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

function calls(fetchImpl: typeof fetch) {
  return vi.mocked(fetchImpl).mock.calls.map(([url, init]) => {
    const parsed = new URL(String(url));
    return {
      method: init?.method ?? "GET",
      path: parsed.pathname + parsed.search,
      body: init?.body ? JSON.parse(String(init.body)) : null,
      headers: (init?.headers ?? {}) as Record<string, string>,
    };
  });
}

async function openTab(name: string) {
  await userEvent.click(await screen.findByRole("tab", { name }));
}

afterEach(cleanup);

describe("formatMargin", () => {
  it("follows the dashboard specification", () => {
    expect(formatMargin(null, "VERIFIED")).toBe("—");
    expect(formatMargin(-2.3, "VERIFIED")).toBe("-2.30 dB");
    expect(formatMargin(2.3, "VERIFIED")).toBe("+2.30 dB");
    expect(formatMargin(0, "VERIFIED")).toBe("0.00 dB");
    expect(formatMargin(2.3, "UNVERIFIED")).toBe("—");
    expect(formatMargin(2.3, null)).toBe("—");
    expect(formatMargin(Number.NaN, "VERIFIED")).toBe("—");
  });
});

describe("case list", () => {
  it("shows a null margin as a dash and labels synthetic data", async () => {
    show(backend(ANALYST), "/cases");
    const row = (await screen.findByRole("link", { name: "SYNTHETIC-NOTICE-001" })).closest("tr")!;
    expect(within(row).getByText("SYNTHETIC")).toBeTruthy();
    expect(within(row).getByText("—")).toBeTruthy();
    expect(within(row).getByText("Insufficient data")).toBeTruthy();
    expect(within(row).getByText("Not computed")).toBeTruthy();
  });

  it("signs a verified margin and names the metric beside its value", async () => {
    show(
      backend(ANALYST, { "GET /api/v1/cases": { body: page([negativeFixture, { ...positiveFixture, case_id: "DEMO-SPACE-003" }]) } }),
      "/cases",
    );
    expect(await screen.findByText("-2.30 dB")).toBeTruthy();
    expect(screen.getByText("+2.30 dB")).toBeTruthy();
    expect(screen.getAllByText(/Power flux density \(PFD\): -102.3 DEMO-UNIT/).length).toBe(2);
    expect(screen.getAllByText("Potential limit exceedance", { selector: "td" }).length).toBe(2);
    expect(screen.queryByText(/violation/i)).toBeNull();
  });

  it("filters on the server, using the case ID in links rather than a position", async () => {
    const fetchImpl = backend(ANALYST);
    show(fetchImpl, "/cases");
    const link = await screen.findByRole("link", { name: "SYNTHETIC-NOTICE-001" });
    expect(link.getAttribute("href")).toBe("/cases/DEMO-SPACE-001");
    await userEvent.selectOptions(screen.getByLabelText("Finding"), "INSUFFICIENT_DATA");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() =>
      expect(calls(fetchImpl).some((call) => call.path.includes("finding_status=INSUFFICIENT_DATA"))).toBe(true),
    );
  });

  it("explains an empty list and loads pages by cursor", async () => {
    show(backend(ANALYST, { "GET /api/v1/cases": { body: page([]) } }), "/cases");
    expect(await screen.findByText(/No cases match/)).toBeTruthy();
    cleanup();
    const fetchImpl = backend(ANALYST, { "GET /api/v1/cases": { body: page([summaryFixture], "NEXT") } });
    show(fetchImpl, "/cases");
    await userEvent.click(await screen.findByRole("button", { name: "Load more" }));
    expect(calls(fetchImpl).some((call) => call.path.includes("cursor=NEXT"))).toBe(true);
  });
});

describe("source inspector", () => {
  it("explains relevance gates without calling an overlap interference", async () => {
    show(backend(ANALYST));
    expect(await screen.findByText(/A frequency match alone does not mean interference/)).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("DEMO / SYNTHETIC");
  });

  it("shows every method, with missing inputs and no number when not computed", async () => {
    show(backend(ANALYST));
    await openTab("Methods");
    const epfd = (await screen.findByText("SPACE_EPFD_NGSO")).closest("tr")!;
    expect(within(epfd).getByText("Not computed")).toBeTruthy();
    expect(within(epfd).getByText("Missing: constellation_definition")).toBeTruthy();
    const pfd = screen.getByText("SPACE_PFD_FREE_SPACE").closest("tr")!;
    expect(within(pfd).getByText("-102.3 DEMO-UNIT")).toBeTruthy();
    expect(within(pfd).getByText("-2.30 dB")).toBeTruthy();
  });

  it("keeps PFD and EPFD in separate tables", async () => {
    show(backend(ANALYST));
    await openTab("Methods");
    const pfd = await screen.findByRole("region", { name: "Power flux density (PFD)" });
    const epfd = screen.getByRole("region", { name: "Equivalent PFD (EPFD)" });
    expect(within(pfd).queryByText("SPACE_EPFD_NGSO")).toBeNull();
    expect(within(epfd).queryByText("SPACE_PFD_FREE_SPACE")).toBeNull();
  });

  it("shows a citation for a verified criterion", async () => {
    show(backend(ANALYST));
    await openTab("Criteria");
    expect(await screen.findByText("DEMO-SECTION")).toBeTruthy();
    expect(screen.getByText("VERIFIED")).toBeTruthy();
  });

  it("states honestly when no criterion was checked", async () => {
    show(
      backend(ANALYST, {
        [`GET /api/v1/analyses/${runFixture.analysis_run_id}`]: { body: { ...runFixture, criterion_checks: [] } },
      }),
    );
    await openTab("Criteria");
    expect(await screen.findByText(/makes no claim about a limit/)).toBeTruthy();
  });

  it("does not offer role actions the user lacks, and hides nothing the server allows", async () => {
    show(backend(REVIEWER));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("button", { name: "Run again" })).toBeNull();
    expect(screen.getByRole("button", { name: "Export evidence pack" })).toBeTruthy();
    cleanup();
    show(backend(ANALYST));
    await openTab("Draft and review");
    expect(await screen.findByText("Only a reviewer can record a decision or approve a draft.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Record decision" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Export evidence pack" })).toBeNull();
  });

  it("asks the server to analyse and never computes anything itself", async () => {
    const fetchImpl = backend(ANALYST, {
      [`POST ${CASE}/analyse`]: {
        status: 202,
        body: { ...envelope, analysis_run_id: runFixture.analysis_run_id, job_id: "DEMO-JOB" },
      },
    });
    show(fetchImpl);
    await userEvent.click(await screen.findByRole("button", { name: "Run again" }));
    const call = calls(fetchImpl).find((item) => item.method === "POST")!;
    expect(call.body).toEqual({});
    expect(call.headers["Idempotency-Key"]).toBeTruthy();
    expect(await screen.findByText(/Results appear when it ends/)).toBeTruthy();
  });

  it("shows a missing or unentitled case as unavailable, with a way back", async () => {
    show(backend(ANALYST, { [`GET ${CASE}`]: { status: 404, body: error("NOT_FOUND", "The requested resource was not found.") } }));
    expect(await screen.findByText("The requested resource was not found.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "All cases" })).toBeTruthy();
  });
});

describe("drafts and review", () => {
  const withDraft = {
    [`GET ${CASE}/drafts`]: { body: page([draftFixture]) },
  };

  it("labels a draft as unapproved and keeps it editable by analysts only", async () => {
    const fetchImpl = backend(ANALYST, {
      ...withDraft,
      [`PUT ${CASE}/drafts/DEMO-DRAFT-001`]: { body: { ...draftFixture, status: "EDITED" } },
    });
    show(fetchImpl);
    await openTab("Draft and review");
    expect(await screen.findByText("AI draft, not approved")).toBeTruthy();
    const box = screen.getByLabelText("Draft text");
    await userEvent.type(box, " More detail.");
    await userEvent.click(screen.getByRole("button", { name: "Save edits" }));
    const put = calls(fetchImpl).find((item) => item.method === "PUT")!;
    expect(Object.keys(put.body)).toEqual(["content_markdown"]);
  });

  it("explains that drafting being down does not stop the rest", async () => {
    show(
      backend(ANALYST, {
        [`POST ${CASE}/drafts`]: { status: 503, body: error("AI_UNAVAILABLE", "AI drafting is not available.") },
      }),
    );
    await openTab("Draft and review");
    await userEvent.click(await screen.findByRole("button", { name: "Create draft" }));
    expect(await screen.findByText("AI drafting is not available.")).toBeTruthy();
    expect(screen.getByText(/keep working without it/)).toBeTruthy();
  });

  it("states that nothing is sent automatically", async () => {
    show(backend(ANALYST));
    await openTab("Draft and review");
    expect(await screen.findByText(/AstraSync never sends anything/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /send/i })).toBeNull();
  });

  it("requires a reason and sends only the decision", async () => {
    const fetchImpl = backend(REVIEWER, {
      ...withDraft,
      [`POST ${CASE}/reviews`]: { status: 201, body: {} },
    });
    show(fetchImpl);
    await openTab("Draft and review");
    const select = await screen.findByLabelText("Decision");
    await userEvent.selectOptions(select, "APPROVE_DRAFT|DEMO-DRAFT-001");
    await userEvent.click(screen.getByRole("button", { name: "Record decision" }));
    expect(calls(fetchImpl).filter((item) => item.method === "POST")).toEqual([]);

    await userEvent.type(screen.getByLabelText(/Reason/), "Evidence checked.");
    await userEvent.click(screen.getByRole("button", { name: "Record decision" }));
    const post = calls(fetchImpl).find((item) => item.method === "POST")!;
    expect(post.body).toEqual({
      action: "APPROVE_DRAFT",
      decision_reason: "Evidence checked.",
      analysis_run_id: runFixture.analysis_run_id,
      draft_id: "DEMO-DRAFT-001",
    });
    expect(post.headers["Idempotency-Key"]).toBeTruthy();
  });

  it("keeps the confirmation after the decision lists reload", async () => {
    const server = backend(REVIEWER, { [`POST ${CASE}/reviews`]: { status: 201, body: {} } });
    let posted = false;
    let release = () => {};
    const held = new Promise<void>((resolve) => (release = resolve));
    // Holds the reload open, as a real network does, so the form is replaced while it loads.
    const fetchImpl = vi.fn(async (url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        posted = true;
      } else if (posted && String(url).endsWith("/reviews")) {
        await held;
      }
      return server(url, init);
    }) as unknown as typeof fetch;
    show(fetchImpl);
    await openTab("Draft and review");
    await userEvent.type(await screen.findByLabelText(/Reason/), "Due date is close.");
    await userEvent.click(screen.getByRole("button", { name: "Record decision" }));
    expect(await screen.findByText("Loading drafts and decisions…")).toBeTruthy();
    release();
    await screen.findByLabelText("Decision");
    expect(screen.getByText("Decision recorded.")).toBeTruthy();
  });

  it("blocks approving an objection when no criterion is verified", async () => {
    show(
      backend(REVIEWER, {
        [`GET /api/v1/analyses/${runFixture.analysis_run_id}`]: { body: { ...runFixture, criterion_checks: [] } },
        [`GET ${CASE}/drafts`]: { body: page([{ ...draftFixture, draft_type: "DRAFT_OBJECTION" }]) },
      }),
    );
    await openTab("Draft and review");
    const option = await screen.findByRole("option", { name: /needs a verified criterion/ });
    expect((option as HTMLOptionElement).disabled).toBe(true);
  });

  it("shows the server's refusal instead of assuming the action worked", async () => {
    show(
      backend(REVIEWER, {
        [`POST ${CASE}/reviews`]: { status: 403, body: error("FORBIDDEN") },
      }),
    );
    await openTab("Draft and review");
    await userEvent.type(await screen.findByLabelText(/Reason/), "Reason.");
    await userEvent.click(screen.getByRole("button", { name: "Record decision" }));
    expect((await screen.findByRole("alert")).textContent).toContain("not authorised");
    expect(screen.queryByText("Decision recorded.")).toBeNull();
  });
});
