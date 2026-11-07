import { useCallback, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ApiError,
  type RecordSearch,
  type Schemas,
  type SourceRecordList,
} from "../api/client";
import { describeError, RequestId, useLoad, useMe, useSession } from "../shared";
import { SeverityBadge, SyntheticBadge as SyntheticLabel } from "../components/StatusBadge";

type Hit = Schemas["SourceRecordHit"];
type Report = Schemas["ArtifactIntegrityReport"];
type RecordDetail = Schemas["SourceRecordDetail"];

// One label each. Byte integrity, publisher trust and parse status are never merged into one
// green tick (DBD section 11).
const TRUST_TEXT: Record<Schemas["PublisherAuthStatus"], string> = {
  VERIFIED_PUBLISHER: "Verified publisher",
  HASH_MATCH_MANIFEST_UNTRUSTED: "Hash matches supplied manifest (publisher unverified)",
  NO_PUBLISHER_DIGEST: "No publisher digest (publisher unverified)",
  MISMATCH: "Digest mismatch",
};

const HEALTH_TEXT: Record<Schemas["SourceHealthStatus"], string> = {
  HEALTHY: "Checked recently",
  SOURCE_STALE: "Source stale",
  SOURCE_UNAVAILABLE: "Source unavailable",
  ACCESS_DENIED: "Access denied by source",
  MANUAL_REQUIRED: "Manual import: no automatic check",
  DISABLED: "Disabled",
};

const RECORD_TEXT: Record<Schemas["RecordStatus"], string> = {
  VALID: "Valid",
  VALID_WITH_WARNINGS: "Valid, with warnings",
  INVALID: "Invalid",
  INSUFFICIENT_DATA: "Insufficient data",
  REVIEW_REQUIRED: "Review required",
};

const ARTIFACT_TEXT: Partial<Record<Schemas["ArtifactStatus"], string>> = {
  INDEXED: "Indexed",
  INDEXED_WITH_WARNINGS: "Indexed with warnings",
  QUARANTINED: "Quarantined",
  VERIFIED_BYTES: "Bytes verified, not indexed",
  FAILED: "Failed",
};

const MAX_BROWSER_DOWNLOAD_BYTES = 200 * 1024 * 1024;

function SyntheticBadge({ show }: { show: boolean }) {
  return show ? <SyntheticLabel /> : null;
}

function formatTime(value: string | null): string {
  return value === null ? "Never" : new Date(value).toISOString().replace("T", " ").slice(0, 16) + " UTC";
}

function formatBytes(bytes: number): string {
  const units = ["bytes", "KiB", "MiB", "GiB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? value : value.toFixed(1)} ${units[unit]}`;
}

function formatFrequency(hit: Hit): string {
  const { frequency_start_mhz: start, frequency_end_mhz: end } = hit;
  if (start === null || end === null) {
    return "Unresolved";
  }
  return start === end ? `${start} MHz` : `${start}–${end} MHz`;
}

function SourcesPanel() {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.listSources(signal), [api]);
  const { result, retry } = useLoad(load);

  return (
    <section className="panel" aria-labelledby="sources-title">
      <h2 id="sources-title">Sources</h2>
      {result === null && <p role="status">Loading sources…</p>}
      {result?.error !== undefined && (
        <>
          <p role="alert">{describeError(result.error)}</p>
          <button type="button" onClick={retry}>Try again</button>
        </>
      )}
      {result?.data?.items.length === 0 && <p className="muted">No sources are registered yet.</p>}
      {result?.data !== undefined && result.data.items.length > 0 && (
        <ul className="source-list">
          {result.data.items.map((source) => (
            <li key={source.source_id}>
              <strong>{source.publisher}</strong> <code>{source.source_id}</code>{" "}
              <SyntheticBadge show={source.is_synthetic} />
              <br />
              <span>{HEALTH_TEXT[source.status]}</span>
              <span className="muted small"> · Last success: {formatTime(source.last_success_at_utc)}</span>
              <br />
              <span className="muted small">Access basis: {source.rights_basis}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function IntegrityPanel({ artifactId }: { artifactId: string }) {
  const { api } = useSession();
  const load = useCallback(
    (signal: AbortSignal) => Promise.all([api.getArtifact(artifactId, signal), api.getIntegrity(artifactId, signal)]),
    [api, artifactId],
  );
  const { result } = useLoad(load);
  const [download, setDownload] = useState<"IDLE" | "CONFIRM" | "BUSY" | string>("IDLE");

  if (result === null) {
    return <p role="status">Loading file details…</p>;
  }
  if (result.data === undefined) {
    return <p role="alert">{describeError(result.error)}</p>;
  }
  const [artifact, report]: [Schemas["SourceArtifactDetail"], Report] = result.data;

  async function save() {
    setDownload("BUSY");
    try {
      const blob = await api.downloadArtifact(artifactId);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = artifact.filename_original.split(/[\\/]/).pop() ?? "source-file";
      link.click();
      URL.revokeObjectURL(url);
      setDownload("IDLE");
    } catch (error) {
      setDownload(describeError(error));
    }
  }

  return (
    <>
      <dl>
        <dt>File</dt>
        <dd>{artifact.filename_original} (revision {artifact.revision})</dd>
        <dt>File status</dt>
        <dd>{ARTIFACT_TEXT[artifact.status] ?? artifact.status}</dd>
        <dt>Publisher trust</dt>
        <dd>{TRUST_TEXT[artifact.publisher_auth_status]}</dd>
        <dt>Size</dt>
        <dd>{formatBytes(artifact.byte_length)}</dd>
        <dt>SHA-256</dt>
        <dd><code>{artifact.raw_sha256}</code></dd>
        <dt>Published</dt>
        <dd>{artifact.published_at_utc === null ? "Not reported" : formatTime(artifact.published_at_utc)}</dd>
        <dt>Indexed</dt>
        <dd>{formatTime(artifact.indexed_at_utc)}</dd>
        {report.row_reconciliation !== null && (
          <>
            <dt>Rows</dt>
            <dd>
              {report.row_reconciliation.parsed} parsed: {report.row_reconciliation.accepted} accepted,{" "}
              {report.row_reconciliation.flagged} flagged, {report.row_reconciliation.rejected} rejected
            </dd>
          </>
        )}
      </dl>
      <h3>Checks</h3>
      <ul className="plain">
        {report.checks.map((check) => (
          <li key={check.check_id}>
            <code>{check.check_type}</code>: {check.result}
            {check.diagnostic !== null && <span className="muted small"> · {check.diagnostic}</span>}
          </li>
        ))}
      </ul>
      <h3>Original file</h3>
      {download === "IDLE" && (
        <button type="button" onClick={() => setDownload("CONFIRM")}>Download full original</button>
      )}
      {download === "CONFIRM" && (
        artifact.byte_length > MAX_BROWSER_DOWNLOAD_BYTES ? (
          <p role="status">
            This file is {formatBytes(artifact.byte_length)}, too large to download in this web
            preview. You do not need it to read this record.
          </p>
        ) : (
          <div className="notice">
            <p>
              This transfers the whole file ({formatBytes(artifact.byte_length)}). You do not need
              it to read this record.
            </p>
            <div className="actions">
              <button type="button" onClick={() => void save()}>Download</button>
              <button type="button" onClick={() => setDownload("IDLE")}>Cancel</button>
            </div>
          </div>
        )
      )}
      {download === "BUSY" && <p role="status">Downloading…</p>}
      {!["IDLE", "CONFIRM", "BUSY"].includes(download) && <p role="alert">{download}</p>}
    </>
  );
}

function RecordInspector({ recordId, onClose }: { recordId: string; onClose: () => void }) {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.getRecord(recordId, signal), [api, recordId]);
  const { result } = useLoad(load);

  let content: React.ReactNode;
  if (result === null) {
    content = <p role="status">Loading record…</p>;
  } else if (result.data === undefined) {
    content = <p role="alert">{describeError(result.error)}</p>;
  } else {
    const record: RecordDetail = result.data;
    const location = record.location;
    const parsed = Object.entries(record.reference_station ?? {}).filter(
      ([name, value]) => value !== null && !["source_record_id", "is_synthetic", "parse_status"].includes(name),
    );
    content = (
      <>
        <p>
          {RECORD_TEXT[record.record_status]} <SyntheticBadge show={record.is_synthetic} />
        </p>
        <h3>Original location</h3>
        <dl>
          <dt>Table or sheet</dt>
          <dd>{location.source_table_or_sheet ?? "Not applicable"}</dd>
          <dt>Row or key</dt>
          <dd>{location.source_row_or_key ?? "Not applicable"}</dd>
          <dt>Parser</dt>
          <dd><code>{location.parser_version ?? "Unknown"}</code></dd>
        </dl>
        <h3>Original values</h3>
        <div className="table-scroll">
          <table>
            <thead><tr><th scope="col">Field</th><th scope="col">As received</th></tr></thead>
            <tbody>
              {Object.entries(record.raw_fields).map(([name, value]) => (
                <tr key={name}>
                  <th scope="row">
                    <code>{name}</code>
                    {record.field_aliases[name] !== undefined && (
                      <span className="muted small block">{record.field_aliases[name]?.join(", ")}</span>
                    )}
                  </th>
                  <td>{value ?? <span className="muted">Empty</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>Parsed values</h3>
        {parsed.length === 0 ? (
          <p className="muted">No values could be parsed from this record.</p>
        ) : (
          <dl>
            {parsed.map(([name, value]) => (
              <div key={name} className="contents">
                <dt><code>{name}</code></dt>
                <dd>{String(value)}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="muted small">Fields not listed are unknown. Unknown is never treated as zero.</p>
        <h3>Data quality</h3>
        {record.quality_findings.length === 0 ? (
          <p className="muted">No findings.</p>
        ) : (
          <ul className="plain">
            {record.quality_findings.map((finding) => (
              <li key={finding.finding_id}>
                <SeverityBadge severity={finding.severity} />{" "}
                <code>{finding.rule_id}</code> on <code>{finding.field_key}</code>: received{" "}
                <code>{finding.raw_value ?? "empty"}</code>. Calculations that need this field
                cannot proceed without review.
              </li>
            ))}
          </ul>
        )}
        <h3>File and integrity</h3>
        <IntegrityPanel artifactId={location.artifact_id} />
      </>
    );
  }

  return (
    <section className="panel" aria-labelledby="record-title">
      <div className="panel-header">
        <h2 id="record-title">Indexed record</h2>
        <button type="button" onClick={onClose}>Close</button>
      </div>
      {content}
    </section>
  );
}

function readSearch(form: HTMLFormElement): RecordSearch {
  const data = new FormData(form);
  const text = (name: string) => String(data.get(name) ?? "").trim();
  const search: RecordSearch = {};
  if (text("query")) search.query = text("query");
  if (text("station")) search.station_number = text("station");
  if (text("from")) search.frequency_start_mhz = Number(text("from"));
  if (text("to")) search.frequency_end_mhz = Number(text("to"));
  return search;
}

export function SourceLibraryPage() {
  const { api } = useSession();
  const canSearch = useMe().capabilities.includes("SOURCE_READ");
  const [results, setResults] = useState<SourceRecordList | null>(null);
  const [search, setSearch] = useState<RecordSearch>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // A linked record (from relevance screening or evidence) opens straight in the inspector; the
  // server still checks access to it.
  const [params] = useSearchParams();
  const [selected, setSelected] = useState<string | null>(params.get("record"));

  async function run(next: RecordSearch, cursor?: string) {
    setBusy(true);
    setError(null);
    try {
      const page = await api.searchRecords(next, cursor);
      setResults((current) =>
        cursor !== undefined && current !== null
          ? { ...page, items: [...current.items, ...page.items] }
          : page,
      );
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 401)) {
        setError(failure);
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = readSearch(event.currentTarget);
    setSearch(next);
    setSelected(null);
    void run(next);
  }

  return (
    <main className="content">
      <h1>Source library</h1>
      <SourcesPanel />
      {!canSearch && (
        <p className="muted">Your role shows source status only. File contents need a separate role.</p>
      )}
      {canSearch && (
      <section className="panel" aria-labelledby="search-title">
        <h2 id="search-title">Find a record</h2>
        <form className="search-form" onSubmit={submit}>
          <label>Search<input name="query" type="search" maxLength={256} placeholder="File, station, issue" /></label>
          <label>Station number<input name="station" maxLength={64} /></label>
          <label>From (MHz)<input name="from" type="number" min="0" step="any" /></label>
          <label>To (MHz)<input name="to" type="number" min="0" step="any" /></label>
          <button type="submit" className="primary" disabled={busy}>Search</button>
        </form>
        <p className="muted small">
          Searches the server index. Only files you are entitled to appear, and no original file is
          transferred.
        </p>
        {busy && <p role="status">Searching…</p>}
        {error !== null && (
          <>
            <p role="alert">{describeError(error)}</p>
            <RequestId error={error} />
          </>
        )}
        {results !== null && results.items.length === 0 && !busy && (
          <p>No records match, or none are indexed yet for sources you can access.</p>
        )}
        {results !== null && results.items.length > 0 && (
          <>
            <div className="table-scroll">
              <table>
                <caption className="muted small">{results.items.length} loaded</caption>
                <thead>
                  <tr>
                    <th scope="col">Station</th>
                    <th scope="col">Frequency</th>
                    <th scope="col">File</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {results.items.map((hit) => (
                    <tr key={hit.source_record_id} aria-selected={selected === hit.source_record_id}>
                      <td>
                        <button type="button" className="link" onClick={() => setSelected(hit.source_record_id)}>
                          {hit.station_number ?? hit.source_record_id}
                        </button>{" "}
                        <SyntheticBadge show={hit.is_synthetic} />
                      </td>
                      <td>{formatFrequency(hit)}</td>
                      <td className="break">{hit.filename_original}</td>
                      <td>{RECORD_TEXT[hit.record_status]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {results.next_cursor !== null && (
              <button
                type="button"
                disabled={busy}
                onClick={() => void run(search, results.next_cursor ?? undefined)}
              >
                Load more
              </button>
            )}
          </>
        )}
      </section>
      )}
      {selected !== null && <RecordInspector recordId={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}
