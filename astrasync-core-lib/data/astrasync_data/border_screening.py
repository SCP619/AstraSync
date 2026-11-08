"""Border and territorial-sea field-strength screening against ECC T/R 25-08 A1.2.3.

Organizer clarifications (docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md): evaluate the field strength
along Finland's land borders and the outer limit of its territorial sea, with ITU-R P.1546-6 at
10 % time, 50 % locations, 10 m receiving height, and compare with the general land-mobile
coordination threshold of T/R 25-08 A1.2.3 (applied above 470 MHz as a challenge extension).

Geometry: ``finland_screening_boundaries.json`` (provenance inside). Lines are resampled every
``spacing_km`` along the great circle between vertices (vertices always kept). For each
transmitter every sample within ``window_km`` of its nearest sample is evaluated, so the maximum
is found over the exposed stretch of border or sea limit, not at one arbitrary point.

The thresholds are read from ``criteria/tr2508_a123.json`` (cited edition, section, approval);
this module holds no limit values.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from . import geo

_HERE = Path(__file__).parent
DEFAULT_SPACING_KM = 5.0
DEFAULT_WINDOW_KM = 150.0
# Results within this many dB below the threshold are POTENTIAL_CONCERN. Team choice, permitted by
# the organizers (concern margins are configurable and documented); not a regulatory value.
DEFAULT_CONCERN_MARGIN_DB = 6.0
SCREENING_VERSION = "border-screening/1.0.0"
FINLAND_ADM = "FIN"


@dataclass(frozen=True)
class Sample:
    kind: str
    label: str
    lat: float
    lon: float
    index: int
    line: int


@cache
def boundaries() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (_HERE / "finland_screening_boundaries.json").read_text(encoding="utf-8")
    )
    return document


@cache
def criterion_set() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(
        (_HERE / "criteria" / "tr2508_a123.json").read_text(encoding="utf-8")
    )
    return document


@cache
def samples(spacing_km: float = DEFAULT_SPACING_KM) -> tuple[Sample, ...]:
    if spacing_km <= 0:
        raise ValueError("spacing_km must be positive")
    out: list[Sample] = []
    for line_number, line in enumerate(boundaries()["lines"]):
        coords = line["coordinates"]
        points = [(coords[0][1], coords[0][0])]
        for (lon1, lat1), (lon2, lat2) in zip(coords, coords[1:], strict=False):
            length = geo.haversine_km(lat1, lon1, lat2, lon2)
            steps = max(1, math.ceil(length / spacing_km))
            for step in range(1, steps + 1):
                points.append(geo.intermediate(lat1, lon1, lat2, lon2, step / steps))
        for lat, lon in points:
            out.append(Sample(line["kind"], line["label"], lat, lon, len(out), line_number))
    return tuple(out)


def candidate_samples(
    lat: float,
    lon: float,
    *,
    spacing_km: float = DEFAULT_SPACING_KM,
    window_km: float = DEFAULT_WINDOW_KM,
) -> list[tuple[float, Sample]]:
    """Samples within ``window_km`` of the nearest one, nearest first, with distances."""
    ranked = sorted(
        ((geo.haversine_km(lat, lon, s.lat, s.lon), s) for s in samples(spacing_km)),
        key=lambda item: item[0],
    )
    nearest = ranked[0][0]
    return [item for item in ranked if item[0] <= nearest + window_km]


def threshold(frequency_mhz: float, bandwidth_khz: float | None) -> dict[str, Any] | None:
    """The applicable threshold with its basis, or None outside every band."""
    cs = criterion_set()
    base = None
    basis = None
    for band in cs["bands"]:
        if band["min_mhz"] <= frequency_mhz <= band["max_mhz"]:
            base, basis = band["threshold_dbuv_m"], "NORMATIVE_T/R_25-08_A1.2.3"
            break
    extension = cs["challenge_extension_above_470_mhz"]
    if base is None and extension["enabled"] and 470.0 < frequency_mhz <= extension["max_mhz"]:
        base, basis = extension["threshold_dbuv_m"], "CHALLENGE_EXTENSION_ABOVE_470_MHZ"
    if base is None:
        return None
    reference_khz = cs["conditions"]["reference_bandwidth_khz"]
    assumptions = []
    if bandwidth_khz is None or bandwidth_khz <= 0:
        correction = 0.0
        assumptions.append(
            "Notified bandwidth unknown: no bandwidth correction (threshold for 25 kHz)."
        )
    elif bandwidth_khz > reference_khz:
        correction = 10 * math.log10(bandwidth_khz / reference_khz)
        assumptions.append(
            f"BC = 10 log10({bandwidth_khz:g} kHz / {reference_khz:g} kHz) = {correction:.2f} dB, "
            "assuming uniform spectral power distribution in the notified bandwidth."
        )
    else:
        correction = 0.0
    return {
        "criterion_set_id": cs["criterion_set_id"],
        "criterion_version": cs["version"],
        "basis": basis,
        "base_threshold_dbuv_m": base,
        "bandwidth_correction_db": round(correction, 4),
        "threshold_dbuv_m": round(base + correction, 4),
        "reference_bandwidth_khz": reference_khz,
        "conditions": cs["conditions"],
        "citation": f"{cs['source']['document']}, {cs['source']['edition']}, "
        f"{cs['source']['section']} ({cs['source']['source_url']})",
        "assumptions": assumptions,
    }


def coordination_summary(coordination: Any) -> dict[str, Any]:
    """Coordination rows ``[adm, status, provision]`` as published; Finland flagged if named."""
    rows = [list(row) for row in coordination or [] if isinstance(row, list | tuple)]
    finland = [row for row in rows if row and str(row[0]).strip().upper() == FINLAND_ADM]
    return {
        "rows": rows,
        "finland_mentioned": bool(finland),
        "finland_rows": finland,
    }


def classify(
    max_field_strength: float | None,
    criterion: dict[str, Any] | None,
    coordination: dict[str, Any],
    *,
    frequency_match: bool,
    concern_margin_db: float = DEFAULT_CONCERN_MARGIN_DB,
) -> dict[str, Any]:
    """Concern class for one notice. Never a statement of interference or non-compliance."""
    if max_field_strength is None:
        label = "FREQUENCY_OVERLAP_ONLY" if frequency_match else "INSUFFICIENT_EVIDENCE"
        return {"classification": label, "margin_db": None, "expert_review": frequency_match}
    if criterion is None:
        return {
            "classification": "INSUFFICIENT_EVIDENCE",
            "margin_db": None,
            "reason": "No applicable criterion for this frequency",
            "expert_review": frequency_match,
        }
    margin = round(max_field_strength - criterion["threshold_dbuv_m"], 2)
    if margin > 0:
        label = (
            "COORDINATION_REVIEW"
            if coordination["finland_mentioned"]
            else "VERIFIED_CRITERION_EXCEEDANCE"
        )
    elif margin > -concern_margin_db:
        label = "POTENTIAL_CONCERN"
    else:
        label = "BELOW_SCREENING_THRESHOLD"
    return {
        "classification": label,
        "margin_db": margin,
        "concern_margin_db": concern_margin_db,
        "expert_review": label != "BELOW_SCREENING_THRESHOLD",
        "meaning": (
            "Screening exceedance of the indicative coordination threshold at the Finnish border "
            "or territorial-sea limit: coordination with Finland is indicated. Not harmful "
            "interference, not non-compliance."
            if margin > 0
            else None
        ),
    }
