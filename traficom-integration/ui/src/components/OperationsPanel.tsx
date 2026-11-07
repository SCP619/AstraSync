/** Processing state from `GET /operations/metrics` (JOB_READ): server counts, never estimates. */
import { useCallback } from "react";
import type { Schemas } from "../api/client";
import { describeError, RequestId, useLoad, useSession } from "../shared";

function age(seconds: number | null): string {
  if (seconds === null) return "—";
  if (seconds < 60) return `${Math.round(seconds)} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

function bytes(value: number): string {
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${(value / 1024 ** 3).toFixed(2)} GiB`;
}

export function OperationsPanel() {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.getOperationsMetrics(signal), [api]);
  const { result, retry } = useLoad<Schemas["OperationsMetrics"]>(load);

  let content: React.ReactNode;
  if (result === null) {
    content = <p role="status">Loading processing state…</p>;
  } else if (result.data === undefined) {
    content = (
      <div role="alert">
        <p>{describeError(result.error)}</p>
        <RequestId error={result.error} />
        <button type="button" onClick={retry}>Try again</button>
      </div>
    );
  } else {
    const metrics = result.data;
    content = (
      <>
        {metrics.queues.length === 0 ? (
          <p>No jobs are waiting or running.</p>
        ) : (
          <table className="case-table">
            <thead>
              <tr>
                <th scope="col">Lane</th>
                <th scope="col">Status</th>
                <th scope="col">Jobs</th>
                <th scope="col">Oldest</th>
              </tr>
            </thead>
            <tbody>
              {metrics.queues.map((queue) => (
                <tr key={`${queue.lane}-${queue.status}`}>
                  <td data-label="Lane">{queue.lane}</td>
                  <td data-label="Status"><code>{queue.status}</code></td>
                  <td data-label="Jobs" className="numeric">{queue.count}</td>
                  <td data-label="Oldest" className="numeric">{age(queue.oldest_age_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <dl>
          <dt>Failed jobs, last 24 h</dt>
          <dd className="numeric">{metrics.failed_jobs_last_24h}</dd>
          <dt>Notifications waiting to be sent</dt>
          <dd className="numeric">{metrics.outbox_pending}</dd>
          <dt>Parsed-record store</dt>
          <dd>
            {metrics.record_store.enabled
              ? `${metrics.record_store.datasets} datasets, ${metrics.record_store.records} records, ${bytes(metrics.record_store.bytes)}`
              : "Not enabled on this server"}
          </dd>
        </dl>
      </>
    );
  }
  return (
    <section className="panel" aria-labelledby="operations-title">
      <h2 id="operations-title">Processing</h2>
      <p className="muted small">Counts for your organisation, from the server.</p>
      {content}
    </section>
  );
}
