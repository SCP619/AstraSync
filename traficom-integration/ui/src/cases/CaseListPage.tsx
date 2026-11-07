import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, type CaseFilters, type CaseList, type Schemas } from "../api/client";
import { describeError, RequestId, useSession } from "../shared";
import {
  CHANGE_TEXT,
  FINDING_TEXT,
  formatFrequencyRange,
  formatMargin,
  METRIC_TEXT,
  REVIEW_TEXT,
} from "./labels";
import { ChangeBadge, FindingBadge, ReviewBadge, SyntheticBadge } from "../components/StatusBadge";

function Options<T extends string>({ labels }: { labels: Record<T, string> }) {
  return (
    <>
      <option value="">All</option>
      {(Object.entries(labels) as [T, string][]).map(([value, text]) => (
        <option key={value} value={value}>{text}</option>
      ))}
    </>
  );
}

function lead(item: Schemas["CaseSummary"]): string {
  const { metric_kind: kind, numeric_value: value, unit } = item.lead_metric;
  if (value === null || kind === null) {
    return "Not computed";
  }
  return `${METRIC_TEXT[kind]}: ${value} ${unit ?? ""}`.trim();
}

function readFilters(form: HTMLFormElement): CaseFilters {
  const data = new FormData(form);
  const filters: CaseFilters = {};
  for (const name of ["query", "domain", "change_type", "finding_status", "review_status", "sort"] as const) {
    const value = String(data.get(name) ?? "").trim();
    if (value) {
      (filters as Record<string, string>)[name] = value;
    }
  }
  return filters;
}

export function CaseListPage() {
  const { api } = useSession();
  const [filters, setFilters] = useState<CaseFilters>({});
  const [page, setPage] = useState<CaseList | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(
    async (next: CaseFilters, cursor?: string, signal?: AbortSignal) => {
      setBusy(true);
      setError(null);
      try {
        const result = await api.listCases(next, cursor, signal);
        setPage((current) =>
          cursor !== undefined && current !== null
            ? { ...result, items: [...current.items, ...result.items] }
            : result,
        );
        setBusy(false);
      } catch (failure) {
        if (failure instanceof DOMException && failure.name === "AbortError") {
          return;
        }
        if (!(failure instanceof ApiError && failure.status === 401)) {
          setError(failure);
        }
        setBusy(false);
      }
    },
    [api],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load({}, undefined, controller.signal);
    return () => controller.abort();
  }, [load]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = readFilters(event.currentTarget);
    setFilters(next);
    void load(next);
  }

  return (
    <main className="content wide">
      <h1>Cases</h1>
      {/* Collapsed on a phone, so that the cases themselves come first. */}
      <details className="panel" open={window.matchMedia?.("(min-width: 761px)").matches ?? true}>
        <summary>Search and filters</summary>
        <form className="search-form" onSubmit={submit}>
          <label>Search<input name="query" type="search" maxLength={256} placeholder="Case, notice, issue" /></label>
          <label>Domain
            <select name="domain"><Options labels={{ SPACE: "Space", TERRESTRIAL: "Terrestrial" }} /></select>
          </label>
          <label>Change<select name="change_type"><Options labels={CHANGE_TEXT} /></select></label>
          <label>Finding<select name="finding_status"><Options labels={FINDING_TEXT} /></select></label>
          <label>Review<select name="review_status"><Options labels={REVIEW_TEXT} /></select></label>
          <label>Sort by
            <select name="sort">
              <option value="case_id">Case ID</option>
              <option value="frequency_start_mhz">Start frequency</option>
              <option value="updated_at_utc">Last updated</option>
            </select>
          </label>
          <button type="submit" className="primary" disabled={busy}>Apply</button>
        </form>
      </details>
      {busy && <p role="status">Loading cases…</p>}
      {error !== null && (
        <>
          <p role="alert">{describeError(error)}</p>
          <RequestId error={error} />
        </>
      )}
      {page !== null && page.items.length === 0 && !busy && (
        <p>No cases match, or none exist yet for sources you can access.</p>
      )}
      {page !== null && page.items.length > 0 && (
        <>
          <p className="muted small">{page.items.length} loaded</p>
          <div className="table-scroll">
            <table className="case-table">
              <thead>
                <tr>
                  <th scope="col">Notice / case</th>
                  <th scope="col">Domain and issue</th>
                  <th scope="col">Change</th>
                  <th scope="col">Frequency</th>
                  <th scope="col">Relevance</th>
                  <th scope="col">Methods run</th>
                  <th scope="col">Lead result</th>
                  <th scope="col">Criterion margin</th>
                  <th scope="col">Finding</th>
                  <th scope="col">Review</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((item) => (
                  <tr key={item.case_id}>
                    <td data-label="Notice / case">
                      <Link to={`/cases/${encodeURIComponent(item.case_id)}`}>{item.notice_id}</Link>{" "}
                      {item.is_synthetic && <SyntheticBadge />}
                      <span className="muted small block break">{item.case_id}</span>
                    </td>
                    <td data-label="Domain and issue">
                      {item.domain === "SPACE" ? "Space" : "Terrestrial"}
                      <span className="muted small block break">{item.source_issue_id}</span>
                    </td>
                    <td data-label="Change"><ChangeBadge change={item.change_type} /></td>
                    <td data-label="Frequency" className="numeric">
                      {formatFrequencyRange(item.frequency_start_mhz, item.frequency_end_mhz)}
                    </td>
                    <td data-label="Relevance"><code>{item.relevance_label}</code></td>
                    <td data-label="Methods run" className="numeric">
                      {item.method_summary.succeeded} of {item.method_summary.candidates}
                    </td>
                    <td data-label="Lead result">{lead(item)}</td>
                    <td data-label="Criterion margin" className="numeric">
                      {formatMargin(item.margin_db, item.criterion_status)}
                    </td>
                    <td data-label="Finding"><FindingBadge status={item.finding_status} /></td>
                    <td data-label="Review"><ReviewBadge status={item.review_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {page.next_cursor !== null && (
            <button type="button" disabled={busy} onClick={() => void load(filters, page.next_cursor ?? undefined)}>
              Load more
            </button>
          )}
        </>
      )}
    </main>
  );
}
