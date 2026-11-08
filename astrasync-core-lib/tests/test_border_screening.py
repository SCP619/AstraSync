"""Border/territorial-sea sampling and the ECC T/R 25-08 A1.2.3 criterion (values checked against
the 6 June 2025 edition, docdb.cept.org/download/4789)."""

import math

import pytest
from astrasync_data import border_screening as B
from astrasync_data import geo


@pytest.mark.parametrize(
    ("frequency_mhz", "expected", "basis"),
    [
        (30.0, 0.0, "NORMATIVE_T/R_25-08_A1.2.3"),
        (80.0, 6.0, "NORMATIVE_T/R_25-08_A1.2.3"),
        (150.0, 12.0, "NORMATIVE_T/R_25-08_A1.2.3"),
        (390.0, 18.0, "NORMATIVE_T/R_25-08_A1.2.3"),
        (450.0, 20.0, "NORMATIVE_T/R_25-08_A1.2.3"),
        (793.5, 20.0, "CHALLENGE_EXTENSION_ABOVE_470_MHZ"),
    ],
)
def test_thresholds_follow_the_cited_table(frequency_mhz: float, expected: float, basis: str):
    criterion = B.threshold(frequency_mhz, 12.5)
    assert criterion is not None
    assert criterion["threshold_dbuv_m"] == expected
    assert criterion["basis"] == basis
    assert criterion["conditions"]["time_percentage"] == 10.0
    assert criterion["conditions"]["location_percentage"] == 50.0
    assert criterion["conditions"]["rx_height_agl_m"] == 10.0
    assert "T/R 25-08" in criterion["citation"]


def test_no_criterion_outside_the_scope() -> None:
    assert B.threshold(20.0, 25.0) is None
    assert B.threshold(5000.0, 25.0) is None


def test_bandwidth_correction_for_wide_channels_only() -> None:
    wide = B.threshold(793.5, 5000.0)
    assert wide is not None
    assert wide["bandwidth_correction_db"] == pytest.approx(10 * math.log10(200), abs=1e-4)
    assert wide["threshold_dbuv_m"] == pytest.approx(20 + 23.0103, abs=1e-3)
    assert any("uniform spectral power" in a for a in wide["assumptions"])
    narrow = B.threshold(450.0, 12.5)
    assert narrow is not None and narrow["bandwidth_correction_db"] == 0.0
    unknown = B.threshold(450.0, None)
    assert unknown is not None and unknown["assumptions"]


def test_samples_cover_land_borders_and_the_territorial_sea_limit() -> None:
    samples = B.samples(5.0)
    kinds = {s.kind for s in samples}
    assert kinds == {"LAND_BORDER", "TERRITORIAL_SEA_OUTER_LIMIT"}
    labels = {s.label for s in samples if s.kind == "LAND_BORDER"}
    assert labels == {
        "Finland-Russia land border",
        "Finland-Norway land border",
        "Finland-Sweden land border",
    }
    # Consecutive samples on a line are never further apart than the spacing (plus rounding).
    by_line: dict[int, list[B.Sample]] = {}
    for s in samples:
        by_line.setdefault(s.line, []).append(s)
    for points in by_line.values():
        for a, b in zip(points, points[1:], strict=False):
            assert geo.haversine_km(a.lat, a.lon, b.lat, b.lon) <= 5.0 + 1e-6


def test_candidate_samples_keep_every_point_in_the_window() -> None:
    # A transmitter in the Gulf of Finland, south of Helsinki: the sea limit is nearest.
    candidates = B.candidate_samples(59.95, 24.9, window_km=50.0)
    nearest = candidates[0][0]
    assert candidates[0][1].kind == "TERRITORIAL_SEA_OUTER_LIMIT"
    assert all(d <= nearest + 50.0 for d, _ in candidates)
    assert len(candidates) > 5


def test_boundary_data_records_its_provenance() -> None:
    provenance = B.boundaries()["provenance"]
    assert {p["part"] for p in provenance} == {"LAND_BORDER", "TERRITORIAL_SEA_OUTER_LIMIT"}
    assert all(p["licence"] and p["source_sha256"] for p in provenance)


@pytest.mark.parametrize(
    ("value", "finland", "expected"),
    [
        (25.0, False, "VERIFIED_CRITERION_EXCEEDANCE"),
        (25.0, True, "COORDINATION_REVIEW"),
        (16.0, False, "POTENTIAL_CONCERN"),
        (10.0, False, "BELOW_SCREENING_THRESHOLD"),
    ],
)
def test_classification_and_coordination(value: float, finland: bool, expected: str) -> None:
    criterion = B.threshold(450.0, 12.5)
    coordination = B.coordination_summary([["FIN", "C", "9.21"]] if finland else [["EST", "", ""]])
    result = B.classify(value, criterion, coordination, frequency_match=True)
    assert result["classification"] == expected
    assert result["margin_db"] == pytest.approx(value - 20.0)


def test_no_value_is_overlap_or_insufficient_evidence_never_an_exceedance() -> None:
    none = B.coordination_summary(None)
    assert B.classify(None, None, none, frequency_match=True)["classification"] == (
        "FREQUENCY_OVERLAP_ONLY"
    )
    assert B.classify(None, None, none, frequency_match=False)["classification"] == (
        "INSUFFICIENT_EVIDENCE"
    )
    assert B.classify(30.0, None, none, frequency_match=True)["classification"] == (
        "INSUFFICIENT_EVIDENCE"
    )


def test_the_concern_margin_is_configurable() -> None:
    criterion = B.threshold(450.0, 12.5)
    none = B.coordination_summary(None)
    assert (
        B.classify(10.0, criterion, none, frequency_match=True, concern_margin_db=12.0)[
            "classification"
        ]
        == "POTENTIAL_CONCERN"
    )
