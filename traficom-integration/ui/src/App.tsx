import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiError, createApiClient, type CaseList, type Me } from "./api/client";
import type { AuthAdapter } from "./auth/adapter";
import {
  describeError,
  MeContext,
  RequestId,
  SessionContext,
  useLoad,
  useMe,
  useSession,
  type Session,
  type SessionState,
  type SignInNotice,
} from "./shared";
import { SourceLibraryPage } from "./sources/SourceLibraryPage";

function SessionProvider({
  auth,
  apiBaseUrl,
  fetchImpl,
  children,
}: {
  auth: AuthAdapter;
  apiBaseUrl: string;
  fetchImpl?: typeof fetch;
  children: React.ReactNode;
}) {
  const [state, setState] = useState<SessionState>("LOADING");
  const [notice, setNotice] = useState<SignInNotice>(null);
  const token = useRef<string | null>(null);

  const refreshToken = useCallback(async () => {
    token.current = await auth.getAccessToken();
    setState(token.current === null ? "SIGNED_OUT" : "SIGNED_IN");
  }, [auth]);

  useEffect(() => {
    void refreshToken();
  }, [refreshToken]);

  const api = useMemo(
    () =>
      createApiClient({
        baseUrl: apiBaseUrl,
        getAccessToken: () => token.current,
        onUnauthenticated: (error: ApiError) => {
          // The server rejected this session: forget it locally so no stale view stays up.
          token.current = null;
          void auth.clearSession();
          setNotice(error.code === "MFA_REQUIRED" ? "MFA_REQUIRED" : "SESSION_ENDED");
          setState("SIGNED_OUT");
        },
        ...(fetchImpl ? { fetch: fetchImpl } : {}),
      }),
    [apiBaseUrl, auth, fetchImpl],
  );

  const session = useMemo<Session>(
    () => ({
      state,
      notice,
      api,
      signIn: (returnTo) => auth.signIn(returnTo),
      signOut: async () => {
        token.current = null;
        setState("SIGNED_OUT");
        await auth.signOut();
      },
      sessionEstablished: async () => {
        setNotice(null);
        await refreshToken();
      },
      signInFailed: () => {
        setNotice("SIGN_IN_FAILED");
        setState("SIGNED_OUT");
      },
    }),
    [state, notice, api, auth, refreshToken],
  );

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

const NOTICE_TEXT: Record<Exclude<SignInNotice, null>, string> = {
  SESSION_ENDED: "Your session has ended. Sign in again to continue.",
  MFA_REQUIRED: "AstraSync requires multi-factor sign-in. Sign in again using a second factor.",
  SIGN_IN_FAILED: "Sign-in could not be completed. Try again.",
};

function LoginPage() {
  const { state, notice, signIn } = useSession();
  const location = useLocation();
  const [starting, setStarting] = useState(false);
  const [failed, setFailed] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  if (state === "SIGNED_IN") {
    return <Navigate to={from} replace />;
  }

  async function start() {
    setStarting(true);
    setFailed(false);
    try {
      await signIn(from);
    } catch {
      setFailed(true);
      setStarting(false);
    }
  }

  return (
    <main className="center-page">
      <section className="panel sign-in" aria-labelledby="sign-in-title">
        <p className="brand">AstraSync</p>
        <h1 id="sign-in-title">Sign in</h1>
        <p className="muted">
          Spectrum coordination workspace, for authorised personnel only. Your organisation's
          identity provider handles sign-in and multi-factor authentication.
        </p>
        {notice !== null && <p role="status" className="notice">{NOTICE_TEXT[notice]}</p>}
        {failed && (
          <p role="alert" className="notice">
            The identity provider could not be reached. Try again.
          </p>
        )}
        <button type="button" className="primary" onClick={() => void start()} disabled={starting}>
          {starting ? "Opening sign-in…" : "Continue to sign-in"}
        </button>
      </section>
    </main>
  );
}

function CallbackPage({ auth }: { auth: AuthAdapter }) {
  const { sessionEstablished, signInFailed } = useSession();
  const navigate = useNavigate();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) {
      return; // The authorization code is single use, and StrictMode runs effects twice.
    }
    started.current = true;
    auth
      .completeSignIn()
      .then(async (returnTo) => {
        await sessionEstablished();
        navigate(returnTo, { replace: true });
      })
      .catch(() => {
        signInFailed();
        navigate("/login", { replace: true });
      });
  }, [auth, navigate, sessionEstablished, signInFailed]);

  return (
    <main className="center-page">
      <p role="status">Completing sign-in…</p>
    </main>
  );
}

function RequireSession({ children }: { children: React.ReactNode }) {
  const { state } = useSession();
  const location = useLocation();
  if (state === "LOADING") {
    return (
      <main className="center-page">
        <p role="status">Loading…</p>
      </main>
    );
  }
  if (state === "SIGNED_OUT") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

const ROLE_TEXT: Record<Me["roles"][number], string> = {
  ANALYST: "Analyst",
  REVIEWER: "Reviewer",
  ADMINISTRATOR: "Administrator",
  DEMO_VIEWER: "Demo viewer",
};

/** Confirms identity with the server before anything inside it renders. */
function AppShell({ children }: { children: React.ReactNode }) {
  const { api, signOut } = useSession();
  const load = useCallback((signal: AbortSignal) => api.getMe(signal), [api]);
  const { result, retry } = useLoad<Me>(load);

  const signOutButton = (
    <button type="button" onClick={() => void signOut()}>Sign out</button>
  );

  if (result === null) {
    return (
      <main className="center-page">
        <p role="status">Checking your access…</p>
      </main>
    );
  }
  if (result.data === undefined) {
    return (
      <main className="center-page">
        <section className="panel sign-in">
          <h1>{result.error instanceof ApiError && result.error.code === "FORBIDDEN"
            ? "No access to AstraSync"
            : "AstraSync is unavailable"}</h1>
          <p role="alert">{describeError(result.error)}</p>
          <RequestId error={result.error} />
          <div className="actions">
            <button type="button" onClick={retry}>Try again</button>
            {signOutButton}
          </div>
        </section>
      </main>
    );
  }

  const me = result.data;
  return (
    <MeContext.Provider value={me}>
      <header className="top-bar">
        <span className="brand">AstraSync</span>
        <nav aria-label="Main" className="main-nav">
          <NavLink to="/dashboard">Overview</NavLink>
          {me.capabilities.includes("SOURCE_HEALTH_READ") && <NavLink to="/sources">Source library</NavLink>}
        </nav>
        <span className="environment" data-environment={me.environment}>
          {me.environment} environment
        </span>
        <span className="spacer" />
        {signOutButton}
      </header>
      {children}
    </MeContext.Provider>
  );
}

function CasesPanel() {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.listCases(signal), [api]);
  const { result, retry } = useLoad<CaseList>(load);

  let content: React.ReactNode;
  if (result === null) {
    content = <p role="status">Loading cases…</p>;
  } else if (result.error instanceof ApiError && result.error.code === "NOT_IMPLEMENTED") {
    content = (
      <p className="muted">
        Your access to cases is confirmed, but case data is not available yet. The server reports
        that this feature is not implemented.
      </p>
    );
  } else if (result.error !== undefined) {
    content = (
      <>
        <p role="alert">{describeError(result.error)}</p>
        <RequestId error={result.error} />
        <button type="button" onClick={retry}>Try again</button>
      </>
    );
  } else if (result.data?.items.length === 0) {
    content = <p className="muted">No cases yet.</p>;
  } else {
    content = <p>{result.data?.items.length} cases loaded.</p>;
  }

  return (
    <section className="panel" aria-labelledby="cases-title">
      <h2 id="cases-title">Cases</h2>
      {content}
    </section>
  );
}

function DashboardPage() {
  const me = useMe();
  return (
    <main className="content">
      <h1>Overview</h1>
      <section className="panel" aria-labelledby="access-title">
        <h2 id="access-title">Your access</h2>
        <p className="muted small">Confirmed by the server for this session.</p>
        <dl>
          <dt>Role</dt>
          <dd>
            {me.roles.length > 0
              ? me.roles.map((role) => ROLE_TEXT[role]).join(", ")
              : "No role assigned. Contact your AstraSync administrator."}
          </dd>
          <dt>Organisation</dt>
          <dd><code>{me.tenant_id}</code></dd>
          <dt>User ID</dt>
          <dd><code>{me.user_id}</code></dd>
        </dl>
      </section>
      {me.capabilities.includes("CASE_READ") && <CasesPanel />}
      <section className="panel" aria-labelledby="permissions-title">
        <h2 id="permissions-title">Permissions</h2>
        <ul className="chips">
          {me.capabilities.map((capability) => (
            <li key={capability}><code>{capability}</code></li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function SourcesRoute() {
  const me = useMe();
  if (!me.capabilities.includes("SOURCE_HEALTH_READ")) {
    return (
      <main className="content">
        <h1>Source library</h1>
        <p role="alert">Your account is not authorised for this. Contact your AstraSync administrator.</p>
      </main>
    );
  }
  return <SourceLibraryPage />;
}

export function App({
  auth,
  apiBaseUrl,
  fetchImpl,
}: {
  auth: AuthAdapter;
  apiBaseUrl: string;
  fetchImpl?: typeof fetch;
}) {
  return (
    <SessionProvider auth={auth} apiBaseUrl={apiBaseUrl} {...(fetchImpl ? { fetchImpl } : {})}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<CallbackPage auth={auth} />} />
        <Route
          path="/dashboard"
          element={<RequireSession><AppShell><DashboardPage /></AppShell></RequireSession>}
        />
        <Route
          path="/sources"
          element={<RequireSession><AppShell><SourcesRoute /></AppShell></RequireSession>}
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </SessionProvider>
  );
}
