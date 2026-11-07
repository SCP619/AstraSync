import { StrictMode, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { createWebOidcAdapter } from "./auth/webOidcAdapter";
import { readConfig, type AppConfig } from "./config";
import "./styles.css";

function Root({ config }: { config: AppConfig }) {
  const auth = useMemo(() => createWebOidcAdapter(config), [config]);
  return (
    <BrowserRouter>
      <App auth={auth} apiBaseUrl={config.apiBaseUrl} />
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
