/**
 * Judge demonstration: a bundled, labelled synthetic dataset (src/demo/judge-demo.json, built by
 * astrasync-core-lib/tools/build_judge_demo.py from invented notices with the real screening
 * code). No sign-in, no API calls, no privileges, nothing protected: it works offline and on a
 * static host, and it never pretends to be live analysis.
 */
import { useState } from "react";
import { Link } from "react-router-dom";
import demo from "./judge-demo.json";

type Scenario = (typeof demo.scenarios)[number] & Record<string, unknown>;

interface Point {
  kind?: string;
  label?: string;
  lat?: number;
  lon?: number;
  distance_km?: number;
  field_strength_dbuv_m?: number;
}

function fmt(value: unknown, digits = 2, unit = ""): string {
  return typeof value === "number" ? `${value.toFixed(digits)}${unit ? ` ${unit}` : ""}` : "–";
}

function Terrestrial({ s }: { s: Scenario }) {
  const concern = s.concern as { classification: string; margin_db: number | null; concern_margin_db?: number; meaning?: string | null };
  const criterion = s.criterion as { threshold_dbuv_m: number; base_threshold_dbuv_m: number; bandwidth_correction_db: number; basis: string; citation: string };
  const border = s.border as { points_evaluated: number; max_field_strength_dbuv_m: number; max_point: Point; parameters: Record<string, unknown> };
  const coordination = s.coordination as { finland_mentioned: boolean };
  return (
    <dl className="facts">
      <dt>Classification</dt>
      <dd><strong>{concern.classification}</strong></dd>
      <dt>Frequency</dt>
      <dd>{fmt(s.frequency_mhz as number, 3, "MHz")} · {fmt(s.bandwidth_khz as number, 1, "kHz")}</dd>
      <dt>Highest border value (P.1546-6)</dt>
      <dd>
        {fmt(border.max_field_strength_dbuv_m, 2, "dB(µV/m)")} at {border.max_point.label} (
        {fmt(border.max_point.lat, 3)}, {fmt(border.max_point.lon, 3)}), {fmt(border.max_point.distance_km, 1, "km")};{" "}
        {border.points_evaluated} boundary points evaluated
      </dd>
      <dt>Threshold</dt>
      <dd>
        {fmt(criterion.threshold_dbuv_m, 2, "dB(µV/m)")} ({criterion.basis}; base {criterion.base_threshold_dbuv_m}, bandwidth
        correction {criterion.bandwidth_correction_db} dB)
      </dd>
      <dt>Margin</dt>
      <dd>{fmt(concern.margin_db, 2, "dB")} (concern window {concern.concern_margin_db ?? 6} dB)</dd>
      <dt>Coordination with Finland noted</dt>
      <dd>{coordination.finland_mentioned ? "Yes: expert review of the coordination history" : "No"}</dd>
      <dt>Parameters</dt>
      <dd className="small">{Object.entries(border.parameters).map(([k, v]) => `${k} ${String(v)}`).join(" · ")}</dd>
      <dt>Source</dt>
      <dd className="small">{criterion.citation}</dd>
    </dl>
  );
}

function Workbook({ s }: { s: Scenario }) {
  const raw = s.raw as Record<string, string>;
  const normalized = s.normalized as Record<string, unknown>;
  return (
    <div className="table-scroll">
      <table>
        <thead><tr><th scope="col">Field</th><th scope="col">As published</th><th scope="col">Interpreted</th></tr></thead>
        <tbody>
          <tr><td>Channel bandwidth</td><td>{raw.channel_bandwidth}</td><td className="num">{fmt(normalized.channel_bandwidth_hz, 0, "Hz")}</td></tr>
          <tr><td>Transmission bandwidth</td><td>{raw.transmission_bandwidth}</td><td className="num">{fmt(normalized.emission_bandwidth_hz, 0, "Hz")}</td></tr>
          <tr><td>Screening bandwidth</td><td>–</td><td className="num">{fmt(normalized.effective_bandwidth_hz, 0, "Hz")} ({String(normalized.effective_bandwidth_rule)})</td></tr>
          <tr><td>Licence class</td><td>{raw.licence_class}</td><td>{String(normalized.licence_class_normalized)}</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function Space({ s }: { s: Scenario }) {
  const geometry = s.geometry as { status: string; min_slant_range_km?: number | null; evaluation_grid?: { nodes: number; max_pfd_location: Point & { elevation_deg?: number } | null } };
  const location = geometry.evaluation_grid?.max_pfd_location;
  const readiness = s.readiness as { status?: string; missing_inputs?: string[] } | undefined;
  return (
    <dl className="facts">
      <dt>PFD upper bound</dt>
      <dd>{fmt(s.max_pfd_db_w_m2_hz_upper_bound as number | null, 2, "dB(W/m²·Hz)")}</dd>
      <dt>RR Table 21-4</dt>
      <dd>
        <strong>{(s.concern as { classification?: string } | undefined)?.classification ?? "–"}</strong>
        {(() => {
          const check = s.criterion_check as
            | { entry_id: string; bands: string[]; pfd_db_w_m2: number; limit_db_w_m2: number; angle_of_arrival_deg: number; margin_db: number; reference_bandwidth_hz: number }
            | null
            | undefined;
          return check ? (
            <>
              {" "}· entry {check.entry_id} ({check.bands.join(", ")}): {fmt(check.pfd_db_w_m2, 2)} vs limit{" "}
              {fmt(check.limit_db_w_m2, 2, "dB(W/m²)")} in {check.reference_bandwidth_hz / 1000} kHz at δ{" "}
              {fmt(check.angle_of_arrival_deg, 1, "°")}, margin {fmt(check.margin_db, 2, "dB")}
            </>
          ) : null;
        })()}
      </dd>
      <dt>Geometry</dt>
      <dd>
        {geometry.status}
        {location && <> · nearest grid node ({fmt(location.lat, 2)}, {fmt(location.lon, 2)}), elevation {fmt(location.elevation_deg, 1, "°")}, slant range {fmt(geometry.min_slant_range_km, 0, "km")} of {geometry.evaluation_grid?.nodes} nodes</>}
      </dd>
      {readiness?.missing_inputs && readiness.missing_inputs.length > 0 && (
        <>
          <dt>Missing inputs</dt>
          <dd>{readiness.missing_inputs.join(", ")}</dd>
        </>
      )}
      <dt>Regulatory status</dt>
      <dd>{String(s.regulatory_finding)}</dd>
    </dl>
  );
}

export function JudgeDemoPage() {
  const scenarios = demo.scenarios as Scenario[];
  const [selected, setSelected] = useState(scenarios[0]?.id);
  const current = scenarios.find((s) => s.id === selected) ?? scenarios[0];
  return (
    <main className="content">
      <p role="note" className="notice" aria-label="Demonstration data notice">
        <strong>Demonstration data (synthetic).</strong> {demo.data_status} Dataset {demo.dataset}.
      </p>
      <h1>AstraSync judge demonstration</h1>
      <p className="muted">
        Each scenario is an invented notice run through the same code as the IFIC 3074 and 3076
        evaluations. Real results need sign-in. <Link to="/login">Sign in</Link>
      </p>
      <div className="two-pane">
        <nav aria-label="Scenarios">
          <ol className="plain">
            {scenarios.map((s) => (
              <li key={s.id}>
                <button type="button" className="link" aria-current={s.id === current?.id} onClick={() => setSelected(s.id)}>
                  {s.title}
                </button>{" "}
                <span className="muted small">{s.domain}</span>
              </li>
            ))}
          </ol>
        </nav>
        {current && (
          <section className="panel" aria-labelledby="scenario-title">
            <h2 id="scenario-title">{current.title}</h2>
            <p className="muted small"><code>{current.id}</code> · {current.domain} · synthetic</p>
            <p>{current.story}</p>
            {current.domain === "TERRESTRIAL" && <Terrestrial s={current} />}
            {current.domain === "WORKBOOK" && <Workbook s={current} />}
            {current.domain === "SPACE" && <Space s={current} />}
            <p className="muted small">
              Screening results, not findings of harmful interference or non-compliance.
            </p>
          </section>
        )}
      </div>
    </main>
  );
}
