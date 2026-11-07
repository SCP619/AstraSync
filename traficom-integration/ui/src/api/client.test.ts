import { describe, expect, it, vi } from "vitest";
import meFixture from "../../../contract/fixtures/valid/Me.analyst.json";
import forbiddenFixture from "../../../contract/fixtures/valid/ErrorResponse.forbidden.json";
import { ApiError, createApiClient } from "./client";

function respond(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

function client(fetchImpl: typeof fetch, token: string | null = "demo-token") {
  const onUnauthenticated = vi.fn();
  const api = createApiClient({
    baseUrl: "http://api.test",
    getAccessToken: () => token,
    onUnauthenticated,
    fetch: fetchImpl,
  });
  return { api, onUnauthenticated };
}

describe("createApiClient", () => {
  it("sends the token in the header only, with no cookies or caching", async () => {
    const fetchImpl = respond(200, meFixture);
    await client(fetchImpl).api.getMe();

    const [url, init] = vi.mocked(fetchImpl).mock.calls[0]!;
    expect(url).toBe("http://api.test/api/v1/me");
    expect(String(url)).not.toContain("demo-token");
    expect(init?.headers).toMatchObject({ Authorization: "Bearer demo-token" });
    expect(init?.credentials).toBe("omit");
    expect(init?.cache).toBe("no-store");
  });

  it("returns the contract fixture unchanged", async () => {
    await expect(client(respond(200, meFixture)).api.getMe()).resolves.toEqual(meFixture);
  });

  it("maps the standard error envelope", async () => {
    const error = await client(respond(403, forbiddenFixture)).api.getMe().catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, code: "FORBIDDEN", requestId: "demo-request" });
  });

  it("does not end the session on 403", async () => {
    const { api, onUnauthenticated } = client(respond(403, forbiddenFixture));
    await api.getMe().catch(() => undefined);
    expect(onUnauthenticated).not.toHaveBeenCalled();
  });

  it("reports a 401 so the session can end", async () => {
    const body = {
      error: { code: "UNAUTHENTICATED", message: "x", details: {}, request_id: "r" },
    };
    const { api, onUnauthenticated } = client(respond(401, body));
    await expect(api.getMe()).rejects.toMatchObject({ code: "UNAUTHENTICATED" });
    expect(onUnauthenticated).toHaveBeenCalledOnce();
  });

  it("makes no request without a token", async () => {
    const fetchImpl = respond(200, meFixture);
    const { api, onUnauthenticated } = client(fetchImpl, null);
    await expect(api.getMe()).rejects.toMatchObject({ status: 401 });
    expect(fetchImpl).not.toHaveBeenCalled();
    expect(onUnauthenticated).toHaveBeenCalledOnce();
  });

  it("reports network failure and non-JSON errors distinctly", async () => {
    const offline = vi.fn(async () => {
      throw new TypeError("failed");
    }) as typeof fetch;
    await expect(client(offline).api.getMe()).rejects.toMatchObject({ code: "NETWORK_ERROR" });

    const html = vi.fn(async () => new Response("<html>", { status: 502 })) as typeof fetch;
    await expect(client(html).api.getMe()).rejects.toMatchObject({
      status: 502,
      code: "INVALID_RESPONSE",
    });
  });
});
