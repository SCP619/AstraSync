import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Schemas } from "../api/client";
import type { PushPermission } from "../platform/types";
import { describeError, RequestId, useLoad, useMe, useSession } from "../shared";

type Severity = Schemas["AlertSeverity"];

// Text and a symbol, never colour alone. Severity is a priority, not a finding (ALERT_ENGINE 6).
const SEVERITY_TEXT: Record<Severity, string> = {
  INFO: "ⓘ Information",
  REVIEW: "◆ Review",
  HIGH: "▲ High priority",
  CRITICAL: "⬤ Critical priority",
  OPERATIONS: "⚙ Operations",
  SECURITY: "⛨ Security",
};

const STATUS_TEXT: Record<Schemas["AlertStatus"], string> = {
  OPEN: "Needs acknowledgment",
  ACKNOWLEDGED: "Acknowledged",
  RESOLVED: "Resolved",
  SUPPRESSED: "Suppressed",
};

const CHANNEL_TEXT: Record<Schemas["AlertChannel"], string> = {
  IN_APP: "In the app",
  WINDOWS: "Windows notification",
  ANDROID: "Android notification",
  EMAIL: "Email",
};

// "Sent" means handed to the provider. Only the device can say more than that.
const DELIVERY_TEXT: Record<Schemas["AlertDeliveryState"], string> = {
  PENDING: "Waiting to send",
  SENT: "Sent, not confirmed delivered",
  DELIVERED: "Delivered",
  READ: "Read",
  FAILED: "Could not send",
};

const PUSH_TEXT: Record<PushPermission, string | null> = {
  GRANTED: null,
  DENIED:
    "Notifications are turned off for this app, so alerts appear only here. You can turn them on in your device settings.",
  NOT_CONFIGURED: "Push notifications are not set up for this deployment, so alerts appear only here.",
  UNSUPPORTED: null,
};

function when(value: string): string {
  return `${value.slice(0, 16).replace("T", " ")} UTC`;
}

function Preferences() {
  const { api } = useSession();
  const [version, setVersion] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => api.getAlertPreferences(signal),
    // `version` reloads after a save.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, version],
  );
  const { result } = useLoad(load);
  const [error, setError] = useState<unknown>(null);

  if (result?.data === undefined) {
    return null;
  }
  const preferences = result.data;
  const android = preferences.enabled_channels.includes("ANDROID");
  const windows = preferences.enabled_channels.includes("WINDOWS");

  async function save(form: HTMLFormElement) {
    const data = new FormData(form);
    const channels: Schemas["AlertChannel"][] = ["IN_APP"];
    if (data.get("windows")) channels.push("WINDOWS");
    if (data.get("android")) channels.push("ANDROID");
    setError(null);
    try {
      await api.updateAlertPreferences({
        enabled_channels: channels,
        quiet_hours_start_utc: String(data.get("start") ?? "") || null,
        quiet_hours_end_utc: String(data.get("end") ?? "") || null,
      });
      setVersion((value) => value + 1);
    } catch (failure) {
      setError(failure);
    }
  }

  return (
    <details className="panel">
      <summary>Notification settings</summary>
      <form
        key={version}
        className="stack"
        onSubmit={(event) => {
          event.preventDefault();
          void save(event.currentTarget);
        }}
      >
        <p className="muted small">
          The inbox here always stays on. Critical and security alerts ignore these settings.
        </p>
        <label className="check"><input type="checkbox" name="windows" defaultChecked={windows} /> Windows notifications</label>
        <label className="check"><input type="checkbox" name="android" defaultChecked={android} /> Android notifications</label>
        <label className="stacked">Quiet hours start (UTC)
          <input type="time" name="start" defaultValue={preferences.quiet_hours_start_utc ?? ""} />
        </label>
        <label className="stacked">Quiet hours end (UTC)
          <input type="time" name="end" defaultValue={preferences.quiet_hours_end_utc ?? ""} />
        </label>
        <button type="submit">Save settings</button>
        {error !== null && <p role="alert">{describeError(error)}</p>}
      </form>
    </details>
  );
}

export function AlertsPage({
  pushPermission,
  refreshKey,
}: {
  pushPermission: PushPermission | null;
  refreshKey: number;
}) {
  const { api } = useSession();
  const { capabilities } = useMe();
  const [view, setView] = useState<"OPEN" | "ALL">("OPEN");
  const [extra, setExtra] = useState<Schemas["AlertList"] | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => api.listAlerts(view === "OPEN" ? "OPEN" : undefined, undefined, signal),
    // `refreshKey` reloads when the stream reports a new alert.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, view, refreshKey],
  );
  const { result, retry } = useLoad(load);
  const [moreError, setMoreError] = useState<unknown>(null);
  useEffect(() => setExtra(null), [view, refreshKey]);

  const notice = pushPermission === null ? null : PUSH_TEXT[pushPermission];
  const page = extra ?? result?.data;

  async function more() {
    if (!page?.next_cursor) {
      return;
    }
    setMoreError(null);
    try {
      const next = await api.listAlerts(view === "OPEN" ? "OPEN" : undefined, page.next_cursor);
      setExtra({ ...next, items: [...page.items, ...next.items] });
    } catch (failure) {
      setMoreError(failure);
    }
  }

  return (
    <main className="content">
      <h1>Alerts</h1>
      {notice !== null && <p className="notice">{notice}</p>}
      <div role="tablist" aria-label="Alert views" className="tabs">
        <button type="button" role="tab" aria-selected={view === "OPEN"} onClick={() => setView("OPEN")}>
          Needs acknowledgment
        </button>
        <button type="button" role="tab" aria-selected={view === "ALL"} onClick={() => setView("ALL")}>
          All alerts
        </button>
      </div>
      {result === null && extra === null && <p role="status">Loading alerts…</p>}
      {result?.error !== undefined && (
        <>
          <p role="alert">{describeError(result.error)}</p>
          <RequestId error={result.error} />
          <button type="button" onClick={retry}>Try again</button>
        </>
      )}
      {page?.items.length === 0 && (
        <p>{view === "OPEN" ? "Nothing needs acknowledgment." : "No alerts yet."}</p>
      )}
      {page !== undefined && page.items.length > 0 && (
        <ul className="plain panel">
          {page.items.map((alert) => (
            <li key={alert.alert_id}>
              <span className="muted small block">{SEVERITY_TEXT[alert.severity]}</span>
              <Link to={`/alerts/${encodeURIComponent(alert.alert_id)}`}>{alert.safe_title}</Link>{" "}
              {alert.is_synthetic && <span className="badge review">SYNTHETIC</span>}
              <span className="muted small block">
                {STATUS_TEXT[alert.status]} · {when(alert.created_at_utc)}
              </span>
            </li>
          ))}
        </ul>
      )}
      {page?.next_cursor && <button type="button" onClick={() => void more()}>Load more</button>}
      {moreError !== null && <p role="alert">{describeError(moreError)}</p>}
      {capabilities.includes("ALERT_PREFERENCES") && <Preferences />}
    </main>
  );
}

export function AlertDetailPage({ onChanged }: { onChanged: () => void }) {
  const { alertId = "" } = useParams();
  const { api } = useSession();
  const { capabilities } = useMe();
  const [version, setVersion] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => api.getAlert(alertId, signal),
    // `version` reloads after acknowledging.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, alertId, version],
  );
  const { result, retry } = useLoad(load);
  const [error, setError] = useState<unknown>(null);

  if (result === null) {
    return <main className="content"><p role="status">Loading alert…</p></main>;
  }
  if (result.data === undefined) {
    return (
      <main className="content">
        <p><Link to="/alerts">All alerts</Link></p>
        <h1>Alert unavailable</h1>
        <p role="alert">{describeError(result.error)}</p>
        <RequestId error={result.error} />
        <button type="button" onClick={retry}>Try again</button>
      </main>
    );
  }

  const alert = result.data;
  const canAcknowledge =
    capabilities.includes("ALERT_ACKNOWLEDGE") && alert.status === "OPEN";

  async function acknowledge() {
    setError(null);
    try {
      await api.acknowledgeAlert(alertId);
      setVersion((value) => value + 1);
      onChanged();
    } catch (failure) {
      setError(failure);
    }
  }

  return (
    <main className="content">
      <p><Link to="/alerts">All alerts</Link></p>
      <h1>{alert.safe_title}</h1>
      <p className="muted small">
        An alert is a prompt to look, not a finding. Severity is an operational priority.
      </p>
      <section className="panel">
        <dl>
          <dt>Priority</dt>
          <dd>{SEVERITY_TEXT[alert.severity]}</dd>
          <dt>Status</dt>
          <dd>{STATUS_TEXT[alert.status]}</dd>
          <dt>Created</dt>
          <dd>{when(alert.created_at_utc)}</dd>
        </dl>
        <div className="actions">
          {alert.case_id !== null && (
            <Link className="button" to={`/cases/${encodeURIComponent(alert.case_id)}`}>Open case and evidence</Link>
          )}
          {canAcknowledge && <button type="button" onClick={() => void acknowledge()}>Acknowledge</button>}
        </div>
        {error !== null && <p role="alert">{describeError(error)}</p>}
      </section>
      {alert.acknowledgments.length > 0 && (
        <section className="panel" aria-labelledby="ack-title">
          <h2 id="ack-title">Acknowledged by</h2>
          <ul className="plain">
            {alert.acknowledgments.map((ack) => (
              <li key={ack.ack_id}>
                <code>{ack.actor_id}</code>
                <span className="muted small"> · {when(ack.acknowledged_at_utc)}</span>
                {ack.comment !== null && <span className="block">{ack.comment}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section className="panel" aria-labelledby="delivery-title">
        <h2 id="delivery-title">How this reached you</h2>
        <ul className="plain">
          {alert.deliveries.map((delivery) => (
            <li key={delivery.delivery_id}>
              {CHANNEL_TEXT[delivery.channel]}: {DELIVERY_TEXT[delivery.state]}
              {delivery.failure_code !== null && <code className="block small">{delivery.failure_code}</code>}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
