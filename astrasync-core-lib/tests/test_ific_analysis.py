"""Finland relevance stages, change rules, geometry and priorities on synthetic records."""

import json
import math
from typing import Any

import pytest
from astrasync_data import geo
from astrasync_data import ific_analysis as A
from astrasync_physics.space_pfd import SpacePfdFreeSpace
from astrasync_physics.terrestrial_p1546 import TerrestrialP1546


def _record(
    table: str, key: str, start: float | None, end: float | None, adm: str, **norm: Any
) -> dict[str, Any]:
    return {
        "source_table_or_sheet": table,
        "source_row_or_key": key,
        "notice_id": norm.pop("notice_id", key),
        "issue_key": "3076",
        "administration": adm,
        "frequency_start_mhz": start,
        "frequency_end_mhz": end,
        "raw_fields": {
            f"norm.{k}": None if v is None else v if isinstance(v, str) else json.dumps(v)
            for k, v in norm.items()
        },
    }


def _refs(stations: list[A.Reference] | None = None) -> A.References:
    m4 = [A.Reference("M4_ALLOCATION", "m4!1", 440, 470, "M4", "PMR", ("FIXED", "MOBILE"))]
    return A.References(A.IntervalIndex(m4), A.IntervalIndex(stations or []))


def _station(centre: float, lat: float = 60.6, lon: float = 27.0) -> A.Reference:
    return A.Reference(
        "SPECIAL_INTEREST_STATION",
        "ws!2:TX",
        centre - 0.0125,
        centre + 0.0125,
        "C",
        "Station 1 TX",
        station={"latitude_deg": lat, "longitude_deg": lon, "antenna_height_agl_m": 20.0},
        is_synthetic=True,
    )


def _notice(
    key: str, intent: str = "ADD", lat: float = 60.70, lon: float = 28.75, **over: Any
) -> dict[str, Any]:
    fields = {
        "role": "NOTICE",
        "intent": intent,
        "assignment_id": f"A{key}",
        "station_class": "FB",
        "is_land_mobile": True,
        "assigned_frequency_mhz": 450.0,
        "bandwidth_khz": 20.0,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "radiated_power_dbw": 20.0,
        "radiated_power_type": "ERP",
        "antenna_height_agl_m": 40.0,
        "targets": [],
        "publications": ["NTFD_RR:1"],
    }
    fields.update(over)
    return _record("fxm_terra", key, 449.99, 450.01, "RUS", **fields)


def test_interval_index_uses_closed_intervals() -> None:
    refs = [
        A.Reference("M4_ALLOCATION", f"r{i}", a, b, "x", "x")
        for i, (a, b) in enumerate([(1, 2), (2, 3), (5, 5), (0, 100)])
    ]
    index = A.IntervalIndex(refs)
    assert {r.key for r in index.overlapping(2, 2)} == {"r0", "r1", "r3"}  # Touching edges count.
    assert {r.key for r in index.overlapping(4, 6)} == {"r2", "r3"}  # A zero-width reference.
    assert {r.key for r in index.overlapping(200, 300)} == set()


def test_change_comes_from_the_intent_and_absence_is_never_withdrawal() -> None:
    recorded = _record(
        "fxm_terra",
        "9",
        449.99,
        450.01,
        "RUS",
        role="RECORDED_CONTEXT",
        radiated_power_dbw=9.9,
        antenna_height_agl_m=40.0,
    )
    modify = _notice("1", "MODIFY", radiated_power_dbw=4.8, targets=[["9", "MODIFY"]])
    change = A.terrestrial_change(modify, {"9": recorded}, None)
    assert change["change_type"] == "MODIFIED"
    assert {"field": "radiated_power_dbw", "before": 9.9, "after": 4.8} in change["field_changes"]
    assert A.terrestrial_change(_notice("2", "SUPPRESS"), {}, None)["change_type"] == "WITHDRAWN"
    # An assignment in the previous issue but not in this one produces no finding at all.
    result = A.analyse_terrestrial([_notice("3")], _refs(), [_notice("4")])
    assert [f["notice_id"] for f in result["findings"]] == ["3"]


def test_terrestrial_stages_and_priority_for_a_border_station() -> None:
    result = A.analyse_terrestrial(
        [_notice("1"), _notice("2", lat=55.75, lon=37.62)],
        _refs([_station(450.0)]),
        p1546_method=TerrestrialP1546(),
    )
    near, far = result["findings"]
    assert near["notice_id"] == "1"
    assert near["stage_a_frequency"]["status"] == "MATCH"
    assert near["stage_b_service"]["finnish_mobile_allocation"] is True
    assert near["stage_c_geography"]["distance_to_finland_km"] < 50
    assert {c["receiver"] for c in near["calculations"]} >= {"Nearest point of Finland"}
    assert near["priority"]["tier"] == "HIGH"
    assert near["finding_status"] == "EXPERT_REVIEW_REQUIRED"
    assert far["priority"]["tier"] != "HIGH"
    assert far["stage_c_geography"]["distance_to_finland_km"] > 500
    # No approved criterion: never more than expert review.
    assert all(f["regulatory_finding"].startswith("NOT_EVALUATED") for f in result["findings"])


def test_missing_power_blocks_the_calculation_instead_of_guessing() -> None:
    result = A.analyse_terrestrial(
        [_notice("1", radiated_power_dbw=None)], _refs(), p1546_method=TerrestrialP1546()
    )
    [finding] = result["findings"]
    assert finding["calculations"] == []
    assert "e.r.p." in finding["stage_d_readiness"]["missing_inputs"]


def test_non_land_mobile_notices_are_outside_the_side_quest() -> None:
    result = A.analyse_terrestrial([_notice("1", is_land_mobile=False)], _refs())
    assert result["findings"] == [] and result["skipped"] == {"not_land_mobile": 1}


def test_gso_geometry_matches_known_look_angles() -> None:
    elevation, slant = geo.gso_look(0.0, 25.0, 25.0)
    assert elevation == pytest.approx(90.0) and slant == pytest.approx(42164 - 6371)
    elevation, _ = geo.gso_look(60.17, 24.94, 25.0)  # Helsinki to a GSO due south.
    assert elevation == pytest.approx(22.0, abs=0.5)
    assert geo.gso_look(69.9, 27.0, 180.0)[0] < 0  # Not visible from Lapland.


def test_ngso_reach_and_finland_geometry() -> None:
    assert geo.ngso_reach(97.0, 500.0, 60.0) == (True, pytest.approx(500.0))
    reach, slant = geo.ngso_reach(30.0, 500.0, 60.0)
    assert reach is False and math.isinf(slant)
    assert geo.in_finland(60.17, 24.94) and not geo.in_finland(
        59.94, 30.31
    )  # Helsinki, St Petersburg.
    assert geo.nearest_finland_point(60.17, 24.94)[0] == 0.0
    assert 20 < geo.nearest_finland_point(59.94, 30.31)[0] < 200


def _group(key: str, **over: Any) -> dict[str, Any]:
    fields = {
        "notice_id": "N1",
        "notice_type": "GSO_SPACE_STATION",
        "satellite_name": "TEST-SAT",
        "nominal_longitude_deg": 25.0,
        "direction": "TRANSMIT",
        "group_id": key,
        "max_power_density_dbw_hz": -60.0,
        "beam_max_gain_dbi": 30.0,
        "service_area_countries": [],
        "special_sections": ["CR/C/1"],
        "submission_occurrence": "F",
    }
    fields.update(over)
    return _record("grp", key, 449.0, 451.0, "XYZ", **fields)


def test_space_finding_aggregates_groups_and_computes_an_upper_bound_pfd() -> None:
    result = A.analyse_space(
        [_group("g1"), _group("g2", direction="RECEIVE")],
        _refs([_station(450.0)]),
        pfd_method=SpacePfdFreeSpace(),
    )
    [finding] = result["findings"]
    assert finding["change"]["change_type"] == "NEW"
    assert finding["stage_c_geometry"]["status"] == "VISIBLE"
    [calc] = finding["calculations"]
    slant_km = finding["stage_c_geometry"]["min_slant_range_km"]
    expected = -60.0 + 30.0 - 10 * math.log10(4 * math.pi * (slant_km * 1000) ** 2)
    assert calc["numeric_value"] == pytest.approx(expected)
    assert any("UPPER_BOUND" in a for a in calc["assumptions"])
    assert finding["priority"]["components"]["special_interest_frequency_overlap_downlink"] == 3


def test_space_change_rules() -> None:
    assert (
        A.space_change(_group("g", internal_external_flag="W"), None)["change_type"] == "WITHDRAWN"
    )
    assert A.space_change(_group("g", target_notice_id="X1"), None)["change_type"] == "MODIFIED"
    assert (
        A.space_change(_group("g", submission_occurrence="R"), None)["change_type"]
        == "INDETERMINATE"
    )


def test_a_gso_not_visible_from_finland_is_screened_out() -> None:
    result = A.analyse_space(
        [_group("g1", nominal_longitude_deg=-150.0)], _refs(), pfd_method=SpacePfdFreeSpace()
    )
    assert result["findings"][0]["finding_status"] == "SCREENED_OUT_GEOMETRY"
