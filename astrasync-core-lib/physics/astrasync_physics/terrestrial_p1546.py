"""`TERR_P1546`: field strength by Recommendation ITU-R P.1546-6 (``p1546.py``), as an RF method.

Scenario block ``scenario["terrestrial_p1546"]``:

- ``frequency_mhz`` (30-4000), ``time_percent`` (1-50), ``distance_km`` (<= 1000)
- ``erp_dbw``: e.r.p. toward the receiver in dBW. P.1546 curves are for 1 kW e.r.p.; the result
  is scaled by ``erp_dbw - 30``. An e.i.r.p. must be converted (e.r.p. = e.i.r.p. - 2.15 dB) by
  the caller and the conversion named in ``power_basis``.
- ``tx_height_agl_m`` (ha) and ``effective_height_m`` (heff, Annex 5 section 3). Without terrain
  data heff is unknown; the caller may set ``effective_height_basis`` to
  ``ASSUMED_EQUAL_TO_HA`` to use ha, which is then listed as an assumption.
- ``rx_height_agl_m``, ``rx_area`` (Rural, Suburban, Urban, Dense Urban, Sea), and optionally
  ``rx_clutter_height_m`` (default 10 m for Rural/Suburban/Sea, 15 m Urban, 20 m Dense Urban, as
  suggested in the reference implementation), ``location_percent`` (default 50) and ``zones``:
  a list of ``[length_km, "Land"|"Sea"|"Cold"|"Warm"]`` (default all land).

Validation: the port matches all 54 result logs of the ITU-R WP 3K reference implementation to
5.1e-5 dB (``tests/test_p1546.py``). That validates the implementation against the reference,
not the inputs: e.r.p. toward the receiver, heights and path type come from the notice and from
stated assumptions, and the result is not a regulatory finding until compared with an approved
criterion.
"""

import hashlib
import json
import math
from typing import Any

from . import p1546

METHOD_ID = "TERR_P1546"
METHOD_VERSION = "1.0.0"
METRIC_KIND = "FIELD_STRENGTH"
UNIT = "dB(uV/m)"
SCENARIO_KEY = "terrestrial_p1546"
REQUIRED = (
    "frequency_mhz",
    "time_percent",
    "distance_km",
    "erp_dbw",
    "tx_height_agl_m",
    "rx_height_agl_m",
    "rx_area",
)
DEFAULT_CLUTTER = {"Rural": 10.0, "Suburban": 10.0, "Sea": 10.0, "Urban": 15.0, "Dense Urban": 20.0}
VALIDATION = {
    "status": "VALIDATED_AGAINST_REFERENCE_IMPLEMENTATION",
    "reference": "ITU-R WP 3K reference P1546FieldStrMixed.m v16 (Zenodo 10.5281/zenodo.6206015)",
    "cases": 54,
    "max_abs_deviation_db": 5.1e-5,
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _block(scenario: dict[str, Any]) -> dict[str, Any]:
    block = scenario.get(SCENARIO_KEY)
    return block if isinstance(block, dict) else {}


def _read(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    block = _block(scenario)
    missing = [f"{SCENARIO_KEY}.{key}" for key in REQUIRED if block.get(key) is None]
    reasons: list[str] = []
    inputs: dict[str, Any] = {}
    for key in REQUIRED:
        if key == "rx_area" or block.get(key) is None:
            continue
        number = _number(block[key])
        if number is None:
            reasons.append("NON_NUMERIC_INPUT")
        inputs[key] = number
    area = block.get("rx_area")
    if area is not None and area not in p1546.AREAS:
        reasons.append("UNKNOWN_RX_AREA")
    inputs["rx_area"] = area
    heff = _number(block.get("effective_height_m"))
    basis = block.get("effective_height_basis")
    if heff is None:
        if basis == "ASSUMED_EQUAL_TO_HA":
            heff = inputs.get("tx_height_agl_m")
        elif "tx_height_agl_m" in inputs:
            missing.append(f"{SCENARIO_KEY}.effective_height_m")
    inputs["effective_height_m"] = heff
    inputs["effective_height_basis"] = basis if block.get("effective_height_m") is None else "GIVEN"
    f = inputs.get("frequency_mhz")
    if f is not None and not 30 <= f <= 4000:
        reasons.append("FREQUENCY_OUTSIDE_30_4000_MHZ")
    t = inputs.get("time_percent")
    if t is not None and not 1 <= t <= 50:
        reasons.append("TIME_PERCENT_OUTSIDE_1_50")
    d = inputs.get("distance_km")
    if d is not None and not 0 < d <= 1000:
        reasons.append("DISTANCE_OUTSIDE_0_1000_KM")
    h2 = inputs.get("rx_height_agl_m")
    if h2 is not None and area in p1546.AREAS and h2 < (3 if area == "Sea" else 1):
        reasons.append("RX_HEIGHT_BELOW_RECOMMENDATION_MINIMUM")
    ha = inputs.get("tx_height_agl_m")
    if ha is not None and ha <= 0:
        reasons.append("NON_POSITIVE_TX_HEIGHT")
    q = _number(block.get("location_percent", 50.0))
    if q is None or not 1 <= q <= 99:
        reasons.append("LOCATION_PERCENT_OUTSIDE_1_99")
    inputs["location_percent"] = q
    clutter = block.get("rx_clutter_height_m")
    inputs["rx_clutter_height_m"] = (
        _number(clutter) if clutter is not None else DEFAULT_CLUTTER.get(str(area))
    )
    inputs["rx_clutter_height_basis"] = (
        "GIVEN" if clutter is not None else "REFERENCE_TYPICAL_VALUE"
    )
    zones = block.get("zones")
    if zones is None:
        inputs["zones"] = None if d is None else [[d, "Land"]]
        inputs["zones_basis"] = "ASSUMED_ALL_LAND"
    else:
        valid = (
            isinstance(zones, list)
            and zones
            and all(
                isinstance(z, list | tuple)
                and len(z) == 2
                and _number(z[0]) is not None
                and z[1] in p1546.ZONES
                for z in zones
            )
        )
        if not valid:
            reasons.append("INVALID_PATH_ZONES")
        elif d is not None and abs(sum(float(z[0]) for z in zones) - d) > 1e-6:
            reasons.append("ZONES_DO_NOT_SUM_TO_DISTANCE")
        inputs["zones"] = [[float(z[0]), z[1]] for z in zones] if valid else None
        inputs["zones_basis"] = "GIVEN"
    inputs["power_basis"] = block.get("power_basis")
    return inputs, sorted(set(missing)), sorted(set(reasons))


class TerrestrialP1546:
    """``RFMethod`` plugin for the backend analysis runner."""

    method_id = METHOD_ID
    method_version = METHOD_VERSION

    def assess_applicability(self, scenario: dict[str, Any]) -> dict[str, Any]:
        _, missing, reasons = _read(scenario)
        applicability = (
            "INSUFFICIENT_DATA" if missing else "NOT_APPLICABLE" if reasons else "APPLICABLE"
        )
        return {
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "applicability": applicability,
            "reason_codes": (["MISSING_REQUIRED_INPUT"] if missing else []) + reasons,
            "missing_fields": missing,
            "metric_kind": METRIC_KIND,
        }

    def calculate(self, scenario: dict[str, Any]) -> dict[str, Any]:
        inputs, missing, reasons = _read(scenario)
        if missing or reasons:
            raise ValueError(f"Not applicable: {missing + reasons}")
        zones = inputs["zones"]
        result = p1546.field_strength(
            inputs["frequency_mhz"],
            inputs["time_percent"],
            inputs["effective_height_m"],
            inputs["rx_height_agl_m"],
            inputs["rx_clutter_height_m"],
            inputs["rx_area"],
            [z[0] for z in zones],
            [z[1] for z in zones],
            0,
            q_percent=inputs["location_percent"],
            ptx_kw=10 ** ((inputs["erp_dbw"] - 30) / 10),
            ha_m=inputs["tx_height_agl_m"],
        )
        assumptions = [
            "No terrain database: terrain clearance angle, tropospheric scatter and terminal "
            "terrain heights are not applied (P.1546-6 Annex 5 steps 12, 13 skipped).",
            "Field strength exceeded for the stated percentage of time and locations; not a "
            "worst case.",
            "e.r.p. is taken as the value toward the receiver; no antenna pattern is applied "
            "unless the scenario's e.r.p. already includes it.",
        ]
        if inputs["effective_height_basis"] == "ASSUMED_EQUAL_TO_HA":
            assumptions.append("Effective height heff assumed equal to antenna height ha.")
        if inputs["zones_basis"] == "ASSUMED_ALL_LAND":
            assumptions.append("The whole path is assumed to be land.")
        if inputs["rx_clutter_height_basis"] == "REFERENCE_TYPICAL_VALUE":
            assumptions.append(
                f"Receiver clutter height {inputs['rx_clutter_height_m']} m: the reference "
                f"implementation's typical value for {inputs['rx_area']}."
            )
        if inputs["power_basis"]:
            assumptions.append(f"Power basis: {inputs['power_basis']}.")
        payload = {
            "method": METHOD_ID,
            "version": METHOD_VERSION,
            "inputs": inputs,
            "value": result.field_strength_dbuv_m,
        }
        return {
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "metric_kind": METRIC_KIND,
            "numeric_value": result.field_strength_dbuv_m,
            "unit": UNIT,
            "reference_bandwidth_hz": None,
            "time_percentage": inputs["time_percent"],
            "location_percentage": inputs["location_percent"],
            "inputs": inputs,
            "assumptions": assumptions,
            "diagnostics": {"role": "ENGINEERING", "validation": VALIDATION},
            "result_trace": {
                **result.trace,
                "basic_transmission_loss_db": result.basic_transmission_loss_db,
                "standard": "ITU-R P.1546-6",
            },
            "implementation_sha": p1546.IMPLEMENTATION_SHA,
            "calculation_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest(),
        }
