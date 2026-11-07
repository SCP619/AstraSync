"""Tier 1 validation for SPACE_PFD_FREE_SPACE (RF_METHODS_AND_VALIDATION.md section 6).

Reference values were computed separately with 40-digit decimal arithmetic, not with the module:
    PFD = EIRP - 10 log10(4 pi r^2) - A
The inputs are made-up test values, not real filings.
"""

import math
from typing import Any

import pytest
from astrasync_physics.space_pfd import SCENARIO_KEY, SpacePfdFreeSpace

METHOD = SpacePfdFreeSpace()

REFERENCE = [
    # (EIRP dBW, slant range m, additional loss dB, PFD dB(W/m^2))
    (0.0, 1.0, 0.0, -10.9920986402),
    (50.0, 35_786_000.0, 0.0, -112.0663617921),
    (30.0, 1_000.0, 0.0, -40.9920986402),
    (55.0, 1_000_000.0, 3.0, -78.9920986402),
]


def scenario(**block: Any) -> dict[str, Any]:
    return {SCENARIO_KEY: block}


@pytest.mark.parametrize(("eirp", "distance", "loss", "expected"), REFERENCE)
def test_matches_independent_reference_values(
    eirp: float, distance: float, loss: float, expected: float
) -> None:
    result = METHOD.calculate(
        scenario(eirp_toward_receiver_dbw=eirp, slant_range_m=distance, additional_loss_db=loss)
    )
    assert result["numeric_value"] == pytest.approx(expected, abs=1e-9)
    assert result["unit"] == "dB(W/m^2)"
    assert result["metric_kind"] == "PFD"


@pytest.mark.parametrize(("eirp", "distance", "loss", "expected"), REFERENCE)
def test_linear_and_db_forms_agree(
    eirp: float, distance: float, loss: float, expected: float
) -> None:
    result = METHOD.calculate(
        scenario(eirp_toward_receiver_dbw=eirp, slant_range_m=distance, additional_loss_db=loss)
    )
    linear = result["result_trace"]["pfd_w_per_m2"]
    assert 10 * math.log10(linear) == pytest.approx(result["numeric_value"], abs=1e-9)
    # Independent linear form: P / (4 pi r^2), with loss as a power ratio.
    eirp_w = 10 ** (eirp / 10)
    assert linear == pytest.approx(eirp_w / (4 * math.pi * distance**2) / 10 ** (loss / 10))


def test_doubling_distance_lowers_pfd_by_6_02_db() -> None:
    near = METHOD.calculate(scenario(eirp_toward_receiver_dbw=40.0, slant_range_m=2_000_000.0))
    far = METHOD.calculate(scenario(eirp_toward_receiver_dbw=40.0, slant_range_m=4_000_000.0))
    assert far["numeric_value"] - near["numeric_value"] == pytest.approx(-6.0205999133, abs=1e-9)


def test_pfd_falls_monotonically_with_distance() -> None:
    values = [
        METHOD.calculate(scenario(eirp_toward_receiver_dbw=40.0, slant_range_m=d))["numeric_value"]
        for d in (1e3, 1e4, 1e5, 1e6, 1e7)
    ]
    assert values == sorted(values, reverse=True)


def test_missing_inputs_are_insufficient_data_never_zero() -> None:
    assessment = METHOD.assess_applicability(scenario(eirp_toward_receiver_dbw=40.0))
    assert assessment["applicability"] == "INSUFFICIENT_DATA"
    assert assessment["missing_fields"] == [f"{SCENARIO_KEY}.slant_range_m"]
    assert METHOD.assess_applicability({})["missing_fields"] == [
        f"{SCENARIO_KEY}.eirp_toward_receiver_dbw",
        f"{SCENARIO_KEY}.slant_range_m",
    ]
    with pytest.raises(ValueError):
        METHOD.calculate(scenario(eirp_toward_receiver_dbw=40.0))


@pytest.mark.parametrize(
    ("block", "reason"),
    [
        ({"slant_range_m": 0.0}, "NON_POSITIVE_SLANT_RANGE"),
        ({"slant_range_m": -5.0}, "NON_POSITIVE_SLANT_RANGE"),
        ({"additional_loss_db": -1.0}, "NEGATIVE_ADDITIONAL_LOSS"),
        ({"eirp_reference_bandwidth_hz": 0}, "INVALID_REFERENCE_BANDWIDTH"),
        ({"eirp_toward_receiver_dbw": "40"}, "NON_NUMERIC_INPUT"),
        ({"eirp_toward_receiver_dbw": True}, "NON_NUMERIC_INPUT"),
        ({"slant_range_m": float("nan")}, "NON_NUMERIC_INPUT"),
    ],
)
def test_invalid_inputs_are_refused(block: dict[str, Any], reason: str) -> None:
    full = {"eirp_toward_receiver_dbw": 40.0, "slant_range_m": 1e6, **block}
    assessment = METHOD.assess_applicability(scenario(**full))
    assert assessment["applicability"] == "NOT_APPLICABLE"
    assert reason in assessment["reason_codes"]
    with pytest.raises(ValueError):
        METHOD.calculate(scenario(**full))


def test_reference_bandwidth_is_carried_not_rescaled() -> None:
    total = METHOD.calculate(scenario(eirp_toward_receiver_dbw=40.0, slant_range_m=1e6))
    per_4khz = METHOD.calculate(
        scenario(eirp_toward_receiver_dbw=40.0, slant_range_m=1e6, eirp_reference_bandwidth_hz=4e3)
    )
    assert total["reference_bandwidth_hz"] is None
    assert per_4khz["reference_bandwidth_hz"] == 4e3
    assert per_4khz["numeric_value"] == total["numeric_value"]  # No 10 log10(B) adjustment.
    assert any("total channel" in a for a in total["assumptions"])


def test_result_is_reproducible_and_traceable() -> None:
    block = {"eirp_toward_receiver_dbw": 47.5, "slant_range_m": 36_000_000.0}
    first, second = METHOD.calculate(scenario(**block)), METHOD.calculate(scenario(**block))
    assert first["calculation_sha256"] == second["calculation_sha256"]
    assert len(first["implementation_sha"]) == 64
    assert first["inputs"] == {
        **block,
        "additional_loss_db": 0.0,
        "eirp_reference_bandwidth_hz": None,
    }
    assert "formula" in first["result_trace"]


def test_results_satisfy_the_backend_contract() -> None:
    contract = pytest.importorskip("astrasync_api.contract.models")
    good = scenario(eirp_toward_receiver_dbw=50.0, slant_range_m=35_786_000.0)
    contract.MethodAssessment.model_validate(METHOD.assess_applicability(good))
    contract.MethodAssessment.model_validate(METHOD.assess_applicability({}))
    contract.MethodCalculation.model_validate(METHOD.calculate(good))
    interfaces = pytest.importorskip("astrasync_api.contract.interfaces")
    assert isinstance(METHOD, interfaces.RFMethod)
