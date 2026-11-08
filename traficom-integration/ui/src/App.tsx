import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { ApiError, createApiClient, type CaseList, type Me } from "./api/client";
import { SignInStepError, type AuthAdapter } from "./auth/adapter";
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
import { AdminUsersPage } from "./admin/AdminUsersPage";
import { AlertDetailPage, AlertsPage } from "./alerts/AlertsPage";
import { CaseInspectorPage } from "./cases/CaseInspectorPage";
import { CaseListPage } from "./cases/CaseListPage";
import { AppShell as ShellLayout } from "./components/AppShell";
import { OperationsPanel } from "./components/OperationsPanel";
import { FinlandRelevancePage } from "./relevance/FinlandRelevancePage";
import { IficIssuesPage } from "./relevance/IficIssuesPage";
import { webPlatform, type PlatformAdapter, type PushPermission } from "./platform/types";
import { SourceLibraryPage } from "./sources/SourceLibraryPage";
import { UploadPage } from "./sources/UploadPage";

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
      sessionEnded: () => {
        token.current = null;
        void auth.clearSession();
        setNotice("SESSION_ENDED");
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
  const [failed, setFailed] = useState<string | null>(null);
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  if (state === "SIGNED_IN") {
    return <Navigate to={from} replace />;
  }

  async function start() {
    setStarting(true);
    setFailed(null);
    try {
      await signIn(from);
    } catch (error) {
      setFailed(
        error instanceof SignInStepError && error.step === "BROWSER_UNAVAILABLE"
          ? "Your web browser could not be opened for sign-in. Check that a default browser is set, then try again."
          : "The identity provider could not be reached. Try again.",
      );
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
        {failed !== null && <p role="alert" className="notice">{failed}</p>}
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

const STREAM_RETRY_MS = 5000;
const INBOX_POLL_MS = 60000;

interface AlertActivity {
  openCount: number | null;
  more: boolean;
  version: number;
  pushPermission: PushPermission | null;
  changed: () => void;
}

/** Live alert state: a stream with reconnects, and a slow poll so a broken stream still recovers. */
function useAlertActivity(platform: PlatformAdapter, me: Me | null): AlertActivity {
  const { api, sessionEnded } = useSession();
  const [version, setVersion] = useState(0);
  const [open, setOpen] = useState<{ count: number; more: boolean } | null>(null);
  const [pushPermission, setPushPermission] = useState<PushPermission | null>(null);
  const changed = useCallback(() => setVersion((value) => value + 1), []);
  const canRead = me?.capabilities.includes("ALERT_READ") ?? false;
  const canRegister = me?.capabilities.includes("DEVICE_MANAGE") ?? false;

  useEffect(() => {
    if (!canRead) {
      return undefined;
    }
    const controller = new AbortController();
    api
      .listAlerts("OPEN", undefined, controller.signal)
      .then((page) => setOpen({ count: page.items.length, more: page.next_cursor !== null }))
      .catch(() => undefined);
    const timer = window.setInterval(changed, INBOX_POLL_MS);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [api, canRead, version, changed]);

  useEffect(() => {
    if (!canRead) {
      return undefined;
    }
    const controller = new AbortController();
    let retry: number | undefined;
    const connect = () => {
      api
        .streamAlerts(
          (alert) => {
            void platform.notify(alert);
            changed();
          },
          controller.signal,
          sessionEnded,
        )
        .catch(() => undefined)
        .finally(() => {
          if (!controller.signal.aborted) {
            retry = window.setTimeout(connect, STREAM_RETRY_MS);
          }
        });
    };
    connect();
    return () => {
      controller.abort();
      window.clearTimeout(retry);
    };
  }, [api, canRead, platform, changed, sessionEnded]);

  useEffect(() => {
    if (!canRegister) {
      return;
    }
    platform
      .enablePush(async (name, token) => {
        await api.registerDevice(name, token);
      })
      .then(setPushPermission)
      .catch(() => setPushPermission("NOT_CONFIGURED"));
  }, [api, canRegister, platform]);

  return {
    openCount: open?.count ?? null,
    more: open?.more ?? false,
    version,
    pushPermission,
    changed,
  };
}

const AlertActivityContext = createContext<AlertActivity | null>(null);

function useAlertContext(): AlertActivity {
  const value = useContext(AlertActivityContext);
  if (value === null) {
    throw new Error("useAlertContext needs an AppShell");
  }
  return value;
}

function AlertsRoute() {
  const activity = useAlertContext();
  return <AlertsPage pushPermission={activity.pushPermission} refreshKey={activity.version} />;
}

function AlertDetailRoute() {
  const activity = useAlertContext();
  return <AlertDetailPage onChanged={activity.changed} />;
}

/** Opens paths the OS hands the app: a sign-in redirect or a tapped notification. */
function DeepLinks({ platform }: { platform: PlatformAdapter }) {
  const navigate = useNavigate();
  useEffect(() => platform.onOpenPath((path) => navigate(path)), [platform, navigate]);
  return null;
}

const ROLE_TEXT: Record<Me["roles"][number], string> = {
  ANALYST: "Analyst",
  REVIEWER: "Reviewer",
  ADMINISTRATOR: "Administrator",
  DEMO_VIEWER: "Demo viewer",
};

/** Confirms identity with the server before anything inside it renders. */
function AppShell({
  platform,
  children,
}: {
  platform: PlatformAdapter;
  children: React.ReactNode;
}) {
  const { api, signOut } = useSession();
  const load = useCallback((signal: AbortSignal) => api.getMe(signal), [api]);
  const { result, retry } = useLoad<Me>(load);
  const activity = useAlertActivity(platform, result?.data ?? null);

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
      <AlertActivityContext.Provider value={activity}>
      <ShellLayout
        user={me}
        openAlerts={activity.openCount ?? 0}
        moreAlerts={Boolean(activity.more)}
        onSignOut={() => void signOut()}
      >
        {children}
      </ShellLayout>
      </AlertActivityContext.Provider>
    </MeContext.Provider>
  );
}

function CasesPanel() {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.listCases({}, undefined, signal), [api]);
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
    content = (
      <p>
        {result.data?.next_cursor === null ? "" : "At least "}
        {result.data?.items.length} loaded. <Link to="/cases">Open cases</Link>
      </p>
    );
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
      {me.capabilities.includes("JOB_READ") && <OperationsPanel />}
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

function RequireCapability({
  capability,
  children,
}: {
  capability: Me["capabilities"][number];
  children: React.ReactNode;
}) {
  const me = useMe();
  if (!me.capabilities.includes(capability)) {
    return (
      <main className="content">
        <p role="alert">Your account is not authorised for this. Contact your AstraSync administrator.</p>
      </main>
    );
  }
  return <>{children}</>;
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
  platform = webPlatform,
}: {
  auth: AuthAdapter;
  apiBaseUrl: string;
  fetchImpl?: typeof fetch;
  platform?: PlatformAdapter;
}) {
  const shell = (page: React.ReactNode) => (
    <RequireSession>
      <AppShell platform={platform}>{page}</AppShell>
    </RequireSession>
  );
  return (
    <SessionProvider auth={auth} apiBaseUrl={apiBaseUrl} {...(fetchImpl ? { fetchImpl } : {})}>
      <DeepLinks platform={platform} />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/auth/callback" element={<CallbackPage auth={auth} />} />
        <Route
          path="/dashboard"
          element={shell(<DashboardPage />)}
        />
        <Route
          path="/sources"
          element={shell(<SourcesRoute />)}
        />
        <Route
          path="/cases"
          element={shell(<RequireCapability capability="CASE_READ"><CaseListPage /></RequireCapability>)}
        />
        <Route
          path="/cases/:caseId"
          element={shell(<RequireCapability capability="CASE_READ"><CaseInspectorPage /></RequireCapability>)}
        />
        <Route
          path="/alerts"
          element={shell(<RequireCapability capability="ALERT_READ"><AlertsRoute /></RequireCapability>)}
        />
        <Route
          path="/alerts/:alertId"
          element={shell(<RequireCapability capability="ALERT_READ"><AlertDetailRoute /></RequireCapability>)}
        />
        <Route
          path="/uploads"
          element={shell(<RequireCapability capability="UPLOAD_MANAGE"><UploadPage /></RequireCapability>)}
        />
        <Route
          path="/finland"
          element={shell(<RequireCapability capability="SOURCE_READ"><FinlandRelevancePage /></RequireCapability>)}
        />
        <Route
          path="/ific"
          element={shell(<RequireCapability capability="SOURCE_READ"><IficIssuesPage /></RequireCapability>)}
        />
        <Route
          path="/admin/users"
          element={shell(<RequireCapability capability="ADMIN_USERS"><AdminUsersPage /></RequireCapability>)}
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </SessionProvider>
  );
}
