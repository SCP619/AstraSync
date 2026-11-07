/**
 * Finland frequency relevance (TR-REL-004/005, workflow B). Calls
 * `GET /finland-relevance/frequency-screen` and shows the server's answer as given: Finnish M4
 * allocations and special-interest stations in separate lists, the stages that are not assessed
 * as not assessed, and overlap as a screening signal only. Layout from the Lovable design
 * (`contract-views.tsx`, `finland.tsx`); nothing here is computed in the browser.
 */
import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { Schemas } from "../api/client";
import { StatusBadge, SyntheticBadge } from "../components/StatusBadge";
import { describeError, RequestId, useSession } from "../shared";

type Screen = Schemas["FrequencyRelevanceScreen"];
type Match = Schemas["FrequencyReferenceMatch"];

const KIND_TEXT: Record<Match["reference_kind"], string> = {
  M4_ALLOCATION: "Finnish allocation table (M4)",
  SPECIAL_INTEREST_STATION: "Special-interest stations",
};

function Gate({ name, value }: { name: string; value: boolean | null }) {
  if (value === null) {
    return <StatusBadge tone="review" icon={CircleDashed} label={`${name}: not assessed`} />;
  }
  return value ? (
    <StatusBadge tone="info" icon={CheckCircle2} label={`${name}: match`} />
  ) : (
    <StatusBadge tone="neutral" icon={XCircle} label={`${name}: no match`} />
  );
}

function mhz(value: number): string {
  return `${value} MHz`;
}

function Matches({ kind, matches }: { kind: Match["reference_kind"]; matches: Match[] }) {
  return (
    <section className="panel" aria-labelledby={`matches-${kind}`}>
      <h2 id={`matches-${kind}`}>
        {KIND_TEXT[kind]} <span className="muted small">({matches.length})</span>
      </h2>
      {matches.length === 0 ? (
        <p className="muted">No overlapping entries.</p>
      ) : (
        <div className="table-scroll">
          <table className="case-table">
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">Reference range</th>
                <th scope="col">Overlap</th>
                <th scope="col">Basis</th>
                <th scope="col">Source record</th>
              </tr>
            </thead>
            <tbody>
              {matches.map((match) => (
                <tr key={`${match.source_record_id}-${match.reference_field}`}>
                  <td data-label="Reference">
                    {match.label ?? <span className="muted">No label</span>}{" "}
                    {match.is_synthetic && <SyntheticBadge />}
                  </td>
                  <td data-label="Reference range" className="numeric">
                    {mhz(match.reference_start_mhz)} – {mhz(match.reference_end_mhz)}
                  </td>
                  <td data-label="Overlap" className="numeric">
                    {mhz(match.overlap_start_mhz)} – {mhz(match.overlap_end_mhz)}
                  </td>
                  <td data-label="Basis">
                    <code>{match.reference_field}</code> <span className="muted small">{match.interval_basis}</span>
                  </td>
                  <td data-label="Source record">
                    <Link to={`/sources?record=${encodeURIComponent(match.source_record_id)}`}>
                      {match.source_record_id}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function FinlandRelevancePage() {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [screen, setScreen] = useState<Screen | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [invalid, setInvalid] = useState<string | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const start = Number(data.get("start"));
    const end = Number(data.get("end"));
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start) {
      setInvalid("Enter a start and end frequency in MHz, with the end at or above the start.");
      return;
    }
    setInvalid(null);
    setBusy(true);
    setError(null);
    try {
      setScreen(await api.screenFrequency(start, end));
    } catch (caught) {
      setScreen(null);
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  const byKind = (kind: Match["reference_kind"]) =>
    screen?.matches.filter((match) => match.reference_kind === kind) ?? [];

  return (
    <main className="content">
      <h1>Finland frequency relevance</h1>
      <p className="muted">
        Screens a frequency range against the Finnish references you can access. An overlap is a
        screening signal for expert review, not evidence of interference.
      </p>
      <form className="panel filters" onSubmit={(event) => void submit(event)} aria-label="Frequency range">
        <label>
          Start (MHz)
          <input name="start" type="number" step="any" min="0" max="3000000" required />
        </label>
        <label>
          End (MHz)
          <input name="end" type="number" step="any" min="0" max="3000000" required />
        </label>
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Screening…" : "Screen range"}
        </button>
      </form>
      {invalid !== null && <p role="alert">{invalid}</p>}
      {error !== null && (
        <section className="panel" role="alert">
          <p>{describeError(error)}</p>
          <RequestId error={error} />
        </section>
      )}
      {screen !== null && (
        <>
          <section className="panel" aria-labelledby="gates-title">
            <h2 id="gates-title">
              Result for {mhz(screen.query_start_mhz)} – {mhz(screen.query_end_mhz)}{" "}
              {screen.is_synthetic && <SyntheticBadge />}
            </h2>
            <p>
              <code>{screen.gates.label}</code>
              {screen.gates.rule_version && (
                <span className="muted small"> rule {screen.gates.rule_version}</span>
              )}
            </p>
            <div className="flex flex-wrap gap-2">
              <Gate name="Frequency" value={screen.gates.frequency_match} />
              <Gate name="Service" value={screen.gates.service_match} />
              <Gate name="Geometry" value={screen.gates.geometry_match} />
              <Gate name="Technical data" value={screen.gates.technical_data_ready} />
            </div>
            {screen.gates.reason_codes.length > 0 && (
              <p className="muted small">
                Reasons: {screen.gates.reason_codes.map((code) => <code key={code}>{code} </code>)}
              </p>
            )}
            <p className="muted small">
              Sources screened:{" "}
              {screen.sources_screened.length === 0
                ? "none you can access"
                : screen.sources_screened
                    .map((source) => `${source.source_id} (${source.source_type}, revision ${source.revision})`)
                    .join("; ")}
            </p>
            {screen.matches_truncated && (
              <p role="status">Only the first matches are shown. Narrow the range to see all.</p>
            )}
          </section>
          <Matches kind="M4_ALLOCATION" matches={byKind("M4_ALLOCATION")} />
          <Matches kind="SPECIAL_INTEREST_STATION" matches={byKind("SPECIAL_INTEREST_STATION")} />
        </>
      )}
    </main>
  );
}
