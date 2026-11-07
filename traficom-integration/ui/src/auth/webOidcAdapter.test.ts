import { InMemoryWebStorage, WebStorageStateStore } from "oidc-client-ts";
import { describe, expect, it } from "vitest";
import { buildOidcSettings, safeReturnPath } from "./webOidcAdapter";

const config = {
  apiBaseUrl: "http://api.test",
  oidcAuthority: "http://idp.test",
  oidcClientId: "client",
  oidcScope: "openid api",
};

describe("buildOidcSettings", () => {
  it("uses Authorization Code flow", () => {
    expect(buildOidcSettings(config, "http://app.test").response_type).toBe("code");
  });

  it("keeps tokens in memory, out of web storage", () => {
    const store = buildOidcSettings(config, "http://app.test").userStore as WebStorageStateStore;
    expect(store).toBeInstanceOf(WebStorageStateStore);
    expect((store as unknown as { _store: unknown })._store).toBeInstanceOf(InMemoryWebStorage);
  });

  it("derives redirects from the app's own origin", () => {
    const settings = buildOidcSettings(config, "http://app.test");
    expect(settings.redirect_uri).toBe("http://app.test/auth/callback");
    expect(settings.post_logout_redirect_uri).toBe("http://app.test/login");
  });
});

describe("safeReturnPath", () => {
  it("keeps in-app paths", () => {
    expect(safeReturnPath("/cases/DEMO-1")).toBe("/cases/DEMO-1");
  });

  it.each(["https://evil.test", "//evil.test", "/\\evil.test", "evil", 42, null, undefined])(
    "rejects %s",
    (value) => {
      expect(safeReturnPath(value)).toBe("/dashboard");
    },
  );

  it("does not return to the sign-in routes", () => {
    expect(safeReturnPath("/login")).toBe("/dashboard");
    expect(safeReturnPath("/auth/callback")).toBe("/dashboard");
  });
});
