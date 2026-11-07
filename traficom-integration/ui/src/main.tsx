import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import type { AuthAdapter } from "./auth/adapter";
import { createWebOidcAdapter } from "./auth/webOidcAdapter";
import { webPlatform, type PlatformAdapter } from "./platform/types";
import { readConfig, type AppConfig } from "./config";
import "./design/tokens.css";
import "./styles.css";

async function createRuntime(
  config: AppConfig,
): Promise<{ auth: AuthAdapter; platform: PlatformAdapter }> {
  const native = await import("./platform/native");
  if (native.isTauri()) {
    return native.createTauriRuntime(config);
  }
  if (native.isCapacitor()) {
    return native.createCapacitorRuntime(config, import.meta.env.VITE_PUSH_CONFIGURED === "true");
  }
  return { auth: createWebOidcAdapter(config), platform: webPlatform };
}

function Root({ config }: { config: AppConfig }) {
  const [runtime, setRuntime] = useState<{ auth: AuthAdapter; platform: PlatformAdapter } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    createRuntime(config).then(setRuntime).catch(() => setFailed(true));
  }, [config]);
  if (failed) {
    return (
      <main className="center-page">
        <p role="alert">AstraSync could not start on this device.</p>
      </main>
    );
  }
  if (runtime === null) {
    return (
      <main className="center-page">
        <p role="status">Starting…</p>
      </main>
    );
  }
  return (
    <BrowserRouter>
      <App auth={runtime.auth} apiBaseUrl={config.apiBaseUrl} platform={runtime.platform} />
    </BrowserRouter>
  );
}

const config = readConfig(import.meta.env);
const container = document.getElementById("root");
if (container === null) {
  throw new Error("Missing root element");
}

createRoot(container).render(
  <StrictMode>
    {"missing" in config ? (
      <main className="center-page">
        <section className="panel sign-in">
          <h1>AstraSync is not configured</h1>
          <p role="alert">Missing settings: {config.missing.join(", ")}</p>
        </section>
      </main>
    ) : (
      <Root config={config} />
    )}
  </StrictMode>,
);
