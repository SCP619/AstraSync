"""`SPACE_PFD_FREE_SPACE`: idealised single-emitter power flux density (screening only).

RF_METHODS_AND_VALIDATION.md section 2:

    PFD [dB(W/m^2)] = EIRP_toward_receiver [dBW] - 10 log10(4 pi r^2) - A_additional [dB]

with r the slant range in metres. This is the inverse-square law (the free-space context of
ITU-R P.525). It is a screening estimate, not a regulatory finding, and it applies no limit.

What it refuses to do:
- Use a satellite's altitude as the slant range, or boresight EIRP as the EIRP toward the
  receiver. The scenario must state both as such; this method cannot check geometry or patterns.
- Rescale to another bandwidth. The result is in the EIRP's own reference bandwidth, or for the
  total channel when no reference bandwidth is given. Subtracting 10 log10(B) would assume a flat
  spectral density that is not established.
- Treat a missing input as zero. Additional loss defaults to 0 dB only because the idealised
  free-space case is defined that way; a negative loss (a gain) is refused.
"""

import hashlib
import json
import math
from pathlib import Path
from typing import Any

METHOD_ID = "SPACE_PFD_FREE_SPACE"
METHOD_VERSION = "1.0.0"
METRIC_KIND = "PFD"
UNIT = "dB(W/m^2)"
# Scenario keys this method reads, under scenario["space_pfd_free_space"].
SCENARIO_KEY = "space_pfd_free_space"
REQUIRED = ("eirp_toward_receiver_dbw", "slant_range_m")
IMPLEMENTATION_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
FOUR_PI = 4.0 * math.pi


def spreading_loss_db(slant_range_m: float) -> float:
    """10 log10(4 pi r^2), the spreading term in dB(m^2)."""
    return 10.0 * math.log10(FOUR_PI * slant_range_m**2)


def free_space_pfd_db(
    eirp_dbw: float, slant_range_m: float, additional_loss_db: float = 0.0
) -> float:
    return eirp_dbw - spreading_loss_db(slant_range_m) - additional_loss_db


class SpacePfdFreeSpace:
    """``RFMethod`` plugin for the backend analysis runner."""

    method_id = METHOD_ID
    method_version = METHOD_VERSION

    def assess_applicability(self, scenario: dict[str, Any]) -> dict[str, Any]:
        inputs, missing, reasons = _read_inputs(scenario)
        if missing:
            applicability = "INSUFFICIENT_DATA"
        elif reasons:
            applicability = "NOT_APPLICABLE"
        else:
            applicability = "APPLICABLE"
        return {
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "applicability": applicability,
            "reason_codes": (["MISSING_REQUIRED_INPUT"] if missing else []) + reasons,
            "missing_fields": missing,
            "metric_kind": METRIC_KIND,
        }

    def calculate(self, scenario: dict[str, Any]) -> dict[str, Any]:
        inputs, missing, reasons = _read_inputs(scenario)
        if missing or reasons:
            raise ValueError(f"Not applicable: {missing + reasons}")
        eirp = inputs["eirp_toward_receiver_dbw"]
        distance = inputs["slant_range_m"]
        loss = inputs["additional_loss_db"]
        spreading = spreading_loss_db(distance)
        value = eirp - spreading - loss
        if not math.isfinite(value):
            raise ValueError("Result is not finite")
        trace = {
            "formula": "PFD = EIRP_toward_receiver - 10*log10(4*pi*r^2) - A_additional",
            "spreading_loss_db_m2": spreading,
            "additional_loss_db": loss,
            "pfd_w_per_m2": 10 ** (eirp / 10) / (FOUR_PI * distance**2) / 10 ** (loss / 10),
        }
        assumptions = [
            "Idealised free space: inverse-square spreading only.",
            "The scenario states the EIRP toward this receive point and the slant range to it; "
            "neither is derived here.",
            "Single emitter; no aggregation and no time variation.",
        ]
        if inputs["eirp_reference_bandwidth_hz"] is None:
            assumptions.append("EIRP is for the total channel; no reference bandwidth was given.")
        if inputs["additional_loss_db"] == 0.0 and "additional_loss_db" not in _block(scenario):
            assumptions.append("No additional propagation loss (A_additional = 0 dB).")
        payload = {"method": METHOD_ID, "version": METHOD_VERSION, "inputs": inputs, "value": value}
        return {
            "method_id": METHOD_ID,
            "method_version": METHOD_VERSION,
            "metric_kind": METRIC_KIND,
            "numeric_value": value,
            "unit": UNIT,
            "reference_bandwidth_hz": inputs["eirp_reference_bandwidth_hz"],
            "time_percentage": None,
            "location_percentage": None,
            "inputs": inputs,
            "assumptions": assumptions,
            "diagnostics": {"role": "SCREENING"},
            "result_trace": trace,
            "implementation_sha": IMPLEMENTATION_SHA,
            "calculation_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest(),
        }


def _block(scenario: dict[str, Any]) -> dict[str, Any]:
    block = scenario.get(SCENARIO_KEY)
    return block if isinstance(block, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _read_inputs(scenario: dict[str, Any]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Typed inputs, missing field names and refusal reasons. Nothing missing becomes zero."""
    block = _block(scenario)
    missing: list[str] = []
    reasons: list[str] = []
    inputs: dict[str, Any] = {}
    for key in REQUIRED:
        if block.get(key) is None:
            missing.append(f"{SCENARIO_KEY}.{key}")
            continue
        number = _number(block[key])
        if number is None:
            reasons.append("NON_NUMERIC_INPUT")
        inputs[key] = number
    distance = inputs.get("slant_range_m")
    if distance is not None and distance <= 0:
        reasons.append("NON_POSITIVE_SLANT_RANGE")

    loss = block.get("additional_loss_db", 0.0)
    loss_number = _number(loss)
    if loss_number is None:
        reasons.append("NON_NUMERIC_INPUT")
    elif loss_number < 0:
        reasons.append("NEGATIVE_ADDITIONAL_LOSS")
    inputs["additional_loss_db"] = loss_number

    bandwidth = block.get("eirp_reference_bandwidth_hz")
    if bandwidth is not None:
        bandwidth_number = _number(bandwidth)
        if bandwidth_number is None or bandwidth_number <= 0:
            reasons.append("INVALID_REFERENCE_BANDWIDTH")
        inputs["eirp_reference_bandwidth_hz"] = bandwidth_number
    else:
        inputs["eirp_reference_bandwidth_hz"] = None
    return inputs, missing, sorted(set(reasons))
