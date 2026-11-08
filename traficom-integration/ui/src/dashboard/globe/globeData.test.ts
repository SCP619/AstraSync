import { describe, expect, it } from "vitest";
import type { Schemas } from "../../api/client";
import { buildMarkers, toMarker, toVector } from "./globeData";

const finding = (over: Partial<Schemas["IficFinding"]> & { detail?: Record<string, unknown> }): Schemas["IficFinding"] => ({
  rank: 1,
  notice_id: "N1",
  domain: "TERRESTRIAL",
  administration: "RUS",
  label: "KOSTOMUKSHA",
  change_type: "NEW",
  priority_score: 10,
  priority_tier: "HIGH",
  finding_status: "EXPERT_REVIEW_REQUIRED",
  max_value: null,
  max_value_unit: null,
  detail: {},
  ...over,
});

describe("globe markers", () => {
  it("places a terrestrial station at its notified coordinates with its issue colour", () => {
    const marker = toMarker(
      finding({ detail: { site_coordinates: [64.6, 30.6], frequency_mhz: 152.025, concern: { classification: "COORDINATION_REVIEW", margin_db: 14.84 } } }),
      "CASE-1",
    );
    expect(marker).toMatchObject({ kind: "terrestrial", lat: 64.6, lon: 30.6, caseId: "CASE-1", margin: 14.84, illustrative: false });
    expect(marker?.issue).toMatch(/coordination noted/);
  });

  it("puts a GSO satellite on the equator at its nominal longitude", () => {
    const marker = toMarker(
      finding({ domain: "SPACE", detail: { stage_c_geometry: { nominal_longitude_deg: 60.5 }, concern: { classification: "WORST_CASE_EXCEEDANCE" } } }),
      null,
    );
    expect(marker).toMatchObject({ kind: "space", lat: 0, lon: 60.5, illustrative: false });
  });

  it("labels non-GSO positions as illustrative and keeps them deterministic", () => {
    const f = finding({ domain: "SPACE", notice_id: "S9", detail: { stage_c_geometry: { inclination_deg_range: [97.5], perigee_km_range: [550] }, concern: { classification: "POTENTIAL_CONCERN" } } });
    const a = toMarker(f, null);
    expect(a?.illustrative).toBe(true);
    expect(toMarker(f, null)).toEqual(a);
  });

  it("skips findings that are neither flagged, open cases nor high-priority changes", () => {
    const quiet = finding({ priority_tier: "LOW", detail: { site_coordinates: [60, 25], concern: { classification: "BELOW_SCREENING_THRESHOLD" } } });
    expect(toMarker(quiet, null)).toBeNull();
    expect(toMarker(quiet, "CASE-2")?.classification).toBe("CASE_OPEN");
  });

  it("orders the most serious issues first and de-duplicates notices", () => {
    const markers = buildMarkers(
      [
        finding({ notice_id: "A", detail: { site_coordinates: [60, 25], concern: { classification: "POTENTIAL_CONCERN" } } }),
        finding({ notice_id: "B", detail: { site_coordinates: [61, 26], concern: { classification: "VERIFIED_CRITERION_EXCEEDANCE" } } }),
        finding({ notice_id: "B", detail: { site_coordinates: [61, 26], concern: { classification: "VERIFIED_CRITERION_EXCEEDANCE" } } }),
      ],
      [],
    );
    expect(markers.map((m) => m.noticeId)).toEqual(["B", "A"]);
  });

  it("maps longitude 0 to +X and the north pole to +Y", () => {
    const [x] = toVector(0, 0);
    expect(x).toBeCloseTo(1);
    expect(toVector(90, 0)[1]).toBeCloseTo(1);
  });
});
