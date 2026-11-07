import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import alertFixture from "../../../contract/fixtures/valid/AlertSummary.review.json";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import { createApiClient, type Schemas } from "../api/client";
import { App } from "../App";
import type { AuthAdapter } from "../auth/adapter";
import { createNativeOidcAdapter, NATIVE_REDIRECT_URI } from "../auth/nativeOidcAdapter";
import { alertPathFromPush, webPlatform, type PlatformAdapter } from "../platform/types";

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
const CAPABILITIES = ["AUTHENTICATED", "ALERT_READ", "ALERT_ACKNOWLEDGE", "ALERT_PREFERENCES", "DEVICE_MANAGE"];
const ID = alertFixture.alert_id;
const detail = {
  ...envelope,
  ...alertFixture,
  evidence_refs: ["DEMO-EVENT"],
  deliveries: [
    { delivery_id: "d1", channel: "IN_APP", attempt: 1, state: "READ", last_attempt_at_utc: null, delivered_at_utc: null, failure_code: null },
    { delivery_id: "d2", channel: "ANDROID", attempt: 1, state: "SENT", last_attempt_at_utc: null, delivered_at_utc: null, failure_code: null },
    { delivery_id: "d3", channel: "ANDROID", attempt: 1, state: "FAILED", last_attempt_at_utc: null, delivered_at_utc: null, failure_code: "PUSH_NOT_CONFIGURED" },
  ],
  acknowledgments: [],
};
const preferences = {
  ...envelope,
  enabled_channels: ["IN_APP", "ANDROID"],
  quiet_hours_start_utc: null,
  quiet_hours_end_utc: null,
};

type Reply = { status?: number; body: unknown };

function sse(text: string) {
  return new Response(text, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function backend(overrides: Record<string, Reply> = {}, stream = ": connected\n\n", capabilities = CAPABILITIES) {
  const routes: Record<string, Reply> = {
    "GET /api/v1/me": { body: { ...meFixture, capabilities } },
    "GET /api/v1/alerts": { body: page([alertFixture]) },
    [`GET /api/v1/alerts/${ID}`]: { body: detail },
    "GET /api/v1/alerts/preferences": { body: preferences },
    ...overrides,
  };
  return vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(url)).pathname;
    if (path === "/api/v1/alerts/stream") {
      return sse(stream);
    }
    const reply = routes[`${init?.method ?? "GET"} ${path}`];
    if (reply === undefined) {
      return new Response(
        JSON.stringify({ error: { code: "ALERT_NOT_FOUND", message: "The requested alert was not found.", details: {}, request_id: "r" } }),
        { status: 404 },
      );
    }
    return new Response(JSON.stringify(reply.body), { status: reply.status ?? 200 });
  }) as unknown as typeof fetch;
}

const auth: AuthAdapter = {
  getAccessToken: async () => "token",
  signIn: async () => undefined,
  completeSignIn: async () => "/alerts",
  clearSession: async () => undefined,
  signOut: async () => undefined,
};

function show(fetchImpl: typeof fetch, path = "/alerts", platform: PlatformAdapter = webPlatform) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <App auth={auth} apiBaseUrl="http://api.test" fetchImpl={fetchImpl} platform={platform} />
    </MemoryRouter>,
  );
}

function calls(fetchImpl: typeof fetch) {
  return vi.mocked(fetchImpl).mock.calls.map(([url, init]) => {
    const parsed = new URL(String(url));
    return { method: init?.method ?? "GET", path: parsed.pathname + parsed.search, body: init?.body ? JSON.parse(String(init.body)) : null, headers: (init?.headers ?? {}) as Record<string, string> };
  });
}

afterEach(cleanup);

describe("alert inbox", () => {
  it("shows the safe title, status in words and a synthetic label", async () => {
    show(backend());
    expect(await screen.findByRole("link", { name: alertFixture.safe_title })).toBeTruthy();
    expect(screen.getByText(/◆ Review/)).toBeTruthy();
    expect(screen.getByText("SYNTHETIC")).toBeTruthy();
    expect(screen.getAllByText(/Needs acknowledgment/).length).toBeGreaterThan(0);
  });

  it("counts open alerts in the navigation", async () => {
    show(backend());
    expect(await screen.findByRole("link", { name: "Alerts (1)" })).toBeTruthy();
  });

  it("asks the server for the chosen view", async () => {
    const fetchImpl = backend();
    show(fetchImpl);
    await userEvent.click(await screen.findByRole("tab", { name: "All alerts" }));
    await waitFor(() =>
      expect(calls(fetchImpl).some((call) => call.path === "/api/v1/alerts?limit=50")).toBe(true),
    );
  });

  it("explains an empty inbox", async () => {
    show(backend({ "GET /api/v1/alerts": { body: page([]) } }));
    expect(await screen.findByText("Nothing needs acknowledgment.")).toBeTruthy();
  });

  it("says when notifications are off, and that the inbox still works", async () => {
    const platform: PlatformAdapter = { ...webPlatform, name: "android", enablePush: async () => "DENIED" };
    show(backend(), "/alerts", platform);
    expect(await screen.findByText(/Notifications are turned off for this app/)).toBeTruthy();
    expect(screen.getByRole("link", { name: alertFixture.safe_title })).toBeTruthy();
  });

  it("never asks to register a device without the capability", async () => {
    const enablePush = vi.fn(async () => "GRANTED" as const);
    show(backend({}, ": connected\n\n", ["AUTHENTICATED", "ALERT_READ"]), "/alerts", { ...webPlatform, enablePush });
    await screen.findByRole("heading", { name: "Alerts" });
    expect(enablePush).not.toHaveBeenCalled();
  });
});

describe("alert detail and acknowledgment", () => {
  it("states that an alert is not a finding and reports delivery honestly", async () => {
    show(backend(), `/alerts/${ID}`);
    expect(await screen.findByText(/not a finding/)).toBeTruthy();
    expect(screen.getByText(/Sent, not confirmed delivered/)).toBeTruthy();
    expect(screen.getByText("PUSH_NOT_CONFIGURED")).toBeTruthy();
  });

  it("links to the case by ID, for the server to authorize", async () => {
    show(backend(), `/alerts/${ID}`);
    const link = await screen.findByRole("link", { name: "Open case and evidence" });
    expect(link.getAttribute("href")).toBe(`/cases/${alertFixture.case_id}`);
  });

  it("acknowledges through the server, with an idempotency key", async () => {
    const fetchImpl = backend({
      [`POST /api/v1/alerts/${ID}/acknowledge`]: {
        body: { ...envelope, ack_id: "a", alert_id: ID, actor_id: "u", comment: null, acknowledged_at_utc: meFixture.generated_at_utc },
      },
    });
    show(fetchImpl, `/alerts/${ID}`);
    await userEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    const post = calls(fetchImpl).find((call) => call.method === "POST")!;
    expect(post.path).toBe(`/api/v1/alerts/${ID}/acknowledge`);
    expect(post.headers["Idempotency-Key"]).toBeTruthy();
  });

  it("offers no acknowledge button without the capability", async () => {
    show(backend({}, ": connected\n\n", ["AUTHENTICATED", "ALERT_READ"]), `/alerts/${ID}`);
    await screen.findByText(/not a finding/);
    expect(screen.queryByRole("button", { name: "Acknowledge" })).toBeNull();
  });

  it("shows a denied or missing alert as unavailable", async () => {
    show(backend(), "/alerts/other-id");
    expect(await screen.findByRole("heading", { name: "Alert unavailable" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "All alerts" })).toBeTruthy();
  });
});

describe("realtime stream", () => {
  it("raises a safe local notification and refreshes the inbox for a new alert", async () => {
    const notify = vi.fn(async () => undefined);
    const event = `event: alert\ndata: ${JSON.stringify(alertFixture)}\n\n`;
    const fetchImpl = backend({}, event);
    show(fetchImpl, "/alerts", { ...webPlatform, name: "windows", notify });
    await waitFor(() => expect(notify).toHaveBeenCalled());
    expect(notify.mock.calls[0]).toEqual([expect.objectContaining({ safe_title: alertFixture.safe_title })]);
  });

  it("parses split chunks, and sends the token in the header", async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode("event: alert\ndata: {\"alert_id\""));
        controller.enqueue(encoder.encode(":\"X\"}\n\n: keep-alive\n\n"));
        controller.close();
      },
    });
    const fetchImpl = vi.fn(async () => new Response(body, { status: 200 })) as unknown as typeof fetch;
    const api = createApiClient({
      baseUrl: "http://api.test",
      getAccessToken: () => "token",
      onUnauthenticated: () => undefined,
      fetch: fetchImpl,
    });
    const seen: unknown[] = [];
    await api.streamAlerts((alert: Schemas["AlertSummary"]) => seen.push(alert), new AbortController().signal);
    expect(seen).toEqual([{ alert_id: "X" }]);
    const [url, init] = vi.mocked(fetchImpl).mock.calls[0]!;
    expect(String(url)).not.toContain("token");
    expect(init?.headers).toMatchObject({ Authorization: "Bearer token" });
  });

  it("ends the session when the server says it ended", async () => {
    const clearSession = vi.fn(async () => undefined);
    show(backend({}, "event: session-ended\ndata: {}\n\n"), "/alerts", webPlatform);
    expect(clearSession).not.toHaveBeenCalled();
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeTruthy();
  });
});

describe("deep links and native sign-in", () => {
  it("opens a path from the platform, such as a tapped notification", async () => {
    let open: (path: string) => void = () => undefined;
    const platform: PlatformAdapter = {
      ...webPlatform,
      onOpenPath: (listener) => {
        open = listener;
        return () => undefined;
      },
    };
    show(backend(), "/alerts", platform);
    await screen.findByRole("heading", { name: "Alerts" });
    open(`/alerts/${ID}`);
    expect(await screen.findByText(/not a finding/)).toBeTruthy();
  });

  it("takes only a safe opaque ID from a push", () => {
    expect(alertPathFromPush({ alert_id: "abc123" })).toBe("/alerts/abc123");
    expect(alertPathFromPush({ alert_id: "../../evil" })).toBeNull();
    expect(alertPathFromPush({ alert_id: 5 })).toBeNull();
    expect(alertPathFromPush(null)).toBeNull();
    expect(alertPathFromPush({ title: "Station at 60.1N" })).toBeNull();
  });

  const config = {
    apiBaseUrl: "http://api.test",
    oidcAuthority: "https://idp.test",
    oidcClientId: "client",
    oidcScope: "openid api",
  };

  it("accepts only its own sign-in redirect", () => {
    const adapter = createNativeOidcAdapter(config, { openExternal: async () => undefined });
    expect(adapter.acceptRedirect(`${NATIVE_REDIRECT_URI}?code=x&state=y`)).toBe(true);
    expect(adapter.acceptRedirect("https://evil.test/auth/callback?code=x")).toBe(false);
    expect(adapter.acceptRedirect("fi.astrasync.app://other?code=x")).toBe(false);
    expect(adapter.acceptRedirect(NATIVE_REDIRECT_URI)).toBe(false);
  });

  it("refuses to complete a sign-in that was never started", async () => {
    const adapter = createNativeOidcAdapter(config, { openExternal: async () => undefined });
    await expect(adapter.completeSignIn()).rejects.toThrow("No sign-in is in progress");
    await expect(adapter.getAccessToken()).resolves.toBeNull();
  });

  function identityProvider(tokenStatus = 200) {
    const encode = (value: unknown) => btoa(JSON.stringify(value)).replace(/=+$/, "");
    const idToken = [
      encode({ alg: "none" }),
      encode({ iss: "https://idp.test", sub: "demo-user", aud: "client", exp: 4102444800, iat: 1 }),
      "signature",
    ].join(".");
    return vi.fn(async (url: RequestInfo | URL, _init?: RequestInit) => {
      const body = String(url).includes("/.well-known/")
        ? {
            issuer: "https://idp.test",
            authorization_endpoint: "https://idp.test/authorize",
            token_endpoint: "https://idp.test/token",
          }
        : tokenStatus === 200
          ? { access_token: "demo-access", id_token: idToken, token_type: "Bearer", expires_in: 900, scope: "openid api" }
          : { error: "invalid_grant" };
      return new Response(JSON.stringify(body), {
        status: String(url).includes("/token") ? tokenStatus : 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  }

  async function startSignIn(returnTo: string) {
    const openExternal = vi.fn(async (_url: string) => undefined);
    const adapter = createNativeOidcAdapter(config, { openExternal });
    await adapter.signIn(returnTo);
    const opened = new URL(openExternal.mock.calls[0]![0]);
    return { adapter, state: opened.searchParams.get("state")! };
  }

  it("completes the full redirect flow and keeps the token only in memory", async () => {
    const provider = identityProvider();
    vi.stubGlobal("fetch", provider);
    const { adapter, state } = await startSignIn("/cases/DEMO-1");
    const accepted = adapter.acceptRedirect(`${NATIVE_REDIRECT_URI}?code=demo-code&state=${state}`);
    expect(accepted).toBe(true);
    await expect(adapter.completeSignIn()).resolves.toBe("/cases/DEMO-1");
    await expect(adapter.getAccessToken()).resolves.toBe("demo-access");
    const exchange = provider.mock.calls.find(([url]) => String(url).includes("/token"))!;
    const form = String(exchange[1]?.body);
    expect(form).toContain("code_verifier=");
    expect(form).not.toContain("client_secret");
    expect(JSON.stringify({ ...localStorage, ...sessionStorage })).not.toContain("demo-access");
    await adapter.clearSession();
    await expect(adapter.getAccessToken()).resolves.toBeNull();
    vi.unstubAllGlobals();
  });

  it("rejects a redirect with a state it did not issue, and gives no token", async () => {
    vi.stubGlobal("fetch", identityProvider());
    const { adapter } = await startSignIn("/");
    adapter.acceptRedirect(`${NATIVE_REDIRECT_URI}?code=stolen&state=forged`);
    await expect(adapter.completeSignIn()).rejects.toThrow();
    await expect(adapter.getAccessToken()).resolves.toBeNull();
    vi.unstubAllGlobals();
  });

  it("cannot replay a used redirect, and a provider error gives no token", async () => {
    vi.stubGlobal("fetch", identityProvider());
    const { adapter, state } = await startSignIn("/");
    const redirect = `${NATIVE_REDIRECT_URI}?code=c&state=${state}`;
    adapter.acceptRedirect(redirect);
    await adapter.completeSignIn();
    await adapter.clearSession();
    adapter.acceptRedirect(redirect);
    await expect(adapter.completeSignIn()).rejects.toThrow();
    await expect(adapter.getAccessToken()).resolves.toBeNull();

    vi.stubGlobal("fetch", identityProvider(400));
    const second = await startSignIn("/");
    second.adapter.acceptRedirect(`${NATIVE_REDIRECT_URI}?code=c&state=${second.state}`);
    await expect(second.adapter.completeSignIn()).rejects.toThrow();
    await expect(second.adapter.getAccessToken()).resolves.toBeNull();
    vi.unstubAllGlobals();
  });

  it("does not return to an unsafe path after sign-in", async () => {
    vi.stubGlobal("fetch", identityProvider());
    const { adapter, state } = await startSignIn("https://evil.test/");
    adapter.acceptRedirect(`${NATIVE_REDIRECT_URI}?code=c&state=${state}`);
    await expect(adapter.completeSignIn()).resolves.toBe("/dashboard");
    vi.unstubAllGlobals();
  });

  it("signs in through the external browser with PKCE, storing no token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            issuer: "https://idp.test",
            authorization_endpoint: "https://idp.test/authorize",
            token_endpoint: "https://idp.test/token",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const openExternal = vi.fn(async (_url: string) => undefined);
    const adapter = createNativeOidcAdapter(config, { openExternal });
    await adapter.signIn("/cases/1");
    vi.unstubAllGlobals();
    const url = new URL(openExternal.mock.calls[0]![0]);
    expect(url.origin + url.pathname).toBe("https://idp.test/authorize");
    expect(url.searchParams.get("response_type")).toBe("code");
    expect(url.searchParams.get("code_challenge_method")).toBe("S256");
    expect(url.searchParams.get("redirect_uri")).toBe(NATIVE_REDIRECT_URI);
    expect(JSON.stringify({ ...localStorage })).not.toContain("access_token");
    expect(JSON.stringify({ ...sessionStorage })).not.toContain("access_token");
  });
});
