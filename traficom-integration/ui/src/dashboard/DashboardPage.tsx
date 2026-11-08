/**
 * Dashboard as a datasheet: KPIs, insights and small charts from the live API. No identifiers,
 * keys or hashes are shown; every number is a screening result for expert review.
 */
import { useCallback } from "react";
import { Link } from "react-router-dom";
import type { Schemas } from "../api/client";
import { formatFrequencyRange } from "../cases/labels";
import { OperationsPanel } from "../components/OperationsPanel";
import { describeError, useLoad, useMe, useSession } from "../shared";

type Analysis = Schemas["IficAnalysis"];
type CaseItem = Schemas["CaseSummary"];

const EXCEEDANCE = ["VERIFIED_CRITERION_EXCEEDANCE", "COORDINATION_REVIEW", "WORST_CASE_EXCEEDANCE"];
const CONCERN_TEXT: Record<string, string> = {
  VERIFIED_CRITERION_EXCEEDANCE: "Above coordination threshold",
  COORDINATION_REVIEW: "Above threshold, coordination noted",
  WORST_CASE_EXCEEDANCE: "Worst-case PFD above limit",
  POTENTIAL_CONCERN: "Near threshold",
  INCONCLUSIVE_UNKNOWN_PARAMETER: "Inconclusive (unknown parameter)",
  BELOW_SCREENING_THRESHOLD: "Below threshold",
  FREQUENCY_OVERLAP_ONLY: "Frequency overlap only",
  INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  NO_APPLICABLE_CRITERION: "No applicable criterion",
};

function counts(analysis: Analysis, key: string): Record<string, number> {
  const value = (analysis.summary as Record<string, unknown>)[key];
  return value && typeof value === "object" ? (value as Record<string, number>) : {};
}

function sum(values: Record<string, number>, keys?: string[]): number {
  return Object.entries(values)
    .filter(([k]) => keys === undefined || keys.includes(k))
    .reduce((total, [, v]) => total + v, 0);
}

function kindLabel(kind: string): string {
  return kind.includes("SPACE") ? "Space" : "Terrestrial";
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * 100},${30 - (v / max) * 28}`)
    .join(" ");
  return (
    <svg className="sparkline" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

function Kpi({ label, value, unit, note, trend }: { label: string; value: number | string; unit?: string; note?: string; trend?: number[] }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value numeric">
        {value}
        {unit && <span className="kpi-unit"> {unit}</span>}
      </div>
      {note && <div className="kpi-delta small muted">{note}</div>}
      {trend && <Sparkline values={trend} />}
    </div>
  );
}

function Bars({ title, description, rows }: { title: string; description: string; rows: [string, number][] }) {
  const max = Math.max(...rows.map(([, v]) => v), 1);
  return (
    <section className="insight">
      <h2 className="insight-title">{title}</h2>
      <p className="insight-text muted small">{description}</p>
      {rows.length === 0 ? (
        <p className="muted small">No data yet.</p>
      ) : (
        <div className="bar-chart">
          {rows.map(([label, value]) => (
            <div className="bar-row" key={label}>
              <span className="bar-label">{label}</span>
              <span className="bar-track"><span className="bar-fill" style={{ width: `${(value / max) * 100}%` }} /></span>
              <span className="bar-value numeric">{value}</span>
            </div>
          ))}
        </div>
      )}
      <p className="insight-footer small muted">Screening result, expert review required</p>
    </section>
  );
}

export function DashboardPage() {
  const { api } = useSession();
  const me = useMe();
  const canSources = me.capabilities.includes("SOURCE_READ");
  const canCases = me.capabilities.includes("CASE_READ");
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [analyses, cases] = await Promise.all([
        canSources ? api.listIficAnalyses(signal).then((r) => r.items) : Promise.resolve([] as Analysis[]),
        canCases ? api.listCases({ sort: "priority" }, undefined, signal).then((r) => r.items) : Promise.resolve([] as CaseItem[]),
      ]);
      return { analyses, cases };
    },
    [api, canSources, canCases],
  );
  const { result, retry } = useLoad(load);

  if (result === null) {
    return <main className="content"><p role="status" aria-busy="true">Loading the dashboard…</p></main>;
  }
  if (result.data === undefined) {
    return (
      <main className="content">
        <h1>Dashboard</h1>
        <p role="alert">{describeError(result.error)}</p>
        <button type="button" onClick={retry}>Try again</button>
      </main>
    );
  }
  const { analyses, cases } = result.data;
  const ordered = [...analyses].sort((a, b) => a.issue - b.issue);
  const latest = (kind: string) => [...ordered].reverse().find((a) => kindLabel(a.kind) === kind);
  const latestTerr = latest("Terrestrial");
  const latestSpace = latest("Space");
  const notices = sum(Object.fromEntries(analyses.map((a) => [a.analysis_id, a.findings_count])));
  const exceedTerr = latestTerr ? sum(counts(latestTerr, "concerns"), EXCEEDANCE) : 0;
  const exceedSpace = latestSpace ? sum(counts(latestSpace, "concerns"), EXCEEDANCE) : 0;
  const nearAll = analyses.reduce((t, a) => t + (counts(a, "concerns").POTENTIAL_CONCERN ?? 0), 0);
  const openCases = cases.filter((c) => !["ACCEPTED", "REJECTED", "CLOSED"].includes(c.review_status));
  const awaiting = cases.filter((c) => c.review_status === "NEW");
  const concernRows = (analysis?: Analysis): [string, number][] =>
    analysis
      ? Object.entries(counts(analysis, "concerns"))
          .sort((a, b) => b[1] - a[1])
          .map(([k, v]) => [CONCERN_TEXT[k] ?? k, v])
      : [];
  const adminRows = (analysis?: Analysis): [string, number][] =>
    analysis ? Object.entries(counts(analysis, "top_administrations")).slice(0, 6) : [];

  const insights: string[] = [];
  if (latestTerr && exceedTerr > 0) {
    insights.push(`${exceedTerr} terrestrial notices in IFIC ${latestTerr.issue} exceed the T/R 25-08 coordination threshold at the Finnish border or territorial-sea limit.`);
  }
  if (latestSpace && exceedSpace > 0) {
    insights.push(`${exceedSpace} space notices in IFIC ${latestSpace.issue} have a worst-case PFD above the RR Table 21-4 limit somewhere in Finland.`);
  }
  if (nearAll > 0) insights.push(`${nearAll} notices are within the 6 dB concern window below a limit.`);
  if (awaiting.length > 0) insights.push(`${awaiting.length} cases are waiting for a first review.`);
  if (insights.length === 0) insights.push("No analysed IFIC issue reports a concern yet. Run an analysis from the IFIC issues page.");

  return (
    <main className="content">
      <header className="page-header">
        <h1>Dashboard</h1>
        <p className="muted">Spectrum screening at a glance: what was published, what needs a look, and why.</p>
      </header>

      <div className="kpi-grid">
        <Kpi label="IFIC issues analysed" value={analyses.length} trend={ordered.map((a) => a.findings_count)} />
        <Kpi label="Notices screened" value={notices.toLocaleString()} note="all analysed issues" />
        <Kpi label="Terrestrial above threshold" value={exceedTerr} note={latestTerr ? `IFIC ${latestTerr.issue}` : "no terrestrial issue"} />
        <Kpi label="Space worst case above limit" value={exceedSpace} note={latestSpace ? `IFIC ${latestSpace.issue}` : "no space issue"} />
        <Kpi label="Open cases" value={openCases.length} note={`${awaiting.length} awaiting first review`} />
        <Kpi label="Near threshold" value={nearAll} unit="notices" note="within 6 dB" />
      </div>

      <section className="insight insight-wide" aria-labelledby="insights-title">
        <h2 id="insights-title" className="insight-title">Insights</h2>
        <ul className="plain">{insights.map((text) => <li key={text}>{text}</li>)}</ul>
        <p className="insight-footer small muted">Screening results, not findings of harmful interference or non-compliance.</p>
      </section>

      <div className="insight-grid">
        <Bars title={`Terrestrial concern classes${latestTerr ? ` · IFIC ${latestTerr.issue}` : ""}`} description="Land-mobile notices against ECC T/R 25-08 A1.2.3 along the border and territorial-sea limit." rows={concernRows(latestTerr)} />
        <Bars title={`Space concern classes${latestSpace ? ` · IFIC ${latestSpace.issue}` : ""}`} description="Downlink groups against ITU RR Article 21 Table 21-4, worst-case PFD over Finland." rows={concernRows(latestSpace)} />
        <Bars title="Notices per issue" description="How much each IFIC issue brought to screen." rows={ordered.map((a) => [`${kindLabel(a.kind)} ${a.issue}`, a.findings_count])} />
        <Bars title="Top administrations" description="Notifying administrations in the latest terrestrial issue." rows={adminRows(latestTerr)} />
      </div>

      {canCases && (
        <section className="insight insight-wide" aria-labelledby="review-title">
          <h2 id="review-title" className="insight-title">Needs review</h2>
          {openCases.length === 0 ? (
            <p className="muted small">Nothing is waiting for review.</p>
          ) : (
            <ul className="review-list plain">
              {openCases.slice(0, 8).map((item) => (
                <li key={item.case_id}>
                  <Link to={`/cases/${encodeURIComponent(item.case_id)}`}>
                    {item.administration ?? "Unknown"} · {formatFrequencyRange(item.frequency_start_mhz, item.frequency_end_mhz)}
                  </Link>
                  <span className="muted small"> · {item.domain === "SPACE" ? "Space" : "Terrestrial"} · {item.finding_status.replaceAll("_", " ").toLowerCase()}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="insight-footer small muted">Screening result, expert review required</p>
        </section>
      )}
      {me.capabilities.includes("JOB_READ") && <OperationsPanel />}
    </main>
  );
}
