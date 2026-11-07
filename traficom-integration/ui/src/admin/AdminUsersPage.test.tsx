import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";

// Made-up test values only.
const envelope = { schema_version: meFixture.schema_version, generated_at_utc: meFixture.generated_at_utc };
const ISSUER = "http://idp.test";
const ADMIN_ME = {
  ...meFixture,
  user_id: "DEMO-ADMIN",
  roles: ["ADMINISTRATOR"],
  capabilities: ["AUTHENTICATED", "SOURCE_HEALTH_READ", "ADMIN_USERS"],
};
const user = (id: string, subject: string, roles: string[], active = true) => ({
  user_id: id,
  issuer: ISSUER,
  oidc_subject: subject,
  active,
  roles,
  sessions_revoked_before_utc: null,
  last_verified_at_utc: null,
});
const detail = (u: ReturnType<typeof user>, capabilities: string[] = []) => ({
  ...envelope,
  user: u,
  effective_capabilities: u.active ? capabilities : [],
  entitlements: [],
});
const source = {
  source_id: "DEMO-SOURCE-001",
  publisher: "Demo publisher",
  domain: "FINNISH_REFERENCE",
  source_type: "CHALLENGE_SYNTHETIC_REFERENCE",
  discovery_mode: "MANUAL_TRANSFER",
  rights_basis: "Synthetic test data",
  usage_classification: "RESTRICTED",
  poll_interval_seconds: null,
  last_checked_at_utc: null,
  last_success_at_utc: null,
  status: "MANUAL_REQUIRED",
  is_synthetic: true,
};
const error = (status: number, code: string, message: string) =>
  new Response(JSON.stringify({ error: { code, message, details: {}, request_id: "req-1" } }), { status });

type Handler = (method: string, path: string, body: unknown) => Response | undefined;

function backend(me: unknown, handler: Handler = () => undefined) {
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(url)).pathname;
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (path === "/api/v1/me") return reply(me);
    const handled = handler(method, path, body);
    if (handled !== undefined) return handled;
    if (path === "/api/v1/sources") {
      return reply({ ...envelope, items: [source], limit: 50, next_cursor: null, total_if_known: null });
    }
    return error(404, "NOT_FOUND", "Not found.");
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/admin/users",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function renderAt(fetchImpl: typeof fetch) {
  render(
    <MemoryRouter initialEntries={["/admin/users"]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

function calls(fetchImpl: typeof fetch) {
  return vi.mocked(fetchImpl).mock.calls.map(([url, init]) => ({
    request: `${init?.method ?? "GET"} ${new URL(String(url)).pathname}`,
    body: init?.body ? JSON.parse(String(init.body)) : undefined,
  }));
}

afterEach(cleanup);

describe("user administration", () => {
  it("lists the tenant's users and changes a user's roles through the server", async () => {
    let reviewer = user("U-2", "reviewer-a", []);
    const fetchImpl = backend(ADMIN_ME, (method, path, body) => {
      if (path === "/api/v1/admin/users" && method === "GET") {
        return new Response(
          JSON.stringify({
            ...envelope,
            items: [user("DEMO-ADMIN", "admin-a", ["ADMINISTRATOR"]), reviewer],
            limit: 50,
            next_cursor: null,
            total_if_known: null,
          }),
        );
      }
      if (path === "/api/v1/admin/users/U-2" && method === "GET") return new Response(JSON.stringify(detail(reviewer)));
      if (path === "/api/v1/admin/users/U-2/roles" && method === "PUT") {
        reviewer = { ...reviewer, roles: (body as { roles: string[] }).roles };
        return new Response(JSON.stringify(detail(reviewer, ["AUTHENTICATED", "REVIEW_DECIDE"])));
      }
      return undefined;
    });
    renderAt(fetchImpl);
    expect(await screen.findByRole("link", { name: /Users and access/ })).toBeTruthy();
    await userEvent.click(await screen.findByRole("button", { name: "reviewer-a" }));
    const panel = await screen.findByRole("region", { name: "reviewer-a" });
    expect(within(panel).getByText("None.")).toBeTruthy();
    await userEvent.click(within(panel).getByLabelText("Reviewer"));
    await userEvent.click(within(panel).getByRole("button", { name: "Save roles" }));
    expect(await within(panel).findByText("REVIEW_DECIDE")).toBeTruthy();
    expect(calls(fetchImpl)).toContainEqual({
      request: "PUT /api/v1/admin/users/U-2/roles",
      body: { roles: ["REVIEWER"] },
    });
  });

  it("disables changes to the administrator's own account", async () => {
    const own = user("DEMO-ADMIN", "admin-a", ["ADMINISTRATOR"]);
    const fetchImpl = backend(ADMIN_ME, (method, path) => {
      if (path === "/api/v1/admin/users") {
        return new Response(JSON.stringify({ ...envelope, items: [own], limit: 50, next_cursor: null, total_if_known: null }));
      }
      if (path === "/api/v1/admin/users/DEMO-ADMIN") return new Response(JSON.stringify(detail(own, ["ADMIN_USERS"])));
      return undefined;
    });
    renderAt(fetchImpl);
    await userEvent.click(await screen.findByRole("button", { name: "admin-a" }));
    expect(await screen.findByText(/This is your own account/)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Deactivate" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Revoke sessions" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows the server's refusal and its request ID", async () => {
    const target = user("U-3", "analyst-a", ["ANALYST"]);
    const fetchImpl = backend(ADMIN_ME, (method, path) => {
      if (path === "/api/v1/admin/users") {
        return new Response(JSON.stringify({ ...envelope, items: [target], limit: 50, next_cursor: null, total_if_known: null }));
      }
      if (path === "/api/v1/admin/users/U-3" && method === "GET") return new Response(JSON.stringify(detail(target)));
      if (path === "/api/v1/admin/users/U-3/status") return error(403, "FORBIDDEN", "Forbidden.");
      return undefined;
    });
    renderAt(fetchImpl);
    await userEvent.click(await screen.findByRole("button", { name: "analyst-a" }));
    await userEvent.click(await screen.findByRole("button", { name: "Deactivate" }));
    expect(await screen.findByText(/not authorised for this/)).toBeTruthy();
    expect(screen.getByText("req-1")).toBeTruthy();
  });

  it("shows an empty list and a list load failure", async () => {
    const empty = backend(ADMIN_ME, (_method, path) =>
      path === "/api/v1/admin/users"
        ? new Response(JSON.stringify({ ...envelope, items: [], limit: 50, next_cursor: null, total_if_known: null }))
        : undefined,
    );
    renderAt(empty);
    expect(await screen.findByText("No users in this organisation.")).toBeTruthy();
    cleanup();
    const failing = backend(ADMIN_ME, (_method, path) =>
      path === "/api/v1/admin/users" ? error(503, "SERVICE_UNAVAILABLE", "Unavailable.") : undefined,
    );
    renderAt(failing);
    expect(await screen.findByText(/cannot verify your sign-in right now/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("ends the session when the server answers 401", async () => {
    const fetchImpl = backend(ADMIN_ME, (_method, path) =>
      path === "/api/v1/admin/users" ? error(401, "UNAUTHENTICATED", "Session revoked.") : undefined,
    );
    renderAt(fetchImpl);
    expect(await screen.findByText("Your session has ended. Sign in again to continue.")).toBeTruthy();
  });

  it("hides the page and its navigation from users without ADMIN_USERS", async () => {
    const fetchImpl = backend(meFixture);
    renderAt(fetchImpl);
    expect(await screen.findByText(/not authorised for this/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Users and access/ })).toBeNull();
    expect(calls(fetchImpl).some((call) => call.request.includes("/admin/"))).toBe(false);
  });
});
