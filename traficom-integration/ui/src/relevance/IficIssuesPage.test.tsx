import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import { CriterionPanel } from "./IficIssuesPage";
import type { AuthAdapter } from "../auth/adapter";

// Made-up test values only.
const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };
const ME = { ...meFixture, capabilities: ["AUTHENTICATED", "SOURCE_READ"] };
const analysis = {
  analysis_id: "AN-1",
  source_id: "ITU-TERR",
  artifact_id: "ART-1",
  previous_artifact_id: null,
  kind: "TERRESTRIAL_IFIC",
  issue: 3076,
  rule_version: "ific-finland-relevance/1.0.0",
  status: "COMPLETED",
  findings_count: 2,
  cases_created: 1,
  findings_sha256: "a".repeat(64),
  summary: { tiers: { HIGH: 1, LOW: 1 }, change_types: { NEW: 2 } },
  created_at_utc: envelope.generated_at_utc,
};
const finding = {
  rank: 1,
  notice_id: "100",
  domain: "TERRESTRIAL",
  administration: "TST",
  label: "TEST SITE",
  change_type: "NEW",
  priority_score: 11,
  priority_tier: "HIGH",
  finding_status: "EXPERT_REVIEW_REQUIRED",
  max_value: 31.75,
  max_value_unit: "dB(uV/m)",
  detail: {
    regulatory_finding: "NOT_EVALUATED: no approved criterion is configured",
    priority: { components: { special_interest_frequency_overlap: 3, neighbouring_administration: 0 } },
    calculations: [
      {
        method_id: "TERR_P1546",
        method_version: "1.0.0",
        receiver: "Nearest point of Finland",
        numeric_value: 31.75,
        unit: "dB(uV/m)",
        assumptions: ["Effective height heff assumed equal to antenna height ha."],
      },
    ],
    change: { change_type: "NEW" },
    stage_a_frequency: { status: "MATCH" },
    stage_b_service: { status: "MATCH" },
    stage_c_geography: { distance_to_finland_km: 14.6 },
    stage_d_readiness: { status: "READY" },
  },
};

function backend(handler: (path: string, url: URL) => Response | undefined) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input));
    if (url.pathname === "/api/v1/me") return new Response(JSON.stringify(ME));
    return (
      handler(url.pathname, url) ??
      new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "Not found.", details: {}, request_id: "r" } }), { status: 404 })
    );
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/ific",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function renderAt(fetchImpl: typeof fetch) {
  render(
    <MemoryRouter initialEntries={["/ific"]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("IFIC issues", () => {
  it("lists analysed issues, ranks findings and explains the selected one", async () => {
    const fetchImpl = backend((path, url) => {
      if (path === "/api/v1/ific/analyses") {
        return new Response(JSON.stringify({ ...envelope, items: [analysis], limit: 50, next_cursor: null, total_if_known: 1 }));
      }
      if (path === "/api/v1/ific/analyses/AN-1/findings") {
        expect(url.searchParams.get("tier")).toBe("HIGH");
        return new Response(
          JSON.stringify({ ...envelope, analysis_id: "AN-1", items: [finding], limit: 50, next_cursor: null, total_if_known: 1 }),
        );
      }
      return undefined;
    });
    renderAt(fetchImpl);
    expect(await screen.findByRole("link", { name: /IFIC issues/ })).toBeTruthy();
    expect(await screen.findByRole("button", { name: "3076" })).toBeTruthy();
    await userEvent.click(await screen.findByRole("button", { name: "TEST SITE" }));
    const panel = await screen.findByRole("region", { name: /TST TEST SITE/ });
    expect(within(panel).getByText(/not a statement of interference/)).toBeTruthy();
    expect(within(panel).getAllByText(/31.75 dB\(uV\/m\)/).length).toBeGreaterThan(0);
    expect(within(panel).getAllByText(/heff assumed equal/).length).toBeGreaterThan(0);
    expect(within(panel).getByText(/special interest frequency overlap/)).toBeTruthy();
  });

  it("shows the empty state and refusals", async () => {
    renderAt(
      backend((path) =>
        path === "/api/v1/ific/analyses"
          ? new Response(JSON.stringify({ ...envelope, items: [], limit: 50, next_cursor: null, total_if_known: 0 }))
          : undefined,
      ),
    );
    expect(await screen.findByText(/No IFIC issue has been analysed yet/)).toBeTruthy();
    cleanup();
    renderAt(
      backend((path) =>
        path === "/api/v1/ific/analyses"
          ? new Response(JSON.stringify({ error: { code: "FORBIDDEN", message: "Forbidden.", details: {}, request_id: "req-9" } }), { status: 403 })
          : undefined,
      ),
    );
    expect(await screen.findByText(/not authorised for this/)).toBeTruthy();
    expect(screen.getByText("req-9")).toBeTruthy();
  });
});

describe("CriterionPanel", () => {
  it("shows the classification, threshold, border point and margin without claiming a violation", () => {
    render(
      <CriterionPanel
        detail={{
          concern: { classification: "COORDINATION_REVIEW", margin_db: 14.84, concern_margin_db: 6, meaning: "Screening exceedance; not non-compliance." },
          criterion: { basis: "NORMATIVE_T/R_25-08_A1.2.3", threshold_dbuv_m: 12, base_threshold_dbuv_m: 12, bandwidth_correction_db: 0, citation: "ECC T/R 25-08 A1.2.3", assumptions: [] },
          border_screening: { status: "READY", points_evaluated: 40, max_point: { label: "Finland-Russia land border", lat: 64.5, lon: 30.1, distance_km: 28.5, field_strength_dbuv_m: 26.84 } },
          coordination: { finland_mentioned: true },
        }}
      />,
    );
    expect(screen.getByText("COORDINATION_REVIEW")).toBeTruthy();
    expect(screen.getByText(/14.84 dB/)).toBeTruthy();
    expect(screen.getByText(/Finland-Russia land border/)).toBeTruthy();
    expect(screen.queryByText(/violat/i)).toBeNull();
  });

  it("renders nothing without a concern", () => {
    const { container } = render(<CriterionPanel detail={{}} />);
    expect(container.innerHTML).toBe("");
  });
});
