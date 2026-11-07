// Windows (Tauri) and Android (Capacitor) adapters. Plugins load only inside their own package, so
// the web preview never runs native code. Not yet exercised in a packaged build: see README.
import type { AuthAdapter } from "../auth/adapter";
import { createNativeOidcAdapter, NATIVE_REDIRECT_URI } from "../auth/nativeOidcAdapter";
import type { AppConfig } from "../config";
import { alertPathFromPush, type PlatformAdapter } from "./types";

export interface NativeRuntime {
  platform: PlatformAdapter;
  auth: AuthAdapter;
}

interface CapacitorGlobal {
  isNativePlatform?: () => boolean;
}

export function isTauri(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export function isCapacitor(): boolean {
  return (window as { Capacitor?: CapacitorGlobal }).Capacitor?.isNativePlatform?.() === true;
}

function emitter() {
  const listeners = new Set<(path: string) => void>();
  return {
    emit: (path: string) => listeners.forEach((listener) => listener(path)),
    on: (listener: (path: string) => void) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export async function createTauriRuntime(config: AppConfig): Promise<NativeRuntime> {
  const [{ openUrl }, deepLink, notifications] = await Promise.all([
    import("@tauri-apps/plugin-opener"),
    import("@tauri-apps/plugin-deep-link"),
    import("@tauri-apps/plugin-notification"),
  ]);
  const paths = emitter();
  const auth = createNativeOidcAdapter(config, { openExternal: openUrl });
  const handle = (urls: string[]) => {
    for (const url of urls) {
      if (auth.acceptRedirect(url)) {
        paths.emit("/auth/callback");
      }
    }
  };
  await deepLink.onOpenUrl(handle);
  handle((await deepLink.getCurrent()) ?? []);

  return {
    auth,
    platform: {
      name: "windows",
      notify: async (alert) => {
        let granted = await notifications.isPermissionGranted();
        if (!granted) {
          granted = (await notifications.requestPermission()) === "granted";
        }
        if (granted) {
          notifications.sendNotification({ title: alert.safe_title, body: alert.safe_preview });
        }
      },
      // Windows alerts arrive over the in-app stream while the app runs. There is no server push.
      enablePush: async () => "UNSUPPORTED",
      onOpenPath: (listener) => paths.on(listener),
    },
  };
}

export async function createCapacitorRuntime(
  config: AppConfig,
  pushConfigured: boolean,
): Promise<NativeRuntime> {
  const [{ App }, { Browser }, { PushNotifications }] = await Promise.all([
    import("@capacitor/app"),
    import("@capacitor/browser"),
    import("@capacitor/push-notifications"),
  ]);
  const paths = emitter();
  const auth = createNativeOidcAdapter(config, {
    openExternal: (url) => Browser.open({ url }),
  });
  await App.addListener("appUrlOpen", ({ url }) => {
    if (auth.acceptRedirect(url)) {
      void Browser.close();
      paths.emit("/auth/callback");
    }
  });

  return {
    auth,
    platform: {
      name: "android",
      // Android alerts arrive by push. A local copy would only duplicate them.
      notify: async () => undefined,
      enablePush: async (register) => {
        // Registering without a Firebase project configured would crash the app.
        if (!pushConfigured) {
          return "NOT_CONFIGURED";
        }
        const { receive } = await PushNotifications.requestPermissions();
        if (receive !== "granted") {
          return "DENIED";
        }
        await PushNotifications.addListener("registration", ({ value }) => {
          void register("ANDROID", value);
        });
        await PushNotifications.addListener(
          "pushNotificationActionPerformed",
          ({ notification }) => {
            const path = alertPathFromPush(notification.data);
            if (path !== null) {
              paths.emit(path);
            }
          },
        );
        await PushNotifications.register();
        return "GRANTED";
      },
      onOpenPath: (listener) => paths.on(listener),
    },
  };
}

export { NATIVE_REDIRECT_URI };
