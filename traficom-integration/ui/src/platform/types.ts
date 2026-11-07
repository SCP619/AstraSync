import type { Schemas } from "../api/client";

export type PushPermission = "GRANTED" | "DENIED" | "NOT_CONFIGURED" | "UNSUPPORTED";

/**
 * What differs between the web preview, Windows and Android. Everything else is shared, and no
 * adapter holds a permission, an RF result or a case detail: those always come from the server.
 */
export interface PlatformAdapter {
  name: "web" | "windows" | "android";
  /** A local OS notification, with only the server's safe title. */
  notify(alert: Schemas["AlertSummary"]): Promise<void>;
  /** Asks for push permission and hands any device token to `register`. */
  enablePush(
    register: (platform: Schemas["DevicePlatform"], token: string) => Promise<void>,
  ): Promise<PushPermission>;
  /** Tells the app to open a path, such as from a tapped notification or a sign-in redirect. */
  onOpenPath(listener: (path: string) => void): () => void;
}

export const webPlatform: PlatformAdapter = {
  name: "web",
  notify: async () => undefined,
  enablePush: async () => "UNSUPPORTED",
  onOpenPath: () => () => undefined,
};

/** Only an opaque alert ID is ever read from a push. Details are fetched after re-authorization. */
export function alertPathFromPush(data: unknown): string | null {
  const alertId = (data as { alert_id?: unknown } | null | undefined)?.alert_id;
  if (typeof alertId !== "string" || !/^[A-Za-z0-9._:-]{1,128}$/.test(alertId)) {
    return null;
  }
  return `/alerts/${encodeURIComponent(alertId)}`;
}
