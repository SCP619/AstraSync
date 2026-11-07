import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import meFixture from "../../contract/fixtures/valid/Me.analyst.json";
import { App } from "./App";
import type { AuthAdapter } from "./auth/adapter";

function fakeAuth(token: string | null, returnTo = "/dashboard"): AuthAdapter {
  return {
    getAccessToken: vi.fn(async () => token),
    signIn: vi.fn(async () => undefined),
    completeSignIn: vi.fn(async () => returnTo),
    clearSession: vi.fn(async () => undefined),
    signOut: vi.fn(async () => undefined),
  };
}

function error(code: string, message = code) {
  return { error: { code, message, details: {}, request_id: "demo-request" } };
}

type Reply = { status: number; body: unknown };

function backend(routes: Record<string, Reply>): typeof fetch {
  return vi.fn(async (url: RequestInfo | URL) => {
    const path = new URL(String(url)).pathname;
    const reply = routes[path] ?? { status: 404, body: error("NOT_FOUND") };
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  }) as typeof fetch;
}

function show(auth: AuthAdapter, fetchImpl: typeof fetch, path = "/dashboard") {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} />
    </MemoryRouter>,
  );
}

const ME = "/api/v1/me";
const CASES = "/api/v1/cases";
const analyst = {
  ...meFixture,
  capabilities: ["AUTHENTICATED", "CASE_READ"],
};

afterEach(cleanup);

describe("signed out", () => {
  it("shows sign-in and calls no protected API", async () => {
    const fetchImpl = backend({});
    show(fakeAuth(null), fetchImpl);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("starts sign-in and remembers the destination", async () => {
    const auth = fakeAuth(null);
    show(auth, backend({}));
    await userEvent.click(await screen.findByRole("button", { name: "Continue to sign-in" }));
    expect(auth.signIn).toHaveBeenCalledWith("/dashboard");
  });

  it("reports an unreachable identity provider", async () => {
    const auth = fakeAuth(null);
    vi.mocked(auth.signIn).mockRejectedValue(new Error("offline"));
    show(auth, backend({}));
    await userEvent.click(await screen.findByRole("button", { name: "Continue to sign-in" }));
    expect((await screen.findByRole("alert")).textContent).toContain("could not be reached");
  });
});

describe("signed in", () => {
  it("shows the identity the server returned", async () => {
    show(
      fakeAuth("token"),
      backend({ [ME]: { status: 200, body: analyst }, [CASES]: { status: 501, body: error("NOT_IMPLEMENTED") } }),
    );
    expect(await screen.findByText("Analyst")).toBeTruthy();
    expect(screen.getByText("DEMO-TENANT-001")).toBeTruthy();
    expect(screen.getByText("DEMO environment")).toBeTruthy();
  });

  it("states honestly that case data does not exist yet", async () => {
    show(
      fakeAuth("token"),
      backend({ [ME]: { status: 200, body: analyst }, [CASES]: { status: 501, body: error("NOT_IMPLEMENTED") } }),
    );
    expect(await screen.findByText(/not implemented/)).toBeTruthy();
  });

  it("hides the case panel without the capability and does not request it", async () => {
    const fetchImpl = backend({
      [ME]: { status: 200, body: { ...analyst, roles: ["ADMINISTRATOR"], capabilities: ["AUTHENTICATED"] } },
    });
    show(fakeAuth("token"), fetchImpl);
    expect(await screen.findByText("Administrator")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Cases" })).toBeNull();
    const paths = vi.mocked(fetchImpl).mock.calls.map(([url]) => new URL(String(url)).pathname);
    expect(paths).not.toContain(CASES);
  });

  it("still shows a server denial if the panel is shown and the server refuses", async () => {
    show(
      fakeAuth("token"),
      backend({ [ME]: { status: 200, body: analyst }, [CASES]: { status: 403, body: error("FORBIDDEN") } }),
    );
    expect((await screen.findByRole("alert")).textContent).toContain("not authorised");
  });

  it("explains a user with no role", async () => {
    show(
      fakeAuth("token"),
      backend({ [ME]: { status: 200, body: { ...analyst, roles: [], capabilities: ["AUTHENTICATED"] } } }),
    );
    expect(await screen.findByText(/No role assigned/)).toBeTruthy();
  });
});

describe("denied and failed sessions", () => {
  it("shows no access for an unprovisioned account, with a way out", async () => {
    const auth = fakeAuth("token");
    show(auth, backend({ [ME]: { status: 403, body: error("FORBIDDEN") } }));
    expect(await screen.findByRole("heading", { name: "No access to AstraSync" })).toBeTruthy();
    expect(screen.getByText("demo-request")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(auth.signOut).toHaveBeenCalledOnce();
  });

  it("ends the session on 401 and clears the local token", async () => {
    const auth = fakeAuth("token");
    show(auth, backend({ [ME]: { status: 401, body: error("UNAUTHENTICATED") } }));
    expect(await screen.findByText(/session has ended/)).toBeTruthy();
    expect(auth.clearSession).toHaveBeenCalledOnce();
    expect(screen.queryByText("DEMO-TENANT-001")).toBeNull();
  });

  it("removes visible identity when a later request gets 401", async () => {
    const auth = fakeAuth("token");
    show(
      auth,
      backend({ [ME]: { status: 200, body: analyst }, [CASES]: { status: 401, body: error("UNAUTHENTICATED") } }),
    );
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
    expect(screen.queryByText("DEMO-TENANT-001")).toBeNull();
  });

  it("explains a missing second factor", async () => {
    show(fakeAuth("token"), backend({ [ME]: { status: 401, body: error("MFA_REQUIRED") } }));
    expect(await screen.findByText(/requires multi-factor/)).toBeTruthy();
  });

  it("offers a retry when the server is unreachable, without ending the session", async () => {
    const auth = fakeAuth("token");
    const offline = vi.fn(async () => {
      throw new TypeError("failed");
    }) as typeof fetch;
    show(auth, offline);
    expect((await screen.findByRole("alert")).textContent).toContain("could not be reached");
    expect(auth.clearSession).not.toHaveBeenCalled();
    vi.mocked(offline).mockClear();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(offline).toHaveBeenCalled());
  });
});

describe("sign-in callback", () => {
  it("completes once and continues to the destination", async () => {
    const auth = fakeAuth(null);
    vi.mocked(auth.completeSignIn).mockImplementation(async () => {
      vi.mocked(auth.getAccessToken).mockResolvedValue("token");
      return "/dashboard";
    });
    show(auth, backend({ [ME]: { status: 200, body: analyst }, [CASES]: { status: 501, body: error("NOT_IMPLEMENTED") } }), "/auth/callback");
    expect(await screen.findByText("Analyst")).toBeTruthy();
    expect(auth.completeSignIn).toHaveBeenCalledOnce();
  });

  it("returns to sign-in with a message when the callback fails", async () => {
    const auth = fakeAuth(null);
    vi.mocked(auth.completeSignIn).mockRejectedValue(new Error("bad state"));
    show(auth, backend({}), "/auth/callback");
    expect(await screen.findByText(/could not be completed/)).toBeTruthy();
  });
});
