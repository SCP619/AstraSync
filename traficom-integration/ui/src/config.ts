export interface AppConfig {
  apiBaseUrl: string;
  oidcAuthority: string;
  oidcClientId: string;
  oidcScope: string;
}

type RawEnv = Record<string, string | boolean | undefined>;

const REQUIRED = {
  apiBaseUrl: "VITE_API_BASE_URL",
  oidcAuthority: "VITE_OIDC_AUTHORITY",
  oidcClientId: "VITE_OIDC_CLIENT_ID",
  oidcScope: "VITE_OIDC_SCOPE",
} as const;

/** No defaults: a build must never fall back silently to another backend or identity provider. */
export function readConfig(env: RawEnv): AppConfig | { missing: string[] } {
  const missing = Object.values(REQUIRED).filter((name) => !env[name]);
  if (missing.length > 0) {
    return { missing };
  }
  return {
    apiBaseUrl: String(env[REQUIRED.apiBaseUrl]).replace(/\/$/, ""),
    oidcAuthority: String(env[REQUIRED.oidcAuthority]),
    oidcClientId: String(env[REQUIRED.oidcClientId]),
    oidcScope: String(env[REQUIRED.oidcScope]),
  };
}
