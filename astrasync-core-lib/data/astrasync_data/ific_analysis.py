"""Deterministic IFIC analysis: change, Finland relevance stages A-E, calculations, priority.

One implementation for both the evaluation command (``ific_evaluate``) and the backend worker.
Inputs are parsed records from ``itu_ific`` plus Finnish references (M4 table, special-interest
workbook). Every stage keeps its own result, so a reader can see why a notice was selected:

A  Frequency: closed-interval overlap with M4 sub-bands and special-interest station intervals.
   Every frequency lies in some M4 band (the table covers the whole spectrum), so an M4 overlap
   only records which Finnish allocations apply; it is not by itself a selection signal.
B  Service: whether the overlapping Finnish use can be affected by this kind of emission.
C  Geography / orbit: distance to Finland (terrestrial); GSO visibility, service area or NGSO
   reach (space).
D  Technical readiness: whether the inputs of an applicable method exist in the notice.
E  Priority: a documented additive score, kept apart from concern and from any limit finding.

Separate concepts, never merged: relevance (A-C), readiness (D), priority (E), and a regulatory
finding, which needs an approved criterion. No criterion is approved in this repository, so no
finding here is a limit exceedance; the strongest status is ``EXPERT_REVIEW_REQUIRED``. A
frequency overlap is never called interference, and missing data is ``UNKNOWN``, never "no".
"""

from __future__ import annotations

import json
import math
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import geo

RULE_VERSION = "ific-finland-relevance/1.0.0"
LAND_MOBILE_SERVICES = ("MOBILE", "LAND MOBILE")
TERRESTRIAL_SERVICES = ("FIXED", "MOBILE", "LAND MOBILE", "BROADCASTING", "RADIO ASTRONOMY")
NEIGHBOURS = ("RUS", "EST", "S", "NOR", "LTU", "LVA", "BLR", "POL", "D", "DNK")
# Screening parameters for terrestrial field strength. They are AstraSync defaults, chosen to
# be typical of land mobile coordination; they are not an approved criterion's conditions.
SCREEN_TIME_PERCENT = 10.0
SCREEN_LOCATION_PERCENT = 50.0
SCREEN_RX_HEIGHT_M = 10.0
SCREEN_RX_AREA = "Rural"
MAX_P1546_DISTANCE_KM = 1000.0
# Free-space PFD for space groups is computed per 1 Hz from the notified maximum power density.
PFD_REFERENCE_BANDWIDTH_HZ = 1.0


# --- References --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Reference:
    kind: str  # M4_ALLOCATION or SPECIAL_INTEREST_STATION
    key: str
    start_mhz: float
    end_mhz: float
    basis: str
    label: str
    services: tuple[str, ...] = ()
    station_classes: str | None = None
    station: dict[str, Any] | None = None
    is_synthetic: bool = False


class IntervalIndex:
    """Closed-interval lookup over many references (touching edges count)."""

    def __init__(self, references: Sequence[Reference]) -> None:
        self.references = list(references)
        points = sorted({r.start_mhz for r in references} | {r.end_mhz for r in references})
        self.points = points
        self.segments: list[list[int]] = [[] for _ in range(max(len(points), 1))]
        for index, ref in enumerate(self.references):
            first = bisect_right(points, ref.start_mhz) - 1
            last = max(first, bisect_right(points, ref.end_mhz) - 1)
            for k in range(first, min(last, len(points) - 1) + 1):
                self.segments[k].append(index)

    def overlapping(self, start: float, end: float) -> list[Reference]:
        if not self.points:
            return []
        first = max(bisect_right(self.points, start) - 1, 0)
        last = min(bisect_right(self.points, end) - 1, len(self.points) - 1)
        seen: set[int] = set()
        found = []
        for k in range(first, last + 1):
            for index in self.segments[k]:
                if index in seen:
                    continue
                seen.add(index)
                ref = self.references[index]
                if ref.start_mhz <= end and ref.end_mhz >= start:
                    found.append(ref)
        return found


def _services(text: str | None) -> tuple[str, ...]:
    if not text:
        return ()
    parts = [p.strip().upper() for p in text.replace(";", ",").split(",")]
    return tuple(p for p in parts if p)


def m4_references(records: Iterable[dict[str, Any]]) -> list[Reference]:
    """From ``TraficomM4TableAdapter`` records."""
    refs = []
    for r in records:
        start, end = r["frequency_start_mhz"], r["frequency_end_mhz"]
        if start is None or end is None:
            continue
        raw = r["raw_fields"]
        refs.append(
            Reference(
                "M4_ALLOCATION",
                f"Taajuusjakotaulukko!{r['source_row_or_key']}",
                start,
                end,
                "M4_SUB_BAND_LIMITS",
                raw.get("Sub_band_usage") or raw.get("Services_in_Finland") or "",
                _services(raw.get("Services_in_Finland")),
                raw.get("Class_of_station"),
            )
        )
    return refs


def station_references(records: Iterable[dict[str, Any]]) -> list[Reference]:
    """From ``TraficomWorkbookAdapter`` records: TX and RX intervals, centre +/- half channel."""
    refs = []
    for r in records:
        station = r.get("reference_station") or {}
        channel = station.get("channel_bandwidth_hz")
        for side, key in (("TX", "tx_frequency_hz"), ("RX", "rx_frequency_hz")):
            centre = station.get(key)
            if not isinstance(centre, int | float) or centre <= 0:
                continue
            if isinstance(channel, int | float) and channel > 0:
                basis, half = "CENTRE_PLUS_MINUS_HALF_CHANNEL_BANDWIDTH", channel / 2
            else:
                basis, half = "CENTRE_FREQUENCY_ONLY", 0.0
            refs.append(
                Reference(
                    "SPECIAL_INTEREST_STATION",
                    f"{r['source_table_or_sheet']}!{r['source_row_or_key']}:{side}",
                    max(centre - half, 0.0) / 1e6,
                    (centre + half) / 1e6,
                    basis,
                    f"Station {station.get('station_number_raw')} {side}",
                    station=station,
                    is_synthetic=True,
                )
            )
    return refs


@dataclass
class References:
    m4: IntervalIndex
    stations: IntervalIndex
    provenance: dict[str, Any] = field(default_factory=dict)


# --- Helpers ------------------------------------------------------------------------------------


def norm(record: dict[str, Any], key: str) -> Any:
    value = record["raw_fields"].get(f"norm.{key}")
    if value is None:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _match(ref: Reference, start: float, end: float) -> dict[str, Any]:
    return {
        "reference_kind": ref.kind,
        "reference_key": ref.key,
        "label": ref.label,
        "interval_basis": ref.basis,
        "reference_start_mhz": ref.start_mhz,
        "reference_end_mhz": ref.end_mhz,
        "overlap_start_mhz": max(ref.start_mhz, start),
        "overlap_end_mhz": min(ref.end_mhz, end),
        "services_in_finland": list(ref.services) or None,
        "station_classes_in_finland": ref.station_classes,
        "is_synthetic_reference": ref.is_synthetic,
    }


def _frequency_stage(refs: References, start: float | None, end: float | None) -> dict[str, Any]:
    if start is None or end is None:
        return {"status": "UNKNOWN", "reason": "NO_FREQUENCY_RANGE", "m4": [], "stations": []}
    m4 = refs.m4.overlapping(start, end)
    stations = refs.stations.overlapping(start, end)
    return {
        "status": "MATCH" if stations else "M4_ONLY" if m4 else "NO_MATCH",
        "range_mhz": [start, end],
        "m4": [_match(r, start, end) for r in m4[:20]],
        "m4_count": len(m4),
        "stations": [_match(r, start, end) for r in stations[:50]],
        "station_count": len(stations),
    }


def _has_service(matches: list[dict[str, Any]], names: Sequence[str]) -> bool:
    return any(
        service in names or any(service.startswith(n + " ") for n in names)
        for match in matches
        for service in (match["services_in_finland"] or [])
    )


# Tier thresholds per domain. Space notices overlap special-interest frequencies and are visible
# from Finland very often, so a HIGH space item also needs a strong Finland-specific signal
# (service area including Finland), which the higher threshold expresses.
TIER_THRESHOLDS = {"TERRESTRIAL": (7, 4), "SPACE": (10, 6)}


def _tier(score: int, domain: str = "TERRESTRIAL") -> str:
    high, medium = TIER_THRESHOLDS[domain]
    return "HIGH" if score >= high else "MEDIUM" if score >= medium else "LOW"


# --- Terrestrial --------------------------------------------------------------------------------

_TERR_COMPARED = (
    "assigned_frequency_mhz",
    "bandwidth_khz",
    "station_class",
    "emission_class",
    "latitude_deg",
    "longitude_deg",
    "area_radius_km",
    "radiated_power_dbw",
    "radiated_power_type",
    "antenna_height_agl_m",
    "antenna_gain_max_db",
    "azimuth_max_radiation_deg",
    "beamwidth_deg",
    "polarization",
    "date_in_use",
)


def _field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for key in _TERR_COMPARED:
        old, new = norm(before, key), norm(after, key)
        if old != new:
            changes.append({"field": key, "before": old, "after": new})
    return changes


def terrestrial_change(
    record: dict[str, Any],
    recorded: dict[str, dict[str, Any]],
    previous: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Change type from the notice's own intent; context from the target and the last issue.

    NEW, MODIFIED and WITHDRAWN come only from the notifying intent (ADD, MODIFY, SUPPRESS or
    WITHDRAW) in the publication. A missing assignment in a later extract is never a withdrawal:
    each extract holds that issue's notices only.
    """
    intent = norm(record, "intent")
    change = {"ADD": "NEW", "MODIFY": "MODIFIED", "SUPPRESS": "WITHDRAWN", "WITHDRAW": "WITHDRAWN"}
    result: dict[str, Any] = {
        "change_type": change.get(intent or "", "INDETERMINATE"),
        "basis": f"NOTICE_INTENT_{intent}" if intent else "NO_INTENT",
        "field_changes": [],
        "targets": norm(record, "targets") or [],
    }
    for target, action in result["targets"]:
        before = recorded.get(str(target))
        if before is not None and action == "MODIFY":
            result["field_changes"] = _field_changes(before, record)
            result["compared_with"] = f"fxm_terra!{target} (RECORDED, same extract)"
    if previous is not None:
        assignment = norm(record, "assignment_id")
        earlier = previous.get(str(assignment)) if assignment else None
        if earlier is not None:
            result["previous_issue"] = {
                "intent": norm(earlier, "intent"),
                "publications": norm(earlier, "publications"),
                "field_changes": _field_changes(earlier, record),
            }
    return result


def _erp_dbw(record: dict[str, Any]) -> tuple[float | None, str | None]:
    power = norm(record, "radiated_power_dbw")
    kind = norm(record, "radiated_power_type")
    if not isinstance(power, int | float):
        return None, None
    if kind == "ERP":
        return float(power), "e.r.p. as notified (RR 1.162)"
    if kind == "EIRP":
        return float(power) - 2.15, "e.r.p. = notified e.i.r.p. - 2.15 dB (RR 1.161, 1.162)"
    return None, None


def _p1546_scenario(
    record: dict[str, Any], rx_lat: float, rx_lon: float, rx_height_m: float, label: str
) -> tuple[dict[str, Any] | None, list[str]]:
    lat, lon = norm(record, "latitude_deg"), norm(record, "longitude_deg")
    f = norm(record, "assigned_frequency_mhz")
    ha = norm(record, "antenna_height_agl_m")
    erp, basis = _erp_dbw(record)
    missing = [
        name
        for name, value in (
            ("latitude", lat),
            ("longitude", lon),
            ("frequency", f),
            ("antenna height", ha),
            ("e.r.p.", erp),
        )
        if value is None
    ]
    if missing:
        return None, missing
    distance = geo.haversine_km(lat, lon, rx_lat, rx_lon)
    radius = norm(record, "area_radius_km")
    area_note = None
    if isinstance(radius, int | float) and radius > 0:
        # A mobile station notified for an area: the nearest edge of the area is used.
        area_note = f"Mobile area of radius {radius} km: distance taken from its nearest edge."
        distance = max(distance - radius, 0.1)
    if distance > MAX_P1546_DISTANCE_KM:
        return None, ["distance over 1000 km (outside P.1546)"]
    if not 30 <= f <= 4000:
        return None, ["frequency outside 30-4000 MHz (outside P.1546)"]
    zones = geo.path_zones(lat, lon, rx_lat, rx_lon) if area_note is None else None
    block: dict[str, Any] = {
        "frequency_mhz": f,
        "time_percent": SCREEN_TIME_PERCENT,
        "location_percent": SCREEN_LOCATION_PERCENT,
        "distance_km": distance,
        "erp_dbw": erp,
        "power_basis": basis,
        "tx_height_agl_m": ha,
        "effective_height_basis": "ASSUMED_EQUAL_TO_HA",
        "rx_height_agl_m": max(rx_height_m, 1.0),
        "rx_area": SCREEN_RX_AREA,
        "receiver": label,
    }
    if zones:
        total = sum(float(z[0]) for z in zones)
        block["zones"] = [[float(z[0]) * distance / total, z[1]] for z in zones]
    return {"terrestrial_p1546": block, "area_note": area_note}, []


def analyse_terrestrial(
    records: Sequence[dict[str, Any]],
    refs: References,
    previous: Sequence[dict[str, Any]] | None = None,
    *,
    p1546_method: Any = None,
    land_mobile_only: bool = True,
) -> dict[str, Any]:
    recorded = {r["source_row_or_key"]: r for r in records if norm(r, "role") == "RECORDED_CONTEXT"}
    previous_by_assignment = None
    if previous is not None:
        previous_by_assignment = {
            str(norm(r, "assignment_id")): r
            for r in previous
            if norm(r, "role") == "NOTICE" and norm(r, "assignment_id")
        }
    findings = []
    skipped: Counter[str] = Counter()
    for record in records:
        if norm(record, "role") != "NOTICE":
            continue
        if land_mobile_only and norm(record, "is_land_mobile") is not True:
            skipped["not_land_mobile"] += 1
            continue
        findings.append(
            _terrestrial_finding(record, refs, recorded, previous_by_assignment, p1546_method)
        )
    findings.sort(key=lambda f: (-f["priority"]["score"], -(f["max_field_strength"] or -999)))
    return {"findings": findings, "skipped": dict(skipped)}


def _terrestrial_finding(
    record: dict[str, Any],
    refs: References,
    recorded: dict[str, dict[str, Any]],
    previous: dict[str, dict[str, Any]] | None,
    method: Any,
) -> dict[str, Any]:
    start, end = record["frequency_start_mhz"], record["frequency_end_mhz"]
    change = terrestrial_change(record, recorded, previous)
    freq = _frequency_stage(refs, start, end)
    service: dict[str, Any]
    if freq["status"] == "UNKNOWN":
        service = {"status": "UNKNOWN"}
    else:
        m4_mobile = _has_service(freq["m4"], LAND_MOBILE_SERVICES)
        same_class = any(
            f"({norm(record, 'station_class')})" in (m["station_classes_in_finland"] or "")
            for m in freq["m4"]
        )
        service = {
            "status": "MATCH" if m4_mobile else "NO_MATCH",
            "notice_service": "LAND_MOBILE",
            "finnish_mobile_allocation": m4_mobile,
            "same_station_class_in_finland": same_class,
            "special_interest_stations_on_frequency": freq["station_count"],
        }
    lat, lon = norm(record, "latitude_deg"), norm(record, "longitude_deg")
    if lat is None or lon is None:
        geography: dict[str, Any] = {"status": "UNKNOWN", "reason": "NO_COORDINATES"}
        distance = None
    else:
        distance, blat, blon = geo.nearest_finland_point(lat, lon)
        radius = norm(record, "area_radius_km")
        if isinstance(radius, int | float) and radius > 0:
            distance = max(distance - radius, 0.0)
        geography = {
            "status": "WITHIN_1000_KM" if distance <= MAX_P1546_DISTANCE_KM else "BEYOND_1000_KM",
            "distance_to_finland_km": round(distance, 2),
            "nearest_finland_point": [round(blat, 4), round(blon, 4)],
            "site_country": norm(record, "site_country"),
            "basis": "Great-circle distance to the nearest vertex of the Natural Earth 1:10m "
            "Finland boundary; mobile areas reduced by their notified radius.",
        }

    calculations: list[dict[str, Any]] = []
    missing_inputs: list[str] = []
    if change["change_type"] != "WITHDRAWN" and geography.get("status") == "WITHIN_1000_KM":
        receivers = [
            ("Nearest point of Finland", *geography["nearest_finland_point"], SCREEN_RX_HEIGHT_M)
        ]
        for m in freq["stations"][:10]:
            station = next(
                (r.station for r in refs.stations.references if r.key == m["reference_key"]), None
            )
            if station and station.get("latitude_deg") is not None:
                receivers.append(
                    (
                        m["label"],
                        station["latitude_deg"],
                        station["longitude_deg"],
                        station.get("antenna_height_agl_m") or SCREEN_RX_HEIGHT_M,
                    )
                )
        for label, rlat, rlon, height in receivers:
            scenario, missing = _p1546_scenario(record, rlat, rlon, height, label)
            if scenario is None:
                missing_inputs.extend(missing)
                continue
            if method is None:
                continue
            assessment = method.assess_applicability(scenario)
            if assessment["applicability"] != "APPLICABLE":
                missing_inputs.extend(assessment["reason_codes"] + assessment["missing_fields"])
                continue
            output = method.calculate(scenario)
            if scenario.get("area_note"):
                output["assumptions"].append(scenario["area_note"])
            output["receiver"] = label
            calculations.append(output)
    readiness = {
        "status": "READY" if calculations else "NOT_READY" if missing_inputs else "NOT_ATTEMPTED",
        "method": "TERR_P1546",
        "missing_inputs": sorted(set(missing_inputs)),
    }
    max_e = max((c["numeric_value"] for c in calculations), default=None)

    near = distance is not None and distance <= 300
    components = {
        "change_new_or_modified": 1 if change["change_type"] in ("NEW", "MODIFIED") else 0,
        # A shared frequency matters most where the station can reach Finnish receivers.
        "special_interest_frequency_overlap": (3 if near else 1)
        if freq["status"] == "MATCH"
        else 0,
        "finnish_land_mobile_allocation": 1 if service.get("finnish_mobile_allocation") else 0,
        "within_100_km_of_finland": 2 if distance is not None and distance <= 100 else 0,
        "within_300_km_of_finland": 1 if distance is not None and distance <= 300 else 0,
        "neighbouring_administration": 1 if record["administration"] in NEIGHBOURS else 0,
        "calculation_available": 1 if calculations else 0,
    }
    score = sum(components.values())
    status = (
        "EXPERT_REVIEW_REQUIRED"
        if _tier(score) == "HIGH" and calculations
        else "INSUFFICIENT_DATA"
        if missing_inputs and not calculations and geography.get("status") == "WITHIN_1000_KM"
        else "SCREENED_LOW_PRIORITY"
    )
    return {
        "domain": "TERRESTRIAL",
        "notice_id": record["notice_id"],
        "record_key": f"{record['source_table_or_sheet']}!{record['source_row_or_key']}",
        "assignment_id": norm(record, "assignment_id"),
        "administration": record["administration"],
        "station_class": norm(record, "station_class"),
        "site_name": norm(record, "site_name"),
        "frequency_mhz": norm(record, "assigned_frequency_mhz"),
        "bandwidth_khz": norm(record, "bandwidth_khz"),
        "publications": norm(record, "publications"),
        "change": change,
        "stage_a_frequency": freq,
        "stage_b_service": service,
        "stage_c_geography": geography,
        "stage_d_readiness": readiness,
        "calculations": calculations,
        "max_field_strength": max_e,
        "priority": {"score": score, "tier": _tier(score), "components": components},
        "finding_status": status,
        "regulatory_finding": "NOT_EVALUATED: no approved criterion is configured",
        "rule_version": RULE_VERSION,
    }


def terrestrial_trends(
    current: Sequence[dict[str, Any]], previous: Sequence[dict[str, Any]] | None
) -> dict[str, Any]:
    """New activity by neighbouring administrations: band, station class, bandwidth, distance."""

    def bucket(f: float | None) -> str:
        if f is None:
            return "unknown"
        for low, high in ((30, 88), (88, 174), (174, 470), (470, 790), (790, 960), (960, 3000)):
            if low <= f < high:
                return f"{low}-{high} MHz"
        return "<30 MHz" if f < 30 else ">=3000 MHz"

    def profile(records: Sequence[dict[str, Any]]) -> dict[str, Counter[str]]:
        result: dict[str, Counter[str]] = defaultdict(Counter)
        for r in records:
            if norm(r, "role") != "NOTICE" or norm(r, "intent") not in ("ADD", "MODIFY"):
                continue
            adm = r["administration"] or "?"
            result[f"{adm}|band"][bucket(norm(r, "assigned_frequency_mhz"))] += 1
            result[f"{adm}|class"][norm(r, "station_class") or "?"] += 1
            result[f"{adm}|bandwidth_khz"][str(norm(r, "bandwidth_khz"))] += 1
            result[f"{adm}|total"]["notices"] += 1
        return result

    now = profile(current)
    before = profile(previous) if previous is not None else {}
    observations = []
    for key, counts in sorted(now.items()):
        adm, dimension = key.split("|")
        if adm not in NEIGHBOURS:
            continue
        for value, count in counts.most_common():
            earlier = before.get(key, Counter()).get(value, 0) if previous is not None else None
            observations.append(
                {
                    "administration": adm,
                    "dimension": dimension,
                    "value": value,
                    "notices_this_issue": count,
                    "notices_previous_issue": earlier,
                }
            )
    return {
        "definition": "ADD and MODIFY notices of neighbouring administrations, by band, station "
        "class and bandwidth, against the previous issue when given. Counts only; a change in "
        "counts is an observation for an expert, not a finding.",
        "neighbours": list(NEIGHBOURS),
        "observations": observations,
    }


# --- Space --------------------------------------------------------------------------------------


def space_change(notice: dict[str, Any], previous_ids: set[str] | None) -> dict[str, Any]:
    target = norm(notice, "target_notice_id")
    flag = norm(notice, "internal_external_flag")
    occurrence = norm(notice, "submission_occurrence")
    notice_id = norm(notice, "notice_id")
    if flag in ("W", "Z"):
        change, basis = "WITHDRAWN", f"f_int_ext={flag} (administration or BR withdrawal)"
    elif target and target != notice_id:
        change, basis = "MODIFIED", f"tgt_ntc_id={target} (notice to be modified or suppressed)"
    elif occurrence == "F":
        change, basis = "NEW", "ntf_occurs=F (first submission)"
    elif any(str(s).startswith("API/A/") for s in norm(notice, "special_sections") or []):
        change, basis = "NEW", "Special Section API/A (advance publication), no target notice"
    else:
        change, basis = "INDETERMINATE", f"ntf_occurs={occurrence}, no target notice"
    result: dict[str, Any] = {
        "change_type": change,
        "basis": basis,
        "action_code_raw": norm(notice, "action_code"),
    }
    if previous_ids is not None:
        result["in_previous_issue"] = notice_id in previous_ids or (target in previous_ids)
    return result


def _space_geometry(group: dict[str, Any]) -> dict[str, Any]:
    kind = norm(group, "notice_type")
    if kind == "GSO_SPACE_STATION":
        longitude = norm(group, "nominal_longitude_deg")
        if not isinstance(longitude, int | float):
            return {"status": "UNKNOWN", "reason": "NO_NOMINAL_LONGITUDE"}
        looks = [
            (name, *geo.gso_look(lat, lon, longitude)) for name, lat, lon in geo.FINLAND_POINTS
        ]
        visible = [(n, e, s) for n, e, s in looks if e > 0]
        best = max(looks, key=lambda x: x[1])
        return {
            "status": "VISIBLE" if visible else "NOT_VISIBLE",
            "nominal_longitude_deg": longitude,
            "elevations_deg": {n: round(e, 2) for n, e, _ in looks},
            "min_slant_range_km": round(min(s for _, _, s in visible), 1) if visible else None,
            "best_point": best[0],
            "basis": "Spherical Earth, GSO radius 42164 km, at the nominal longitude; station-"
            "keeping tolerance ignored.",
        }
    if kind == "NON_GSO_SPACE_STATION":
        incl = norm(group, "orbit_inclination_deg_range")
        perigee = norm(group, "orbit_perigee_km_range")
        apogee = norm(group, "orbit_apogee_km_range")
        if not incl or not perigee:
            return {"status": "UNKNOWN", "reason": "NO_ORBIT_PARAMETERS"}
        reach, slant = False, math.inf
        for latitude in geo.FINLAND_LATITUDE_RANGE:
            ok, distance = geo.ngso_reach(max(incl), max(apogee or perigee), latitude)
            reach = reach or ok
        if reach:
            ok, slant = geo.ngso_reach(max(incl), min(perigee), geo.FINLAND_LATITUDE_RANGE[0])
        return {
            "status": "REACHES_FINLAND_LATITUDES" if reach else "DOES_NOT_REACH",
            "inclination_deg_range": incl,
            "perigee_km_range": perigee,
            "apogee_km_range": apogee,
            "min_slant_range_km": round(slant, 1) if reach and math.isfinite(slant) else None,
            "basis": "Highest inclination and altitude; minimum slant range at the lowest "
            "perigee and 59.7 N (spherical Earth, circular-orbit approximation).",
        }
    lat = norm(group, "earth_station_latitude_deg")
    lon = norm(group, "earth_station_longitude_deg")
    if lat is None or lon is None:
        return {"status": "UNKNOWN", "reason": "NOT_A_SPACE_STATION_OR_NO_LOCATION"}
    distance, _, _ = geo.nearest_finland_point(lat, lon)
    return {"status": "EARTH_STATION", "distance_to_finland_km": round(distance, 1)}


def _pfd_scenario(group: dict[str, Any], geometry: dict[str, Any]) -> dict[str, Any] | None:
    density = norm(group, "max_power_density_dbw_hz")
    gain = norm(group, "beam_max_gain_dbi")
    slant = geometry.get("min_slant_range_km")
    if density is None or gain is None or not slant:
        return None
    return {
        "space_pfd_free_space": {
            "eirp_toward_receiver_dbw": float(density) + float(gain),
            "slant_range_m": float(slant) * 1000,
            "eirp_reference_bandwidth_hz": PFD_REFERENCE_BANDWIDTH_HZ,
            "eirp_basis": "UPPER_BOUND: notified maximum power density (dBW/Hz) + maximum beam "
            "gain, as if the beam peak pointed at Finland",
            "slant_range_basis": geometry["basis"],
        }
    }


def analyse_space(
    records: Sequence[dict[str, Any]],
    refs: References,
    previous_notice_ids: set[str] | None = None,
    *,
    pfd_method: Any = None,
    max_groups_per_notice: int = 15,
) -> dict[str, Any]:
    by_notice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_notice[record["notice_id"]].append(record)
    findings = []
    for notice_id, groups in by_notice.items():
        findings.append(
            _space_finding(
                notice_id, groups, refs, previous_notice_ids, pfd_method, max_groups_per_notice
            )
        )
    findings.sort(key=lambda f: (-f["priority"]["score"], -(f["max_pfd"] or -999)))
    return {"findings": findings}


def _space_finding(
    notice_id: str,
    groups: list[dict[str, Any]],
    refs: References,
    previous_ids: set[str] | None,
    method: Any,
    keep: int,
) -> dict[str, Any]:
    first = groups[0]
    change = space_change(first, previous_ids)
    geometry = _space_geometry(first)
    sections = norm(first, "special_sections") or []
    group_results = []
    station_overlaps = 0
    service_area_fin = False
    terrestrial_sharing = False
    calculations = []
    for group in groups:
        start, end = group["frequency_start_mhz"], group["frequency_end_mhz"]
        freq = _frequency_stage(refs, start, end)
        downlink = norm(group, "direction") == "TRANSMIT"
        areas = norm(group, "service_area_countries") or []
        if "FIN" in areas:
            service_area_fin = True
        shares = downlink and _has_service(freq["m4"], TERRESTRIAL_SERVICES)
        terrestrial_sharing = terrestrial_sharing or shares
        if freq["status"] == "MATCH" and downlink:
            station_overlaps += 1
        result = {
            "group_id": norm(group, "group_id"),
            "beam": norm(group, "beam_name"),
            "direction": norm(group, "direction"),
            "range_mhz": [start, end],
            "classes_services": norm(group, "station_classes_services"),
            "service_area_includes_finland": "FIN" in areas,
            "frequency_status": freq["status"],
            "special_interest_overlaps": [m["label"] for m in freq["stations"][:5]],
            "finnish_terrestrial_service_in_band": shares,
        }
        scenario = _pfd_scenario(group, geometry) if downlink else None
        if scenario and method is not None:
            assessment = method.assess_applicability(scenario)
            if assessment["applicability"] == "APPLICABLE":
                output = method.calculate(scenario)
                output["assumptions"].append(scenario["space_pfd_free_space"]["eirp_basis"])
                output["group_id"] = result["group_id"]
                result["pfd_db_w_m2_hz_upper_bound"] = round(output["numeric_value"], 2)
                calculations.append(output)
        group_results.append(result)
    group_results.sort(
        key=lambda g: (
            g["frequency_status"] != "MATCH",
            g["direction"] != "TRANSMIT",
            -(g.get("pfd_db_w_m2_hz_upper_bound") or -999),
        )
    )
    max_pfd = max((c["numeric_value"] for c in calculations), default=None)
    visible = geometry["status"] in ("VISIBLE", "REACHES_FINLAND_LATITUDES")
    is_api_cr = any(s.startswith(("API/A", "CR/C")) for s in sections)
    is_ap30 = any("AP30" in s for s in sections)
    components = {
        "change_new_or_modified": 1 if change["change_type"] in ("NEW", "MODIFIED") else 0,
        "special_interest_frequency_overlap_downlink": 3 if station_overlaps else 0,
        "service_area_includes_finland": 3 if service_area_fin else 0,
        "visible_from_or_reaches_finland": 2 if visible else 0,
        "finnish_terrestrial_service_in_downlink_band": 1 if terrestrial_sharing else 0,
        "api_a_or_cr_c_special_section": 1 if is_api_cr else 0,
        "ap30_30a_30b": 1 if is_ap30 else 0,
        "pfd_upper_bound_available": 1 if calculations else 0,
    }
    score = sum(components.values())
    if not visible and geometry["status"] in ("NOT_VISIBLE", "DOES_NOT_REACH"):
        status = "SCREENED_OUT_GEOMETRY"
    elif _tier(score, "SPACE") == "HIGH":
        status = "EXPERT_REVIEW_REQUIRED"
    elif geometry["status"] == "UNKNOWN" or not calculations:
        status = "INSUFFICIENT_DATA"
    else:
        status = "SCREENED_LOW_PRIORITY"
    matched = [g for g in group_results if g["frequency_status"] == "MATCH"]
    anomalies = [a for g in groups for a in (norm(g, "power_anomalies") or [])]
    return {
        "domain": "SPACE",
        "notice_id": notice_id,
        "administration": first["administration"],
        "notice_type": norm(first, "notice_type"),
        "satellite_name": norm(first, "satellite_name"),
        "earth_station_name": norm(first, "earth_station_name"),
        "provision": norm(first, "provision"),
        "special_sections": sections,
        "ific_part": norm(first, "ific_part"),
        "change": change,
        "stage_a_frequency": {
            "groups": len(groups),
            "groups_overlapping_special_interest_stations": len(matched),
            "downlink_groups_overlapping_special_interest_stations": station_overlaps,
            "note": "M4 overlap is recorded per group; every frequency lies in some M4 band.",
        },
        "stage_b_service": {
            "status": "MATCH" if terrestrial_sharing or station_overlaps else "NO_MATCH",
            "downlink_in_band_with_finnish_terrestrial_service": terrestrial_sharing,
            "service_area_includes_finland": service_area_fin,
        },
        "stage_c_geometry": geometry,
        "stage_d_readiness": {
            "status": "READY" if calculations else "NOT_READY",
            "method": "SPACE_PFD_FREE_SPACE",
            "groups_with_pfd": len(calculations),
        },
        "data_quality_anomalies": anomalies[:20],
        "data_quality_anomaly_count": len(anomalies),
        "groups": group_results[:keep],
        "calculations": sorted(calculations, key=lambda c: -c["numeric_value"])[:3],
        "max_pfd": max_pfd,
        "max_pfd_unit": "dB(W/m^2) in 1 Hz (upper bound)" if max_pfd is not None else None,
        "priority": {"score": score, "tier": _tier(score, "SPACE"), "components": components},
        "finding_status": status,
        "regulatory_finding": "NOT_EVALUATED: no approved criterion is configured",
        "rule_version": RULE_VERSION,
    }
