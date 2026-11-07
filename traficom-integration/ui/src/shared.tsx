import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, type ApiClient, type Me } from "./api/client";

export type SignInNotice = "SESSION_ENDED" | "MFA_REQUIRED" | "SIGN_IN_FAILED" | null;
export type SessionState = "LOADING" | "SIGNED_OUT" | "SIGNED_IN";

export interface Session {
  state: SessionState;
  notice: SignInNotice;
  api: ApiClient;
  signIn(returnTo: string): Promise<void>;
  signOut(): Promise<void>;
  sessionEstablished(): Promise<void>;
  signInFailed(): void;
}

export const SessionContext = createContext<Session | null>(null);
export const MeContext = createContext<Me | null>(null);

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (session === null) {
    throw new Error("useSession needs a SessionProvider");
  }
  return session;
}

export function useMe(): Me {
  const me = useContext(MeContext);
  if (me === null) {
    throw new Error("useMe needs an AppShell");
  }
  return me;
}

export function describeError(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Something went wrong.";
  }
  switch (error.code) {
    case "FORBIDDEN":
      return "Your account is not authorised for this. Contact your AstraSync administrator.";
    case "SERVICE_UNAVAILABLE":
      return "AstraSync cannot verify your sign-in right now. Try again shortly.";
    case "NETWORK_ERROR":
      return "The AstraSync server could not be reached. Check your connection and try again.";
    default:
      return error.message;
  }
}

export function useLoad<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [result, setResult] = useState<{ data?: T; error?: unknown } | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setResult(null);
    load(controller.signal)
      .then((data) => setResult({ data }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setResult({ error });
        }
      });
    return () => controller.abort();
  }, [load, attempt]);

  return { result, retry: () => setAttempt((value) => value + 1) };
}

export function RequestId({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.requestId !== null) {
    return <p className="muted small">Request ID: <code>{error.requestId}</code></p>;
  }
  return null;
}
