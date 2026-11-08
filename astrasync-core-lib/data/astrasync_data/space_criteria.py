"""Space PFD screening against ITU RR Article 21, Table 21-4 (No. 21.16), Edition of 2024.

The limit values live in ``criteria/rr_art21_table21_4.json`` (transcribed by
``tools/build_rr_table21_4.py``, with citations); this module holds no limit values.

For one downlink group the assessment:

1. maps the IFIC class-of-station codes to services (Preface to the BR IFIC, Table 3);
2. selects the Table 21-4 entries whose band overlaps the group's frequency range, whose service
   matches, and whose orbit condition (GSO, NGSO, highly-inclined orbit) is established from the
   notice; entries with an unresolved condition are never applied (``excluded`` in the JSON);
3. builds the angle-of-arrival profile seen from Finland: GSO over the Finland grid
   (``geo.finland_grid``), NGSO over 0-90 degrees at the lowest notified perigee (circular orbit);
4. computes the free-space PFD upper bound in each limit's reference bandwidth,
   ``pfd = p + g - 10 log10(4 pi d^2) + 10 log10(B)``, with ``p`` the notified maximum power
   density (dBW/Hz), ``g`` the maximum beam gain (worst case: the beam peak toward Finland,
   organizer clarification C9) and ``B = min(reference bandwidth, group bandwidth)``;
5. takes the margin ``max over the profile of (pfd(delta) - limit(delta))``.

Because the PFD is an upper bound, a negative margin shows the notified maxima cannot exceed the
limit anywhere in Finland; a positive margin is a worst-case exceedance that needs the real
antenna pattern and pointing before any conclusion. Where a limit depends on an unknown
parameter (X, Y), the least strict value is used, so only an exceedance is conclusive.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

from . import geo

_HERE = Path(__file__).parent
ASSESSMENT_VERSION = "rr-table21-4-screening/1.0.0"
DEFAULT_CONCERN_MARGIN_DB = 6.0
NGSO_STEP_DEG = 0.5

ORDER = (
    "WORST_CASE_EXCEEDANCE",
    "POTENTIAL_CONCERN",
    "INCONCLUSIVE_UNKNOWN_PARAMETER",
    "BELOW_SCREENING_THRESHOLD",
    "INSUFFICIENT_EVIDENCE",
    "NO_APPLICABLE_CRITERION",
)


@cache
def registry() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (_HERE / "criteria" / "rr_art21_table21_4.json").read_text(encoding="utf-8")
    )
    return document


def services(classes_services: list[str] | None) -> set[str]:
    """Services of the group's ``stn_cls/nat_srv`` pairs; unknown classes contribute nothing."""
    mapping = registry()["class_of_station_services"]
    return {
        mapping[str(item).split("/")[0]]
        for item in classes_services or []
        if str(item).split("/")[0] in mapping
    }


def orbit_category(
    notice_type: str | None,
    inclination_range: list[float] | None,
    apogee_range: list[float] | None,
) -> str:
    if notice_type == "GSO_SPACE_STATION":
        return "GSO"
    if notice_type != "NON_GSO_SPACE_STATION":
        return "NOT_A_SPACE_STATION"
    if not inclination_range or not apogee_range:
        return "NGSO_UNKNOWN"
    hio = registry()["highly_inclined_orbit"]
    low, high = hio["inclination_deg"]
    inclined = [low <= i <= high for i in inclination_range]
    high_apogee = [a > hio["apogee_km_greater_than"] for a in apogee_range]
    if all(inclined) and all(high_apogee):
        return "NGSO_HIO"
    if not any(inclined) or not any(high_apogee):
        return "NGSO_NOT_HIO"
    return "NGSO_UNKNOWN"  # Mixed orbit planes: the HIO condition cannot be decided.


def _orbit_matches(required: str, orbit: str) -> bool | None:
    """True, False, or None when the notice does not establish the condition."""
    if required == "ANY":
        return orbit != "NOT_A_SPACE_STATION"
    if required == "GSO":
        return orbit == "GSO"
    if required == "NGSO":
        return orbit.startswith("NGSO")
    if orbit == "NGSO_UNKNOWN":
        return None if required in ("NGSO_HIO", "NGSO_NOT_HIO", "ANY_NOT_HIO") else False
    if required == "NGSO_HIO":
        return orbit == "NGSO_HIO"
    if required == "NGSO_NOT_HIO":
        return orbit == "NGSO_NOT_HIO"
    if required == "ANY_NOT_HIO":
        return orbit in ("GSO", "NGSO_NOT_HIO")
    return False


def select_entries(
    start_mhz: float, end_mhz: float, group_services: set[str], orbit: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Applicable entries (with the overlapping band) and reasons for entries left out."""
    selected, unresolved = [], []
    for entry in registry()["entries"]:
        bands = [b for b in entry["bands"] if b["min_mhz"] < end_mhz and start_mhz < b["max_mhz"]]
        if not bands or not group_services & set(entry["services"]):
            continue
        match = _orbit_matches(entry["orbit"], orbit)
        if match is None:
            unresolved.append(
                f"{entry['entry_id']}: orbit condition {entry['orbit']} not established"
            )
            continue
        if match:
            selected.append({**entry, "matched_bands": bands})
    return selected, unresolved


def limit_db(limit: dict[str, Any], delta_deg: float) -> float:
    """Piecewise-linear limit at angle of arrival ``delta_deg`` (0-90 degrees)."""
    if not 0 <= delta_deg <= 90:
        raise ValueError("The angle of arrival must be within 0-90 degrees")
    for segment in limit["segments"]:
        if segment["from_deg"] <= delta_deg <= segment["to_deg"]:
            return float(
                segment["base_db"] + segment["slope_db_per_deg"] * (delta_deg - segment["ref_deg"])
            )
    raise ValueError("No segment covers this angle")


def ngso_slant_range_km(altitude_km: float, elevation_deg: float) -> float:
    """Slant range to a satellite at ``altitude_km`` seen at ``elevation_deg`` (spherical Earth)."""
    r = geo.EARTH_RADIUS_KM
    e = math.radians(elevation_deg)
    return math.sqrt((r + altitude_km) ** 2 - (r * math.cos(e)) ** 2) - r * math.sin(e)


def ngso_max_elevation_deg(inclination_deg: float, altitude_km: float) -> float | None:
    """Highest elevation a circular orbit can reach over Finland (lowest Finnish latitude), or
    None if it never rises above the horizon there (spherical Earth)."""
    folded = min(inclination_deg, 180 - inclination_deg)
    gap = math.radians(max(0.0, geo.FINLAND_LATITUDE_RANGE[0] - folded))
    ratio = geo.EARTH_RADIUS_KM / (geo.EARTH_RADIUS_KM + altitude_km)
    if math.cos(gap) <= ratio:
        return None
    if gap == 0:
        return 90.0
    return math.degrees(math.atan2(math.cos(gap) - ratio, math.sin(gap)))


def profile(
    orbit: str,
    nominal_longitude_deg: float | None,
    perigee_range: list[float] | None,
    inclination_range: list[float] | None = None,
) -> tuple[list[tuple[float, float, dict[str, Any]]], str | None]:
    """(angle of arrival, slant range km, where) seen from Finland, or a reason it is unknown."""
    if orbit == "GSO":
        if nominal_longitude_deg is None:
            return [], "no nominal longitude"
        points = []
        for lat, lon in geo.finland_grid():
            elevation, slant = geo.gso_look(lat, lon, nominal_longitude_deg)
            if elevation > 0:
                points.append((elevation, slant, {"lat": lat, "lon": lon}))
        return points, None if points else "not visible from Finland"
    if orbit.startswith("NGSO"):
        if not perigee_range:
            return [], "no perigee"
        if not inclination_range:
            return [], "no inclination"
        altitude = min(perigee_range)
        top = ngso_max_elevation_deg(max(inclination_range), altitude)
        if top is None:
            return [], "not visible from Finland"
        steps = int(top / NGSO_STEP_DEG)
        angles = [k * NGSO_STEP_DEG for k in range(steps + 1)]
        if angles[-1] < top:
            angles.append(top)
        return [
            (a, ngso_slant_range_km(altitude, a), {"max_elevation_over_finland_deg": round(top, 2)})
            for a in angles
        ], None
    return [], "not a space station"


def _spreading_db(slant_km: float) -> float:
    return 10 * math.log10(4 * math.pi * (slant_km * 1000) ** 2)


def assess_limit(
    limit: dict[str, Any],
    points: list[tuple[float, float, dict[str, Any]]],
    density_dbw_hz: float,
    gain_dbi: float,
    group_bandwidth_hz: float | None,
) -> dict[str, Any]:
    reference = float(limit["reference_bandwidth_hz"])
    bandwidth = min(reference, group_bandwidth_hz) if group_bandwidth_hz else reference
    bandwidth_db = 10 * math.log10(bandwidth)
    worst: dict[str, Any] | None = None
    for delta, slant, where in points:
        pfd = density_dbw_hz + gain_dbi - _spreading_db(slant) + bandwidth_db
        value = limit_db(limit, min(delta, 90.0))
        margin = pfd - value
        if worst is None or margin > worst["margin_db"]:
            worst = {
                "margin_db": margin,
                "pfd_db_w_m2": pfd,
                "limit_db_w_m2": value,
                "angle_of_arrival_deg": delta,
                "slant_range_km": slant,
                **({"location": where} if where else {}),
            }
    assert worst is not None  # noqa: S101 - callers pass a non-empty profile
    return {
        "reference_bandwidth_hz": reference,
        "bandwidth_used_hz": bandwidth,
        "bandwidth_basis": (
            "reference bandwidth (group bandwidth unknown or wider)"
            if bandwidth == reference
            else "group bandwidth narrower than the reference bandwidth"
        ),
        **{k: round(v, 3) if isinstance(v, float) else v for k, v in worst.items()},
    }


def classify(margin_db: float, parameter: dict[str, Any] | None, concern_db: float) -> str:
    if margin_db > 0:
        return "WORST_CASE_EXCEEDANCE"
    if parameter is not None:
        return "INCONCLUSIVE_UNKNOWN_PARAMETER"
    if margin_db > -concern_db:
        return "POTENTIAL_CONCERN"
    return "BELOW_SCREENING_THRESHOLD"


def assess_group(
    *,
    start_mhz: float | None,
    end_mhz: float | None,
    direction: str | None,
    classes_services: list[str] | None,
    notice_type: str | None,
    nominal_longitude_deg: float | None,
    inclination_range: list[float] | None,
    apogee_range: list[float] | None,
    perigee_range: list[float] | None,
    density_dbw_hz: float | None,
    gain_dbi: float | None,
    group_bandwidth_khz: float | None,
    concern_db: float = DEFAULT_CONCERN_MARGIN_DB,
) -> dict[str, Any]:
    """Table 21-4 screening of one group; never a finding of non-compliance."""
    base: dict[str, Any] = {"assessment_version": ASSESSMENT_VERSION}
    if direction != "TRANSMIT":
        return {**base, "classification": "NO_APPLICABLE_CRITERION", "reason": "not a downlink"}
    if start_mhz is None or end_mhz is None:
        return {**base, "classification": "INSUFFICIENT_EVIDENCE", "reason": "no frequency"}
    group_services = services(classes_services)
    orbit = orbit_category(notice_type, inclination_range, apogee_range)
    entries, unresolved = select_entries(start_mhz, end_mhz, group_services, orbit)
    base.update(
        {
            "services": sorted(group_services),
            "orbit_category": orbit,
            "unresolved_entries": unresolved,
        }
    )
    if not entries:
        return {
            **base,
            "classification": "INSUFFICIENT_EVIDENCE" if unresolved else "NO_APPLICABLE_CRITERION",
            "reason": "applicability not established"
            if unresolved
            else "no Table 21-4 entry for this band, service and orbit",
        }
    if density_dbw_hz is None or gain_dbi is None:
        missing = [
            n for n, v in (("power density", density_dbw_hz), ("beam gain", gain_dbi)) if v is None
        ]
        return {
            **base,
            "classification": "INSUFFICIENT_EVIDENCE",
            "reason": "missing " + ", ".join(missing),
            "entries": [e["entry_id"] for e in entries],
        }
    points, why = profile(orbit, nominal_longitude_deg, perigee_range, inclination_range)
    if not points:
        return {
            **base,
            "classification": "INSUFFICIENT_EVIDENCE"
            if why != "not visible from Finland"
            else "NO_APPLICABLE_CRITERION",
            "reason": why,
            "entries": [e["entry_id"] for e in entries],
        }
    bandwidth_hz = group_bandwidth_khz * 1e3 if group_bandwidth_khz else None
    checks = []
    for entry in entries:
        for limit in entry["limits"]:
            result = assess_limit(limit, points, density_dbw_hz, gain_dbi, bandwidth_hz)
            parameter = entry.get("parameter")
            checks.append(
                {
                    "entry_id": entry["entry_id"],
                    "bands": [b["label"] for b in entry["matched_bands"]],
                    "orbit_condition": entry["orbit"],
                    "printed_page": entry["printed_page"],
                    "footnotes": entry["footnotes"],
                    "parameter": parameter,
                    **result,
                    "classification": classify(result["margin_db"], parameter, concern_db),
                }
            )
    worst = min(checks, key=lambda c: (ORDER.index(c["classification"]), -c["margin_db"]))
    return {
        **base,
        "classification": worst["classification"],
        "margin_db": worst["margin_db"],
        "worst_check": worst,
        "checks": checks,
        "concern_margin_db": concern_db,
    }


def citation() -> str:
    source = registry()["source"]
    return f"{source['document']}, {source['article']} ({source['source_url']})"
