import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import detailFixture from "../../../contract/fixtures/valid/CaseDetail.insufficient_data.json";
import summaryFixture from "../../../contract/fixtures/valid/CaseSummary.frequency_match_insufficient_data.json";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";
import { COMMANDS } from "./AssistantPage";

const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };
const CASE = `/api/v1/cases/${summaryFixture.case_id}`;
const RUN = "DEMO-RUN-001";
const answer = {
  ...envelope,
  case_id: summaryFixture.case_id,
  analysis_run_id: RUN,
  answer_markdown: "The case was screened for review [E:DEMO-EVIDENCE-1].",
  uncertainties: [],
  cited_evidence_ids: ["DEMO-EVIDENCE-1"],
  ai_model_id: "qwen3:8b",
  requires_human_review: true,
};

function backend(capabilities: string[], ask: { status?: number; body: unknown } = { body: answer }) {
  const routes: Record<string, { status?: number; body: unknown }> = {
    "GET /api/v1/me": { body: { ...meFixture, capabilities } },
    "GET /api/v1/cases": { body: { ...envelope, items: [summaryFixture], limit: 50, next_cursor: null, total_if_known: 1 } },
    [`GET ${CASE}`]: { body: { ...detailFixture, latest_analysis_run_id: RUN } },
    [`POST ${CASE}/questions`]: ask,
  };
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const reply = routes[`${init?.method ?? "GET"} ${new URL(String(url)).pathname}`];
    return reply
      ? new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 })
      : new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "Not found.", details: {}, request_id: "x" } }), { status: 404 });
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/assistant",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(fetchImpl: typeof fetch) {
  render(
    <MemoryRouter initialEntries={["/assistant"]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

afterEach(cleanup);

const ANALYST = ["AUTHENTICATED", "CASE_READ", "DRAFT_CREATE", "DRAFT_READ"];

describe("AI agent page", () => {
  it("runs a preset command on the chosen case and shows the cited answer", async () => {
    const fetchImpl = backend(ANALYST);
    show(fetchImpl);
    await screen.findByRole("option", { name: new RegExp(summaryFixture.notice_id) });
    await userEvent.selectOptions(screen.getByLabelText("Case to discuss"), summaryFixture.case_id);
    const command = await screen.findByRole("button", { name: COMMANDS[0]!.label });
    await vi.waitFor(() => expect((command as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(command);
    expect(await screen.findByText(/screened for review/)).toBeTruthy();
    const post = vi.mocked(fetchImpl).mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ analysis_run_id: RUN, question: COMMANDS[0]!.prompt });
  });

  it("explains a refused answer", async () => {
    show(backend(ANALYST, { status: 503, body: { error: { code: "AI_UNAVAILABLE", message: "The assistant did not return a usable answer.", details: {}, request_id: "x" } } }));
    await screen.findByRole("option", { name: new RegExp(summaryFixture.notice_id) });
    await userEvent.selectOptions(screen.getByLabelText("Case to discuss"), summaryFixture.case_id);
    const command = await screen.findByRole("button", { name: COMMANDS[1]!.label });
    await vi.waitFor(() => expect((command as HTMLButtonElement).disabled).toBe(false));
    await userEvent.click(command);
    expect(await screen.findByText("The assistant did not return a usable answer.")).toBeTruthy();
  });

  it("keeps commands disabled without the drafting permission", async () => {
    show(backend(["AUTHENTICATED", "CASE_READ"]));
    expect(await screen.findByText(/needs the drafting permission/)).toBeTruthy();
    for (const command of COMMANDS) {
      expect((screen.getByRole("button", { name: command.label }) as HTMLButtonElement).disabled).toBe(true);
    }
  });
});
