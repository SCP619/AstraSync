import {
  InMemoryWebStorage,
  UserManager,
  WebStorageStateStore,
  type UserManagerSettings,
} from "oidc-client-ts";
import type { AppConfig } from "../config";
import type { AuthAdapter } from "./adapter";

export function buildOidcSettings(config: AppConfig, origin: string): UserManagerSettings {
  return {
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    scope: config.oidcScope,
    redirect_uri: `${origin}/auth/callback`,
    post_logout_redirect_uri: `${origin}/login`,
    response_type: "code", // Authorization Code; the library adds PKCE S256.
    loadUserInfo: false,
    automaticSilentRenew: false,
    // Tokens live in memory only, never in localStorage or sessionStorage. A reload means
    // signing in again. Only the short-lived PKCE and state values use sessionStorage.
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  };
}

export function createWebOidcAdapter(config: AppConfig): AuthAdapter {
  const manager = new UserManager(buildOidcSettings(config, window.location.origin));
  return {
    async getAccessToken() {
      const user = await manager.getUser();
      return user?.access_token ?? null;
    },
    async signIn(returnTo) {
      await manager.signinRedirect({ state: { returnTo } });
    },
    async completeSignIn() {
      const user = await manager.signinRedirectCallback();
      const state = user.state as { returnTo?: unknown } | undefined;
      return safeReturnPath(state?.returnTo);
    },
    async clearSession() {
      await manager.removeUser();
    },
    async signOut() {
      await manager.signoutRedirect();
    },
  };
}

/** Same-app paths only, so that a crafted link cannot redirect a user off the app after sign-in. */
export function safeReturnPath(value: unknown): string {
  if (typeof value === "string" && value.startsWith("/") && !value.startsWith("//")) {
    if (!value.startsWith("/\\") && !value.startsWith("/login") && !value.startsWith("/auth/")) {
      return value;
    }
  }
  return "/dashboard";
}
