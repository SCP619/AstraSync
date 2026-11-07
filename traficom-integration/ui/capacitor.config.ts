import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "fi.astrasync.app",
  appName: "AstraSync",
  webDir: "dist",
  android: {
    allowMixedContent: false,
    // Only for local automated device tests (ui/e2e). Off in every other build.
    webContentsDebuggingEnabled: process.env.ASTRASYNC_E2E_WEBVIEW_DEBUG === "true",
  },
};

export default config;
