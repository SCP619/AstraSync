import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import summaryFixture from "../../../contract/fixtures/valid/CaseSummary.frequency_match_insufficient_data.json";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";

const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };
const page = (items: unknown[]) => ({ ...envelope, items, limit: 50, next_cursor: null, total_if_known: items.length });
const analysis = (kind: string, issue: number, concerns: Record<string, number>, findings: number) => ({
  analysis_id: `AN-${issue}`,
  source_id: "SRC",
  artifact_id: `ART-${issue}`,
  previous_artifact_id: null,
  kind,
  issue,
  rule_version: "demo",
  status: "COMPLETED",
  findings_count: findings,
  cases_created: 1,
  findings_sha256: null,
  summary: { concerns, top_administrations: { RUS: 4, EST: 2 } },
  created_at_utc: meFixture.generated_at_utc,
});

function show(capabilities: string[]) {
  const routes: Record<string, unknown> = {
    "/api/v1/me": { ...meFixture, capabilities },
    "/api/v1/ific/analyses": page([
      analysis("TERRESTRIAL_IFIC", 3076, { VERIFIED_CRITERION_EXCEEDANCE: 1, COORDINATION_REVIEW: 5, POTENTIAL_CONCERN: 2 }, 1867),
      analysis("SPACE_IFIC", 3074, { WORST_CASE_EXCEEDANCE: 44, POTENTIAL_CONCERN: 36 }, 196),
    ]),
    "/api/v1/cases": page([summaryFixture]),
  };
  const fetchImpl = vi.fn(async (url: RequestInfo | URL) => {
    const body = routes[new URL(String(url)).pathname];
    return new Response(JSON.stringify(body ?? {}), { status: body ? 200 : 404 });
  }) as unknown as typeof fetch;
  const auth: AuthAdapter = {
    getAccessToken: async () => "token",
    signIn: async () => undefined,
    completeSignIn: async () => "/dashboard",
    clearSession: async () => undefined,
    signOut: async () => undefined,
  };
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("dashboard", () => {
  it("shows KPIs and insights from the analyses, without identifiers", async () => {
    show(["AUTHENTICATED", "SOURCE_READ", "CASE_READ"]);
    const terrestrial = (await screen.findByText("Terrestrial above threshold")).closest(".kpi") as HTMLElement;
    expect(within(terrestrial).getByText("6")).toBeTruthy();
    const space = screen.getByText("Space worst case above limit").closest(".kpi") as HTMLElement;
    expect(within(space).getByText("44")).toBeTruthy();
    expect(screen.getByText(/6 terrestrial notices in IFIC 3076 exceed/)).toBeTruthy();
    expect(screen.getByText(/44 space notices in IFIC 3074/)).toBeTruthy();
    expect(screen.queryByText(/AN-3076|ART-3076|DEMO-TENANT/)).toBeNull();
  });

  it("does not request data the user cannot read", async () => {
    show(["AUTHENTICATED"]);
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Needs review" })).toBeNull();
  });
});
