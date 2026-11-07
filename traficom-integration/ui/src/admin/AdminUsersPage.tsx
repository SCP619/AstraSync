/**
 * User, role and source-entitlement administration (ADMIN_USERS, DECISIONS G26).
 *
 * Every rule is the server's: tenant scope, no changes to your own access, the entitlement's
 * classification (taken from the source), and what a user can do. This page shows what the
 * server answers, and disables only the controls the server would refuse anyway.
 */
import { useCallback, useState, type FormEvent } from "react";
import type { Schemas } from "../api/client";
import { describeError, RequestId, useLoad, useMe, useSession } from "../shared";

type Role = Schemas["Role"];
type Right = Schemas["AdminEntitlementGrantRequest"]["rights"][number];
type Detail = Schemas["AdminUserDetail"];

const ROLES: { role: Role; label: string }[] = [
  { role: "ANALYST", label: "Analyst" },
  { role: "REVIEWER", label: "Reviewer" },
  { role: "ADMINISTRATOR", label: "Administrator" },
  { role: "DEMO_VIEWER", label: "Demo viewer" },
];
const RIGHTS: Right[] = ["READ", "DOWNLOAD", "IMPORT"];

function formatTime(value: string | null): string {
  return value === null ? "Never" : new Date(value).toLocaleString();
}

function Failure({ error }: { error: unknown }) {
  return (
    <div role="alert" className="notice">
      <p>{describeError(error)}</p>
      <RequestId error={error} />
    </div>
  );
}

function ProvisionForm({ onCreated }: { onCreated: (detail: Detail) => void }) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError(null);
    try {
      const detail = await api.createUser({
        issuer: String(data.get("issuer") ?? "").trim(),
        oidc_subject: String(data.get("subject") ?? "").trim(),
        roles: data.getAll("role").map((value) => String(value) as Role),
      });
      form.reset();
      onCreated(detail);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel" aria-labelledby="provision-title">
      <h2 id="provision-title">Provision an identity</h2>
      <p className="muted small">
        A user is the identity provider's issuer plus subject, never an email address. New users join
        your organisation. With no role they can sign in but see nothing.
      </p>
      <form aria-label="Provision" onSubmit={submit} className="admin-form">
        <label>
          Issuer
          <input name="issuer" required placeholder="https://idp.example" />
        </label>
        <label>
          Subject
          <input name="subject" required />
        </label>
        <fieldset>
          <legend>Roles</legend>
          {ROLES.map(({ role, label }) => (
            <label key={role} className="inline">
              <input type="checkbox" name="role" value={role} /> {label}
            </label>
          ))}
        </fieldset>
        <div className="actions">
          <button type="submit" className="primary" disabled={busy}>Provision</button>
        </div>
      </form>
      {error !== null && <Failure error={error} />}
    </section>
  );
}

function UserDetail({
  userId,
  onChanged,
}: {
  userId: string;
  onChanged: () => void;
}) {
  const { api } = useSession();
  const me = useMe();
  const self = userId === me.user_id;
  const load = useCallback((signal: AbortSignal) => api.getUser(userId, signal), [api, userId]);
  const { result, retry } = useLoad(load);
  const loadSources = useCallback((signal: AbortSignal) => api.listSources(signal), [api]);
  const { result: sources } = useLoad(loadSources);
  const [current, setCurrent] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [roles, setRoles] = useState<Role[] | null>(null);

  const detail = current?.user.user_id === userId ? current : result?.data ?? null;

  async function act(action: () => Promise<Detail>) {
    setBusy(true);
    setError(null);
    try {
      setCurrent(await action());
      setRoles(null);
      onChanged();
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  if (result === null && detail === null) {
    return <p className="muted" role="status">Loading user…</p>;
  }
  if (detail === null) {
    return (
      <>
        <Failure error={result?.error} />
        <button type="button" onClick={retry}>Try again</button>
      </>
    );
  }

  const { user } = detail;
  const chosen = roles ?? user.roles;
  const disabled = busy || self;

  async function grant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const expires = String(data.get("expires") ?? "");
    await act(() =>
      api.grantEntitlement(userId, {
        source_id: String(data.get("source") ?? ""),
        rights: data.getAll("right").map((value) => String(value) as Right),
        ...(expires ? { expires_at_utc: new Date(expires).toISOString() } : {}),
      }),
    );
    form.reset();
  }

  return (
    <section className="panel" aria-labelledby="user-title">
      <h2 id="user-title">
        <code>{user.oidc_subject}</code>
      </h2>
      <dl className="facts">
        <dt>Issuer</dt>
        <dd><code>{user.issuer}</code></dd>
        <dt>User ID</dt>
        <dd><code>{user.user_id}</code></dd>
        <dt>Status</dt>
        <dd>{user.active ? "Active" : "Deactivated"}</dd>
        <dt>Last verified sign-in</dt>
        <dd>{formatTime(user.last_verified_at_utc)}</dd>
        <dt>Sessions revoked before</dt>
        <dd>{formatTime(user.sessions_revoked_before_utc)}</dd>
      </dl>
      {self && (
        <p className="notice">
          This is your own account. Your access can only be changed by another administrator.
        </p>
      )}
      {error !== null && <Failure error={error} />}

      <h3>Roles</h3>
      <fieldset disabled={disabled}>
        <legend className="sr-only">Roles</legend>
        {ROLES.map(({ role, label }) => (
          <label key={role} className="inline">
            <input
              type="checkbox"
              checked={chosen.includes(role)}
              onChange={(event) =>
                setRoles(
                  event.target.checked ? [...chosen, role] : chosen.filter((item) => item !== role),
                )
              }
            />{" "}
            {label}
          </label>
        ))}
      </fieldset>
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={disabled || roles === null}
          onClick={() => act(() => api.setUserRoles(userId, chosen))}
        >
          Save roles
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => act(() => api.setUserStatus(userId, !user.active))}
        >
          {user.active ? "Deactivate" : "Activate"}
        </button>
        <button
          type="button"
          disabled={disabled}
          onClick={() => {
            if (window.confirm("Sign this user out everywhere? Their current sessions stop working.")) {
              void act(() => api.revokeUserSessions(userId));
            }
          }}
        >
          Revoke sessions
        </button>
      </div>

      <h3>Effective permissions</h3>
      <p className="muted small">What the server grants on this user's next request.</p>
      {detail.effective_capabilities.length === 0 ? (
        <p className="muted">None.{user.active ? "" : " The account is deactivated."}</p>
      ) : (
        <ul className="chips">
          {detail.effective_capabilities.map((capability) => (
            <li key={capability}><code>{capability}</code></li>
          ))}
        </ul>
      )}

      <h3>Source entitlements</h3>
      <p className="muted small">
        Restricted and confidential source records, and the cases built from them, need an entitlement
        to their source. The classification comes from the source.
      </p>
      {detail.entitlements.length === 0 ? (
        <p className="muted">No entitlements.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Source</th><th>Classification</th><th>Rights</th><th>Expires</th><th /></tr>
            </thead>
            <tbody>
              {detail.entitlements.map((grant) => (
                <tr key={grant.grant_id}>
                  <td><code>{grant.object_id}</code></td>
                  <td>{grant.classification}</td>
                  <td>{grant.rights.join(", ")}</td>
                  <td>{grant.expires_at_utc === null ? "No expiry" : formatTime(grant.expires_at_utc)}</td>
                  <td>
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() => act(() => api.revokeEntitlement(userId, grant.grant_id))}
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form aria-label="Grant entitlement" onSubmit={grant} className="admin-form">
        <fieldset disabled={disabled}>
          <legend>Grant an entitlement</legend>
          <label>
            Source
            <select name="source" required defaultValue="">
              <option value="" disabled>Choose a source</option>
              {sources?.data?.items.map((source) => (
                <option key={source.source_id} value={source.source_id}>
                  {source.source_id} ({source.usage_classification})
                </option>
              ))}
            </select>
          </label>
          {sources?.error !== undefined && <Failure error={sources.error} />}
          {RIGHTS.map((right) => (
            <label key={right} className="inline">
              <input type="checkbox" name="right" value={right} defaultChecked={right === "READ"} /> {right}
            </label>
          ))}
          <label>
            Expires (optional)
            <input type="datetime-local" name="expires" />
          </label>
          <div className="actions">
            <button type="submit" className="primary">Grant</button>
          </div>
        </fieldset>
      </form>
    </section>
  );
}

export function AdminUsersPage() {
  const { api } = useSession();
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [version, setVersion] = useState(0);
  const load = useCallback(
    // `version` reloads the list after a change.
    (signal: AbortSignal) => (void version, api.listUsers(cursor, signal)),
    [api, cursor, version],
  );
  const { result, retry } = useLoad(load);
  const [selected, setSelected] = useState<string | null>(null);
  const refresh = () => setVersion((value) => value + 1);

  return (
    <main className="content">
      <h1>Users and access</h1>
      <p className="muted">
        Users, roles and source entitlements in your organisation. Administering does not give you
        access to case or source content. Every change is audited.
      </p>
      <section className="panel" aria-labelledby="users-title">
        <h2 id="users-title">Users</h2>
        {result === null && <p className="muted" role="status">Loading users…</p>}
        {result?.error !== undefined && (
          <>
            <Failure error={result.error} />
            <button type="button" onClick={retry}>Try again</button>
          </>
        )}
        {result?.data?.items.length === 0 && <p className="muted">No users in this organisation.</p>}
        {result?.data !== undefined && result.data.items.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>Subject</th><th>Issuer</th><th>Roles</th><th>Status</th></tr>
              </thead>
              <tbody>
                {result.data.items.map((user) => (
                  <tr key={user.user_id} aria-selected={selected === user.user_id}>
                    <td>
                      <button type="button" className="link" onClick={() => setSelected(user.user_id)}>
                        {user.oidc_subject}
                      </button>
                    </td>
                    <td className="break"><code>{user.issuer}</code></td>
                    <td>{user.roles.length === 0 ? <span className="muted">No role</span> : user.roles.join(", ")}</td>
                    <td>{user.active ? "Active" : "Deactivated"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="actions">
          {cursor !== undefined && (
            <button type="button" onClick={() => setCursor(undefined)}>First page</button>
          )}
          {result?.data?.next_cursor && (
            <button type="button" onClick={() => setCursor(result.data?.next_cursor ?? undefined)}>
              Next page
            </button>
          )}
        </div>
      </section>
      {selected !== null && <UserDetail key={selected} userId={selected} onChanged={refresh} />}
      <ProvisionForm
        onCreated={(detail) => {
          refresh();
          setSelected(detail.user.user_id);
        }}
      />
    </main>
  );
}
