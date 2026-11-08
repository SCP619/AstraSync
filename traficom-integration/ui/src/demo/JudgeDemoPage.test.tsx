import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";
import demo from "./judge-demo.json";

const auth: AuthAdapter = {
  getAccessToken: async () => null,
  signIn: async () => undefined,
  completeSignIn: async () => "/dashboard",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(path: string) {
  const fetchImpl = vi.fn(async () => new Response("{}", { status: 500 })) as unknown as typeof fetch;
  render(
    <MemoryRouter initialEntries={[path]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
  return fetchImpl;
}

afterEach(cleanup);

describe("judge demonstration", () => {
  it("opens from ?demo=judge without sign-in, labelled synthetic, with no API call", async () => {
    const fetchImpl = show("/cases?demo=judge");
    expect(await screen.findByRole("heading", { name: "AstraSync judge demonstration" })).toBeTruthy();
    expect(screen.getByRole("note").textContent).toContain("Demonstration data (synthetic)");
    expect(vi.mocked(fetchImpl)).not.toHaveBeenCalled();
  });

  it("walks through every scenario and never claims a violation", async () => {
    show("/demo");
    for (const scenario of demo.scenarios) {
      await userEvent.click(screen.getByRole("button", { name: scenario.title }));
      expect(screen.getByRole("heading", { level: 2, name: scenario.title })).toBeTruthy();
    }
    expect(screen.queryByText(/violat|illegal|non-compliant\b/i)).toBeNull();
  });

  it("shows the land-border exceedance with its threshold and margin", async () => {
    show("/demo");
    await userEvent.click(screen.getByRole("button", { name: "Land-border exceedance" }));
    expect(screen.getByText("VERIFIED_CRITERION_EXCEEDANCE")).toBeTruthy();
    expect(screen.getByText(/Finland-Russia land border/)).toBeTruthy();
  });

  it("is offered from the sign-in page", async () => {
    show("/login");
    expect(await screen.findByRole("link", { name: /judge demonstration/ })).toBeTruthy();
  });

  it("the dataset is synthetic and contains no IFIC identifiers", () => {
    expect(demo.data_status).toMatch(/SYNTHETIC/);
    for (const scenario of demo.scenarios) {
      expect(scenario.id.startsWith("DEMO-")).toBe(true);
    }
  });
});
