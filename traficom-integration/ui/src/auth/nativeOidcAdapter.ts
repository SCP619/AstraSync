import { OidcClient, WebStorageStateStore } from "oidc-client-ts";
import type { AppConfig } from "../config";
import type { AuthAdapter } from "./adapter";
import { safeReturnPath } from "./webOidcAdapter";

export const NATIVE_SCHEME = "fi.astrasync.app";
export const NATIVE_REDIRECT_URI = `${NATIVE_SCHEME}://auth/callback`;
const NATIVE_LOGOUT_URI = `${NATIVE_SCHEME}://auth/logout`;

export interface NativeSignInBridge {
  /** Opens the OS browser, never a WebView, so the app can't see credentials or MFA. */
  openExternal(url: string): Promise<unknown>;
}

export interface NativeAuthAdapter extends AuthAdapter {
  /** Takes a deep link. Returns true if it is this app's sign-in redirect, ready to complete. */
  acceptRedirect(url: string): boolean;
}

/**
 * Authorization Code + PKCE through the system browser (RFC 8252). The access token stays in
 * memory only: nothing long-lived is stored, so there is no refresh token to protect or leak. A
 * restart signs in again, normally without a prompt because the browser keeps the IdP session.
 */
export function createNativeOidcAdapter(
  config: AppConfig,
  bridge: NativeSignInBridge,
): NativeAuthAdapter {
  const client = new OidcClient({
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    scope: config.oidcScope,
    redirect_uri: NATIVE_REDIRECT_URI,
    post_logout_redirect_uri: NATIVE_LOGOUT_URI,
    response_type: "code",
    // Only PKCE and state values, for the moment the browser is open. Never a token.
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
  });
  let accessToken: string | null = null;
  let idToken: string | undefined;
  let pendingRedirect: string | null = null;

  return {
    getAccessToken: async () => accessToken,
    signIn: async (returnTo) => {
      const request = await client.createSigninRequest({ state: { returnTo } });
      await bridge.openExternal(request.url);
    },
    acceptRedirect: (url) => {
      if (!url.startsWith(`${NATIVE_REDIRECT_URI}?`)) {
        return false;
      }
      pendingRedirect = url;
      return true;
    },
    completeSignIn: async () => {
      const url = pendingRedirect;
      pendingRedirect = null;
      if (url === null) {
        throw new Error("No sign-in is in progress");
      }
      const response = await client.processSigninResponse(url);
      accessToken = response.access_token;
      idToken = response.id_token;
      const state = response.userState as { returnTo?: unknown } | undefined;
      return safeReturnPath(state?.returnTo);
    },
    clearSession: async () => {
      accessToken = null;
      idToken = undefined;
    },
    signOut: async () => {
      const hint = idToken;
      accessToken = null;
      idToken = undefined;
      const request = await client.createSignoutRequest(hint ? { id_token_hint: hint } : {});
      await bridge.openExternal(request.url);
    },
  };
}
