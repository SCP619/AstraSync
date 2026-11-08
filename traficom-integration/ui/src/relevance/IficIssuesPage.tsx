/**
 * IFIC issues: analysed Space and Terrestrial BR IFIC issues, their ranked findings and each
 * finding's stage-by-stage reasoning (DECISIONS G27). Everything shown comes from the API; the
 * priority orders expert work and is never presented as a regulatory finding.
 */
import { useCallback, useState } from "react";
import type { Schemas } from "../api/client";
import { describeError, RequestId, useLoad, useSession } from "../shared";

type Analysis = Schemas["IficAnalysis"];
type Finding = Schemas["IficFinding"];
type Tier = "HIGH" | "MEDIUM" | "LOW";

function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

function Stage({ title, value }: { title: string; value: unknown }) {
  return (
    <details>
      <summary>{title}</summary>
      <Json value={value} />
    </details>
  );
}

function FindingDetail({ finding }: { finding: Finding }) {
  const d = finding.detail as Record<string, unknown> & {
    calculations?: Array<Record<string, unknown>>;
    change?: Record<string, unknown>;
    priority?: { components?: Record<string, number> };
  };
  const calculations = d.calculations ?? [];
  return (
    <section className="panel" aria-labelledby="finding-title">
      <h2 id="finding-title">
        #{finding.rank} {finding.administration} {finding.label ?? finding.notice_id}
      </h2>
      <p className="muted small">
        Notice <code>{finding.notice_id}</code> · {finding.domain} · change {finding.change_type} · status{" "}
        <strong>{finding.finding_status}</strong>
      </p>
      <p className="notice">
        {String(d.regulatory_finding ?? "")}. Priority orders expert work; it is not a statement of
        interference or of a limit exceedance.
      </p>
      <h3>Why it was selected</h3>
      <ul className="plain">
        {Object.entries(d.priority?.components ?? {}).map(([name, points]) => (
          <li key={name}>
            {points > 0 ? "✔" : "–"} {name.replaceAll("_", " ")} {points > 0 ? `(+${points})` : ""}
          </li>
        ))}
      </ul>
      <h3>Technical calculations</h3>
      {calculations.length === 0 ? (
        <p className="muted">No calculation: see readiness (stage D) for the missing inputs.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Method</th><th>Receiver / group</th><th>Value</th><th>Assumptions</th></tr>
            </thead>
            <tbody>
              {calculations.map((c, index) => (
                <tr key={index}>
                  <td>
                    <code>{String(c.method_id)}</code> {String(c.method_version)}
                  </td>
                  <td>{String(c.receiver ?? c.group_id ?? "–")}</td>
                  <td className="num">
                    {Number(c.numeric_value).toFixed(2)} {String(c.unit)}
                    {c.reference_bandwidth_hz ? ` in ${String(c.reference_bandwidth_hz)} Hz` : ""}
                  </td>
                  <td>
                    <ul className="plain small">
                      {(c.assumptions as string[]).map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3>Stage results</h3>
      <Stage title="Change against the published intent and previous issue" value={d.change} />
      <Stage title="A — Frequency" value={d.stage_a_frequency} />
      <Stage title="B — Service" value={d.stage_b_service} />
      <Stage title="C — Geography / orbit" value={d.stage_c_geography ?? d.stage_c_geometry} />
      <Stage title="D — Technical readiness" value={d.stage_d_readiness} />
      {"groups" in d && <Stage title="Frequency groups (highest relevance first)" value={d.groups} />}
      {"data_quality_anomalies" in d && Number(d.data_quality_anomaly_count) > 0 && (
        <Stage title="Data-quality anomalies in the published notice" value={d.data_quality_anomalies} />
      )}
      <Stage title="Calculation inputs and traces" value={calculations} />
    </section>
  );
}

function Findings({ analysis }: { analysis: Analysis }) {
  const { api } = useSession();
  const [tier, setTier] = useState<Tier | undefined>("HIGH");
  const [cursor, setCursor] = useState<string | undefined>(undefined);
  const [selected, setSelected] = useState<Finding | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => api.listIficFindings(analysis.analysis_id, tier, cursor, signal),
    [api, analysis.analysis_id, tier, cursor],
  );
  const { result, retry } = useLoad(load);
  const isSpace = analysis.kind === "SPACE_IFIC";
  return (
    <>
      <section className="panel" aria-labelledby="findings-title">
        <h2 id="findings-title">Findings</h2>
        <div className="actions" role="group" aria-label="Priority tier">
          {(["HIGH", "MEDIUM", "LOW", undefined] as const).map((value) => (
            <button
              key={value ?? "ALL"}
              type="button"
              className={tier === value ? "primary" : undefined}
              aria-pressed={tier === value}
              onClick={() => {
                setTier(value);
                setCursor(undefined);
                setSelected(null);
              }}
            >
              {value ?? "All"}
            </button>
          ))}
        </div>
        {result === null && <p className="muted" role="status">Loading findings…</p>}
        {result?.error !== undefined && (
          <div role="alert" className="notice">
            <p>{describeError(result.error)}</p>
            <RequestId error={result.error} />
            <button type="button" onClick={retry}>Try again</button>
          </div>
        )}
        {result?.data?.items.length === 0 && <p className="muted">No findings in this tier.</p>}
        {result?.data !== undefined && result.data.items.length > 0 && (
          <div className="table-scroll">
            <table>
              <caption className="muted small">
                {result.data.total_if_known} findings in this view, ranked by priority
              </caption>
              <thead>
                <tr>
                  <th>Rank</th><th>Administration</th><th>{isSpace ? "Network" : "Site"}</th>
                  <th>Change</th><th>Score</th><th>Status</th>
                  <th>{isSpace ? "PFD upper bound" : "Max field strength"}</th>
                </tr>
              </thead>
              <tbody>
                {result.data.items.map((f) => (
                  <tr key={f.notice_id} aria-selected={selected?.notice_id === f.notice_id}>
                    <td className="num">{f.rank}</td>
                    <td>{f.administration}</td>
                    <td>
                      <button type="button" className="link" onClick={() => setSelected(f)}>
                        {f.label ?? f.notice_id}
                      </button>
                    </td>
                    <td>{f.change_type}</td>
                    <td className="num">
                      {f.priority_score} ({f.priority_tier})
                    </td>
                    <td>{f.finding_status}</td>
                    <td className="num">
                      {f.max_value === null ? "–" : `${f.max_value.toFixed(1)} ${f.max_value_unit ?? ""}`}
                    </td>
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
      {selected !== null && <FindingDetail key={selected.notice_id} finding={selected} />}
    </>
  );
}

export function IficIssuesPage() {
  const { api } = useSession();
  const load = useCallback((signal: AbortSignal) => api.listIficAnalyses(signal), [api]);
  const { result, retry } = useLoad(load);
  const [selected, setSelected] = useState<string | null>(null);
  const items = result?.data?.items ?? [];
  const analysis = items.find((a) => a.analysis_id === selected) ?? items[0];
  return (
    <main className="content">
      <h1>IFIC issues</h1>
      <p className="muted">
        Space and Terrestrial BR IFIC issues acquired from the ITU, screened against Finnish
        frequency use (M4 table and special-interest stations). Issues are analysed automatically
        after they are downloaded, verified and indexed.
      </p>
      <section className="panel" aria-labelledby="issues-title">
        <h2 id="issues-title">Analysed issues</h2>
        {result === null && <p className="muted" role="status">Loading issues…</p>}
        {result?.error !== undefined && (
          <div role="alert" className="notice">
            <p>{describeError(result.error)}</p>
            <RequestId error={result.error} />
            <button type="button" onClick={retry}>Try again</button>
          </div>
        )}
        {result?.data !== undefined && items.length === 0 && (
          <p className="muted">
            No IFIC issue has been analysed yet. An administrator can check the ITU sources for new
            issues from the source library.
          </p>
        )}
        {items.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr><th>Issue</th><th>Kind</th><th>Findings</th><th>Tiers</th><th>Changes</th><th>Cases</th></tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.analysis_id} aria-selected={a.analysis_id === analysis?.analysis_id}>
                    <td>
                      <button type="button" className="link" onClick={() => setSelected(a.analysis_id)}>
                        {a.issue}
                      </button>
                    </td>
                    <td>{a.kind === "SPACE_IFIC" ? "Space" : "Terrestrial"}</td>
                    <td className="num">{a.findings_count}</td>
                    <td className="small">{JSON.stringify(a.summary.tiers ?? {})}</td>
                    <td className="small">{JSON.stringify(a.summary.change_types ?? {})}</td>
                    <td className="num">{a.cases_created}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {analysis !== undefined && (
          <p className="muted small">
            Rule set <code>{analysis.rule_version}</code> · findings SHA-256{" "}
            <code>{analysis.findings_sha256?.slice(0, 16)}…</code>
          </p>
        )}
      </section>
      {analysis !== undefined && <Findings key={analysis.analysis_id} analysis={analysis} />}
    </main>
  );
}
