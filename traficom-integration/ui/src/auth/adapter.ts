/**
 * Platform seam for sign-in. The web preview uses the browser; the Tauri and Capacitor builds will
 * provide the same interface with the system browser and OS-protected credential storage.
 */
export interface AuthAdapter {
  /** The current access token, or null when signed out. */
  getAccessToken(): Promise<string | null>;
  /** Starts Authorization Code + PKCE sign-in. `prompt` forces a fresh choice of account. */
  signIn(returnTo: string): Promise<void>;
  /** Finishes sign-in on the callback route and returns where to go next. */
  completeSignIn(): Promise<string>;
  /** Forgets local tokens only, for a session the server no longer accepts. */
  clearSession(): Promise<void>;
  /** Forgets local tokens and ends the identity provider session. */
  signOut(): Promise<void>;
}
