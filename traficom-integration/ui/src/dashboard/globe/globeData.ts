/**
 * Findings to globe markers. Positions come from the notices themselves: terrestrial stations
 * at their notified coordinates; GSO satellites at their nominal orbital longitude on the
 * equator; non-GSO satellites have no single position, so they are drawn at a deterministic,
 * labelled illustrative point at the highest latitude their inclination reaches near Finland.
 */
import type { Schemas } from "../../api/client";

export type MarkerKind = "space" | "terrestrial";

export interface GlobeMarker {
  key: string;
  kind: MarkerKind;
  lat: number;
  lon: number;
  /** Display radius in Earth radii (compressed; not to scale). */
  radius: number;
  label: string;
  administration: string;
  frequency: string;
  classification: string;
  issue: string;
  color: string;
  margin: number | null;
  noticeId: string;
  caseId: string | null;
  illustrative: boolean;
}

export const FINLAND = { lat: 64.5, lon: 26.0 };

export const ISSUE: Record<string, { text: string; color: string; rank: number }> = {
  VERIFIED_CRITERION_EXCEEDANCE: { text: "Above coordination threshold", color: "#fb7185", rank: 0 },
  WORST_CASE_EXCEEDANCE: { text: "Worst-case PFD above limit", color: "#f97316", rank: 1 },
  COORDINATION_REVIEW: { text: "Above threshold, coordination noted", color: "#fbbf24", rank: 2 },
  POTENTIAL_CONCERN: { text: "Near threshold", color: "#facc15", rank: 3 },
  CASE_OPEN: { text: "Open case, needs review", color: "#38bdf8", rank: 4 },
  CHANGED: { text: "New or modified notice", color: "#a78bfa", rank: 5 },
};

const FLAGGED = new Set(["VERIFIED_CRITERION_EXCEEDANCE", "WORST_CASE_EXCEEDANCE", "COORDINATION_REVIEW", "POTENTIAL_CONCERN"]);
const MAX_MARKERS = 160;

function hash(text: string): number {
  let h = 2166136261;
  for (let i = 0; i < text.length; i += 1) {
    h = Math.imul(h ^ text.charCodeAt(i), 16777619);
  }
  return (h >>> 0) / 4294967295;
}

type Detail = Record<string, unknown>;

function concernOf(detail: Detail): { classification?: string; margin_db?: number | null } {
  return (detail.concern as { classification?: string; margin_db?: number | null } | undefined) ?? {};
}

function frequencyOf(finding: Schemas["IficFinding"], detail: Detail): string {
  const f = detail.frequency_mhz;
  if (typeof f === "number") return `${f} MHz`;
  const groups = detail.groups as { range_mhz?: [number, number] }[] | undefined;
  const range = groups?.[0]?.range_mhz;
  return range ? `${range[0]}–${range[1]} MHz` : finding.label ?? "";
}

/** Issue category for colour and wording; null when the finding should not be drawn. */
export function issueOf(finding: Schemas["IficFinding"], hasCase: boolean): string | null {
  const detail = finding.detail as Detail;
  const classification = concernOf(detail).classification;
  if (classification && FLAGGED.has(classification)) return classification;
  if (hasCase) return "CASE_OPEN";
  if (finding.priority_tier === "HIGH" && (finding.change_type === "NEW" || finding.change_type === "MODIFIED")) {
    return "CHANGED";
  }
  return null;
}

export function toMarker(finding: Schemas["IficFinding"], caseId: string | null): GlobeMarker | null {
  const issue = issueOf(finding, caseId !== null);
  if (issue === null) return null;
  const detail = finding.detail as Detail;
  const base = {
    key: `${finding.domain}-${finding.notice_id}`,
    label: finding.label ?? `Notice ${finding.notice_id}`,
    administration: finding.administration ?? "Unknown",
    frequency: frequencyOf(finding, detail),
    classification: issue,
    issue: ISSUE[issue]!.text,
    color: ISSUE[issue]!.color,
    margin: concernOf(detail).margin_db ?? null,
    noticeId: finding.notice_id,
    caseId,
  };
  if (finding.domain === "TERRESTRIAL") {
    const site = detail.site_coordinates as [number, number] | null | undefined;
    if (!site) return null;
    return { ...base, kind: "terrestrial", lat: site[0], lon: site[1], radius: 1.004, illustrative: false };
  }
  const geometry = (detail.stage_c_geometry ?? {}) as {
    nominal_longitude_deg?: number;
    inclination_deg_range?: number[];
    perigee_km_range?: number[];
  };
  if (typeof geometry.nominal_longitude_deg === "number") {
    return { ...base, kind: "space", lat: 0, lon: geometry.nominal_longitude_deg, radius: 1.55, illustrative: false };
  }
  const inclination = geometry.inclination_deg_range?.length ? Math.max(...geometry.inclination_deg_range) : null;
  if (inclination === null) return null;
  const folded = Math.min(inclination, 180 - inclination);
  const lat = Math.min(folded, 72) * (hash(finding.notice_id) > 0.5 ? 1 : 0.8);
  const lon = FINLAND.lon + (hash(`${finding.notice_id}:lon`) - 0.5) * 120;
  const perigee = geometry.perigee_km_range?.length ? Math.min(...geometry.perigee_km_range) : 600;
  return {
    ...base,
    kind: "space",
    lat,
    lon,
    radius: 1.08 + Math.min(perigee, 20000) / 20000 * 0.3,
    illustrative: true,
  };
}

export function buildMarkers(findings: Schemas["IficFinding"][], cases: Schemas["CaseSummary"][]): GlobeMarker[] {
  const caseByNotice = new Map(cases.map((c) => [c.notice_id, c.case_id]));
  const seen = new Set<string>();
  const markers: GlobeMarker[] = [];
  for (const finding of findings) {
    const marker = toMarker(finding, caseByNotice.get(finding.notice_id) ?? null);
    if (marker && !seen.has(marker.key)) {
      seen.add(marker.key);
      markers.push(marker);
    }
  }
  markers.sort((a, b) => ISSUE[a.classification]!.rank - ISSUE[b.classification]!.rank);
  return markers.slice(0, MAX_MARKERS);
}

/** Unit vector for (lat, lon) in the frame of three.js SphereGeometry's equirectangular UVs. */
export function toVector(lat: number, lon: number, radius = 1): [number, number, number] {
  const phi = ((lon + 180) * Math.PI) / 180;
  const theta = (lat * Math.PI) / 180;
  return [-Math.cos(phi) * Math.cos(theta) * radius, Math.sin(theta) * radius, Math.sin(phi) * Math.cos(theta) * radius];
}
