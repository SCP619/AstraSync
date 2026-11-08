"""`TERR_P1546` method plugin: applicability, refusals and provenance."""

import math

import pytest
from astrasync_physics import p1546
from astrasync_physics.terrestrial_p1546 import TerrestrialP1546

BLOCK = {
    "frequency_mhz": 450.0,
    "time_percent": 10.0,
    "distance_km": 30.0,
    "erp_dbw": 20.0,
    "tx_height_agl_m": 40.0,
    "effective_height_basis": "ASSUMED_EQUAL_TO_HA",
    "rx_height_agl_m": 10.0,
    "rx_area": "Rural",
}


def test_the_result_scales_the_1_kw_curves_by_the_erp() -> None:
    result = TerrestrialP1546().calculate({"terrestrial_p1546": BLOCK})
    one_kw = p1546.field_strength(
        450.0, 10.0, 40.0, 10.0, 10.0, "Rural", [30.0], ["Land"], 0, ha_m=40.0
    )
    assert result["numeric_value"] == pytest.approx(one_kw.field_strength_dbuv_m - 10.0)
    assert result["unit"] == "dB(uV/m)" and result["metric_kind"] == "FIELD_STRENGTH"
    assert result["implementation_sha"] == p1546.IMPLEMENTATION_SHA
    assert any("heff assumed equal" in a for a in result["assumptions"])
    assert result["diagnostics"]["validation"]["cases"] == 54


def test_missing_and_out_of_range_inputs_are_refused() -> None:
    method = TerrestrialP1546()
    no_heff = {k: v for k, v in BLOCK.items() if k != "effective_height_basis"}
    assessed = method.assess_applicability({"terrestrial_p1546": no_heff})
    assert assessed["applicability"] == "INSUFFICIENT_DATA"
    assert "terrestrial_p1546.effective_height_m" in assessed["missing_fields"]
    for key, value, code in (
        ("frequency_mhz", 6000.0, "FREQUENCY_OUTSIDE_30_4000_MHZ"),
        ("time_percent", 0.5, "TIME_PERCENT_OUTSIDE_1_50"),
        ("distance_km", 1500.0, "DISTANCE_OUTSIDE_0_1000_KM"),
        ("rx_area", "Moon", "UNKNOWN_RX_AREA"),
    ):
        assessed = method.assess_applicability({"terrestrial_p1546": {**BLOCK, key: value}})
        assert assessed["applicability"] == "NOT_APPLICABLE" and code in assessed["reason_codes"]
    with pytest.raises(ValueError):
        method.calculate({"terrestrial_p1546": {**BLOCK, "zones": [[10.0, "Land"]]}})


def test_mixed_land_sea_paths_follow_the_given_zones() -> None:
    method = TerrestrialP1546()
    land = method.calculate({"terrestrial_p1546": BLOCK})["numeric_value"]
    sea = method.calculate(
        {"terrestrial_p1546": {**BLOCK, "zones": [[10.0, "Land"], [20.0, "Sea"]]}}
    )["numeric_value"]
    assert math.isfinite(sea) and sea > land  # Propagation over sea is stronger.
