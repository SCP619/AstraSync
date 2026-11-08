/**
 * The signed-in layout: sidebar on wide screens, bottom navigation on narrow ones (DBD section 3).
 * Adapted from the Lovable design-system prototype (project 97dc87fa, `app-shell.tsx`) to this
 * app's router, capabilities and live alert counts. Only one navigation is rendered at a time,
 * so links are never announced twice.
 */
import { Bell, Briefcase, FileSearch, FlaskConical, Gauge, Library, LogOut, MapPin, Radio, Sparkles, Upload, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "./cn";

/** The shell shows the environment and the user's role names; never identifiers. */
export type ShellUser = {
  environment: string;
  capabilities: string[];
  roles?: string[];
};

const GROUPS = ["Analyse", "Investigate", "Data", "Settings"];

const ROLE_TEXT: Record<string, string> = {
  ADMINISTRATOR: "Administrator",
  ANALYST: "Analyst",
  REVIEWER: "Reviewer",
  DEMO_VIEWER: "Demo viewer",
  AUDITOR: "Auditor",
};

type Item = { to: string; label: string; icon: typeof Gauge; capability?: string; group: string };

const ITEMS: Item[] = [
  { to: "/dashboard", label: "Dashboard", icon: Gauge, group: "Analyse" },
  { to: "/cases", label: "Cases", icon: Briefcase, capability: "CASE_READ", group: "Investigate" },
  { to: "/assistant", label: "AI agent", icon: Sparkles, capability: "CASE_READ", group: "Analyse" },
  { to: "/alerts", label: "Alerts", icon: Bell, capability: "ALERT_READ", group: "Investigate" },
  { to: "/sources", label: "Source library", icon: Library, capability: "SOURCE_HEALTH_READ", group: "Data" },
  { to: "/uploads", label: "Upload", icon: Upload, capability: "UPLOAD_MANAGE", group: "Data" },
  { to: "/ific", label: "IFIC issues", icon: FileSearch, capability: "SOURCE_READ", group: "Investigate" },
  { to: "/finland", label: "Finland relevance", icon: MapPin, capability: "SOURCE_READ", group: "Investigate" },
  { to: "/admin/users", label: "Users and access", icon: Users, capability: "ADMIN_USERS", group: "Settings" },
];

const NARROW = "(max-width: 767px)";

function useNarrow(): boolean {
  const query = typeof window !== "undefined" && window.matchMedia ? window.matchMedia(NARROW) : null;
  const [narrow, setNarrow] = useState(query?.matches ?? false);
  useEffect(() => {
    if (!query) return;
    const update = () => setNarrow(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, [query]);
  return narrow;
}

function AlertCount({ count, more }: { count: number; more: boolean }) {
  if (!count) return null;
  const text = `${count}${more ? "+" : ""}`;
  return (
    <>
      <span
        aria-hidden
        className="num ml-auto min-w-5 rounded-sm bg-accent px-1.5 text-center text-2xs font-semibold text-accent-foreground"
      >
        {text}
      </span>
      <span className="sr-only"> ({text})</span>
    </>
  );
}

export function AppShell({
  user,
  openAlerts,
  moreAlerts,
  onSignOut,
  children,
}: {
  user: ShellUser;
  openAlerts: number;
  moreAlerts: boolean;
  onSignOut: () => void;
  children: ReactNode;
}) {
  const narrow = useNarrow();
  const items = ITEMS.filter((item) => !item.capability || user.capabilities.includes(item.capability));
  const link = (item: Item, mobile: boolean) => (
    <NavLink
      key={item.to}
      to={item.to}
      className={({ isActive }) =>
        mobile
          ? cn(
              "flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 text-2xs text-muted-foreground",
              isActive && "text-accent",
            )
          : cn(isActive && "active")
      }
    >
      <item.icon className={mobile ? "size-5" : "size-4"} aria-hidden />
      {item.label}
      {item.to === "/alerts" && <AlertCount count={openAlerts} more={moreAlerts} />}
    </NavLink>
  );

  return (
    <div className="flex min-h-screen w-full flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to main content
      </a>
      {user.environment === "DEMO" && (
        <div
          role="note"
          className="hatch flex items-center justify-center gap-2 border-b border-review/40 bg-review-soft px-3 py-1 text-2xs font-semibold tracking-wider text-review"
        >
          <FlaskConical className="size-3.5" aria-hidden />
          DEMO environment: synthetic and made-up data only
        </div>
      )}
      <div className={narrow ? "flex flex-1" : "app-shell flex-1"}>
        {!narrow && (
          <nav aria-label="Main" className="sidebar">
            <span className="brand">
              <Radio aria-hidden />
              AstraSync
            </span>
            {GROUPS.filter((group) => items.some((item) => item.group === group)).map((group) => (
              <div className="nav-group" key={group}>
                <span className="nav-group-title">{group}</span>
                {items.filter((item) => item.group === group).map((item) => link(item, false))}
              </div>
            ))}
          </nav>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="topbar">
            {narrow && (
              <span className="flex items-center gap-2">
                <Radio className="size-5 text-accent" aria-hidden />
                <span className="brand font-semibold">AstraSync</span>
              </span>
            )}
            <span className="ml-auto" />
            <span className="role-label small muted whitespace-nowrap">
              {user.roles && user.roles.length > 0
                ? user.roles.map((role) => ROLE_TEXT[role] ?? role).join(", ")
                : "No role assigned"}
            </span>
            <span
              className="environment hidden sm:inline-flex"
              data-environment={user.environment}
            >
              {user.environment} environment
            </span>
            <button type="button" className="touch inline-flex items-center gap-1.5 whitespace-nowrap" onClick={onSignOut}>
              <LogOut className="size-4" aria-hidden />
              Sign out
            </button>
          </header>
          <div id="main-content" tabIndex={-1} className={cn("flex-1", narrow && "pb-16")}>
            {children}
          </div>
        </div>
      </div>
      {narrow && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)]"
        >
          {items.map((item) => link(item, true))}
        </nav>
      )}
    </div>
  );
}
