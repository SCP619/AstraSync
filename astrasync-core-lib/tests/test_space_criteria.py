"""ITU RR Article 21 Table 21-4 (Edition of 2024, Rev.WRC-23) screening.

Expected limits are read from the printed table (pages 287-291): each case gives the entry, the
angle of arrival and the value the table's formula yields there. Group inputs are made up.
"""

import math

import pytest
from astrasync_data import geo
from astrasync_data import space_criteria as S


def entry(entry_id: str) -> dict:
    return next(e for e in S.registry()["entries"] if e["entry_id"] == entry_id)


@pytest.mark.parametrize(
    ("entry_id", "delta", "expected", "reference_hz"),
    [
        # 3 400-4 200 MHz FSS (GSO): -152 / -152 + 0.5(delta - 5) / -142 dB(W/m2) in 4 kHz.
        ("T21-4-04", 0.0, -152.0, 4e3),
        ("T21-4-04", 5.0, -152.0, 4e3),
        ("T21-4-04", 15.0, -147.0, 4e3),
        ("T21-4-04", 25.0, -142.0, 4e3),
        ("T21-4-04", 60.0, -142.0, 4e3),
        # 1 670-1 700 MHz EESS / MetSat: -133 in 1.5 MHz at every angle.
        ("T21-4-01", 3.0, -133.0, 1.5e6),
        ("T21-4-01", 70.0, -133.0, 1.5e6),
        # 2 500-2 690 MHz FSS: -136 + 11/20 (delta - 5) in 1 MHz.
        ("T21-4-03a", 15.0, -130.5, 1e6),
        # 10.7-11.7 GHz FSS NGSO not HIO (21.16.18): -126 + 0.5(delta - 5) in 1 MHz.
        ("T21-4-12", 25.0, -116.0, 1e6),
        # 10.7-12.5 GHz FSS NGSO HIO (21.16.17): -129 + 0.75(delta - 5) in 1 MHz.
        ("T21-4-13", 15.0, -121.5, 1e6),
        ("T21-4-13", 40.0, -114.0, 1e6),
        # 13.4-13.65 GHz Region 1 FSS GSO: four segments in 4 kHz.
        ("T21-4-15", 10.0, -155.0, 4e3),
        ("T21-4-15", 50.0, -149.0, 4e3),
        ("T21-4-15", 82.0, -150.0, 4e3),
        ("T21-4-15", 87.0, -151.0, 4e3),
        # 37.5-40 GHz FSS/MSS GSO: -127 / -127 + 4/3 (delta - 5) / -107 + 0.4 (delta - 20) / -105.
        ("T21-4-22", 11.0, -119.0, 1e6),
        ("T21-4-22", 22.5, -106.0, 1e6),
        ("T21-4-22", 30.0, -105.0, 1e6),
        # 40.5-42 GHz FSS/BSS GSO: -120 + (delta - 5) for 5-15, -110 + 0.5 (delta - 15) for 15-25.
        ("T21-4-24", 10.0, -115.0, 1e6),
        ("T21-4-24", 20.0, -107.5, 1e6),
        # 5 150-5 216 MHz FSS: -164 in 4 kHz.
        ("T21-4-07", 45.0, -164.0, 4e3),
    ],
)
def test_limits_match_the_printed_table(
    entry_id: str, delta: float, expected: float, reference_hz: float
) -> None:
    limit = entry(entry_id)["limits"][0]
    assert S.limit_db(limit, delta) == pytest.approx(expected)
    assert limit["reference_bandwidth_hz"] == reference_hz


def test_6825_7075_mhz_carries_both_the_4_khz_and_1_mhz_limits() -> None:
    limits = entry("T21-4-09")["limits"]
    assert [lim["reference_bandwidth_hz"] for lim in limits] == [4e3, 1e6]
    assert S.limit_db(limits[0], 25) == -144.0
    assert S.limit_db(limits[1], 25) == -124.0


def test_every_piecewise_limit_is_continuous_and_covers_0_to_90() -> None:
    for e in S.registry()["entries"]:
        for limit in e["limits"]:
            segments = limit["segments"]
            assert segments[0]["from_deg"] == 0 and segments[-1]["to_deg"] == 90
            for a, b in zip(segments, segments[1:], strict=False):
                assert a["to_deg"] == b["from_deg"]
                assert S.limit_db(limit, a["to_deg"]) == pytest.approx(
                    b["base_db"] + b["slope_db_per_deg"] * (b["from_deg"] - b["ref_deg"])
                )


def test_angles_outside_0_90_are_refused() -> None:
    with pytest.raises(ValueError):
        S.limit_db(entry("T21-4-04")["limits"][0], 91)


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        (["EC/CP"], {"FIXED_SATELLITE"}),
        (["ER/OT", "EK/OT", "ET/CV"], {"SPACE_OPERATION"}),
        (["EH/CO"], {"SPACE_RESEARCH"}),
        (["EW/CV"], {"EARTH_EXPLORATION_SATELLITE"}),
        (["EN/CP", "E3/CV"], set()),  # RNSS has no entry; EESS (active) is excluded.
    ],
)
def test_classes_of_station_map_to_services(codes: list[str], expected: set[str]) -> None:
    assert S.services(codes) == expected


@pytest.mark.parametrize(
    ("notice_type", "incl", "apogee", "expected"),
    [
        ("GSO_SPACE_STATION", None, None, "GSO"),
        ("NON_GSO_SPACE_STATION", [53.0, 53.0], [550.0, 550.0], "NGSO_NOT_HIO"),
        ("NON_GSO_SPACE_STATION", [63.4], [39000.0], "NGSO_HIO"),
        ("NON_GSO_SPACE_STATION", [63.4, 0.0], [39000.0, 39000.0], "NGSO_UNKNOWN"),
        ("NON_GSO_SPACE_STATION", None, None, "NGSO_UNKNOWN"),
    ],
)
def test_orbit_category(notice_type, incl, apogee, expected) -> None:
    assert S.orbit_category(notice_type, incl, apogee) == expected


def group(**over):
    values = {
        "start_mhz": 11000.0,
        "end_mhz": 11036.0,
        "direction": "TRANSMIT",
        "classes_services": ["EC/CP"],
        "notice_type": "GSO_SPACE_STATION",
        "nominal_longitude_deg": 20.0,
        "inclination_range": None,
        "apogee_range": None,
        "perigee_range": None,
        "density_dbw_hz": -60.0,
        "gain_dbi": 30.0,
        "group_bandwidth_khz": 36000.0,
    }
    values.update(over)
    return S.assess_group(**values)


def test_entry_selection_by_band_service_and_orbit() -> None:
    assert group()["worst_check"]["entry_id"] == "T21-4-11"
    ngso = dict(notice_type="NON_GSO_SPACE_STATION", perigee_range=[550.0, 550.0])
    low = group(**ngso, inclination_range=[53.0], apogee_range=[550.0])
    assert low["worst_check"]["entry_id"] == "T21-4-12"
    hio = group(**ngso, inclination_range=[63.4], apogee_range=[39000.0])
    assert hio["worst_check"]["entry_id"] == "T21-4-13"
    assert group(start_mhz=2200.0, end_mhz=2202.0, classes_services=["ER/OT"])["worst_check"][
        "entry_id"
    ] == ("T21-4-02")


def test_unestablished_applicability_is_never_applied() -> None:
    unknown = group(notice_type="NON_GSO_SPACE_STATION", perigee_range=[550.0])
    assert unknown["classification"] == "INSUFFICIENT_EVIDENCE"
    assert any("T21-4-12" in u for u in unknown["unresolved_entries"])
    # 12.5-12.75 GHz in Region 1 applies only in the countries of Nos. 5.494 and 5.496.
    assert group(start_mhz=12600.0, end_mhz=12650.0)["classification"] == (
        "NO_APPLICABLE_CRITERION"
    )
    # Radionavigation-satellite has no Table 21-4 entry; receive groups are not emissions.
    assert group(start_mhz=1176.0, end_mhz=1177.0, classes_services=["EN/CP"])[
        "classification"
    ] == ("NO_APPLICABLE_CRITERION")
    assert group(direction="RECEIVE")["classification"] == "NO_APPLICABLE_CRITERION"


def test_gso_margin_is_the_worst_over_the_finland_grid() -> None:
    result = group()
    check = result["worst_check"]
    limit = entry("T21-4-11")["limits"][0]
    expected = max(
        -60.0
        + 30.0
        - 10 * math.log10(4 * math.pi * (slant * 1000) ** 2)
        + 10 * math.log10(4e3)
        - S.limit_db(limit, elevation)
        for elevation, slant in (geo.gso_look(lat, lon, 20.0) for lat, lon in geo.finland_grid())
    )
    assert check["margin_db"] == pytest.approx(expected, abs=1e-3)
    assert check["bandwidth_used_hz"] == 4e3
    assert check["location"]["lat"] in {lat for lat, _ in geo.finland_grid()}


def test_classification_follows_the_margin() -> None:
    assert group(density_dbw_hz=-20.0)["classification"] == "WORST_CASE_EXCEEDANCE"
    assert group(density_dbw_hz=-80.0)["classification"] == "BELOW_SCREENING_THRESHOLD"
    margin = group()["margin_db"]
    near = group(density_dbw_hz=-60.0 - margin - 3.0)
    assert near["classification"] == "POTENTIAL_CONCERN"
    assert near["margin_db"] == pytest.approx(-3.0, abs=1e-3)


def test_unknown_parameter_makes_only_an_exceedance_conclusive() -> None:
    ngso = dict(
        start_mhz=3700.0,
        end_mhz=3740.0,
        notice_type="NON_GSO_SPACE_STATION",
        inclination_range=[53.0],
        apogee_range=[1200.0],
        perigee_range=[1200.0],
    )
    below = group(**ngso, density_dbw_hz=-90.0)
    assert below["worst_check"]["entry_id"] == "T21-4-05"
    assert below["classification"] == "INCONCLUSIVE_UNKNOWN_PARAMETER"
    assert group(**ngso, density_dbw_hz=-20.0)["classification"] == "WORST_CASE_EXCEEDANCE"


def test_a_narrow_group_uses_its_own_bandwidth_in_a_1_mhz_reference() -> None:
    ngso = dict(
        notice_type="NON_GSO_SPACE_STATION",
        inclination_range=[53.0],
        apogee_range=[550.0],
        perigee_range=[550.0],
    )
    wide = group(**ngso)["worst_check"]
    narrow = group(**ngso, group_bandwidth_khz=25.0)["worst_check"]
    assert narrow["bandwidth_used_hz"] == 25e3
    assert wide["margin_db"] - narrow["margin_db"] == pytest.approx(
        10 * math.log10(1e6 / 25e3), abs=1e-3
    )


def test_missing_inputs_are_insufficient_evidence() -> None:
    result = group(gain_dbi=None)
    assert result["classification"] == "INSUFFICIENT_EVIDENCE"
    assert "beam gain" in result["reason"]


def test_ngso_slant_range_geometry() -> None:
    assert S.ngso_slant_range_km(550.0, 90.0) == pytest.approx(550.0)
    r = geo.EARTH_RADIUS_KM
    assert S.ngso_slant_range_km(550.0, 0.0) == pytest.approx(math.sqrt((r + 550) ** 2 - r**2))


def test_registry_cites_its_source_and_lists_exclusions() -> None:
    registry = S.registry()
    assert registry["source"]["document"].endswith("Edition of 2024")
    assert registry["source"]["source_sha256"]
    assert len(registry["excluded"]) >= 10
    assert all(e["printed_page"] in range(287, 292) for e in registry["entries"])


def test_ngso_angles_stop_at_the_highest_elevation_over_finland() -> None:
    assert S.ngso_max_elevation_deg(97.5, 550.0) == 90.0  # Sun-synchronous passes overhead.
    low = S.ngso_max_elevation_deg(53.0, 550.0)
    assert low is not None and 0 < low < 90
    assert S.ngso_max_elevation_deg(10.0, 550.0) is None  # Never above Finland's horizon.
    unreachable = group(
        notice_type="NON_GSO_SPACE_STATION",
        inclination_range=[10.0],
        apogee_range=[550.0],
        perigee_range=[550.0],
    )
    assert unreachable["classification"] == "NO_APPLICABLE_CRITERION"
    assert unreachable["reason"] == "not visible from Finland"
    capped = group(
        notice_type="NON_GSO_SPACE_STATION",
        inclination_range=[53.0],
        apogee_range=[550.0],
        perigee_range=[550.0],
        density_dbw_hz=-20.0,
    )
    assert capped["worst_check"]["angle_of_arrival_deg"] <= low + 1e-9
