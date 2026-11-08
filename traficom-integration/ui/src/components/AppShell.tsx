/**
 * The signed-in layout: sidebar on wide screens, bottom navigation on narrow ones (DBD section 3).
 * Adapted from the Lovable design-system prototype (project 97dc87fa, `app-shell.tsx`) to this
 * app's router, capabilities and live alert counts. Only one navigation is rendered at a time,
 * so links are never announced twice.
 */
import { Bell, Briefcase, FileSearch, FlaskConical, Gauge, Library, LogOut, MapPin, Radio, Upload, Users } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { cn } from "./cn";

/** Identity and roles are shown on the overview page, so the shell only needs these. */
export type ShellUser = {
  environment: string;
  capabilities: string[];
};

type Item = { to: string; label: string; icon: typeof Gauge; capability?: string };

const ITEMS: Item[] = [
  { to: "/dashboard", label: "Overview", icon: Gauge },
  { to: "/cases", label: "Cases", icon: Briefcase, capability: "CASE_READ" },
  { to: "/alerts", label: "Alerts", icon: Bell, capability: "ALERT_READ" },
  { to: "/sources", label: "Source library", icon: Library, capability: "SOURCE_HEALTH_READ" },
  { to: "/uploads", label: "Upload", icon: Upload, capability: "UPLOAD_MANAGE" },
  { to: "/ific", label: "IFIC issues", icon: FileSearch, capability: "SOURCE_READ" },
  { to: "/finland", label: "Finland relevance", icon: MapPin, capability: "SOURCE_READ" },
  { to: "/admin/users", label: "Users and access", icon: Users, capability: "ADMIN_USERS" },
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
          : cn(
              "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-muted-foreground no-underline hover:bg-raised hover:text-foreground",
              isActive && "bg-raised font-medium text-foreground shadow-[inset_2px_0_0_var(--accent)]",
            )
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
      <div className="flex flex-1">
        {!narrow && (
          <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-border bg-surface">
            <div className="flex items-center gap-2 border-b border-border px-4 py-3.5">
              <Radio className="size-5 text-accent" aria-hidden />
              <span className="brand font-semibold tracking-tight">AstraSync</span>
            </div>
            <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto p-2">
              {items.map((item) => link(item, false))}
            </nav>
          </aside>
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-border bg-background/95 px-4 py-2 backdrop-blur">
            {narrow && (
              <span className="flex items-center gap-2">
                <Radio className="size-5 text-accent" aria-hidden />
                <span className="brand font-semibold">AstraSync</span>
              </span>
            )}
            <span className="ml-auto" />
            <span
              className="environment num hidden whitespace-nowrap rounded-md border border-border px-2 py-1 text-2xs sm:inline"
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
