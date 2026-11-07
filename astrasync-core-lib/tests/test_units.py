import pytest
from astrasync_data import units


@pytest.mark.parametrize(
    ("raw", "hz"),
    [
        ("87.900 MHz", 87.9e6),
        ("300.000 kHz", 300e3),
        ("25 kHz", 25e3),
        ("26 GHz", 26e9),
        ("10,5 MHz", 10.5e6),
        (" 2025.700 MHz ", 2025.7e6),
    ],
)
def test_frequency_with_an_explicit_unit(raw: str, hz: float) -> None:
    assert units.frequency_hz(raw).value == pytest.approx(hz)


@pytest.mark.parametrize(
    ("raw", "rule"),
    [
        (None, "MISSING_VALUE"),
        ("", "MISSING_VALUE"),
        ("26", "UNIT_UNSPECIFIED"),  # Never assumed to be MHz.
        ("26.5", "UNIT_UNSPECIFIED"),
        ("1.000,5 MHz", "UNPARSEABLE_VALUE"),
        ("87.9 mhz", "UNPARSEABLE_VALUE"),
        ("0 MHz", "NON_POSITIVE_VALUE"),
        ("abc", "UNPARSEABLE_VALUE"),
    ],
)
def test_frequency_without_a_clear_meaning_is_null(raw: str | None, rule: str) -> None:
    assert units.frequency_hz(raw) == units.Parsed(None, rule)


@pytest.mark.parametrize(
    ("raw", "hz", "note"),
    [
        ("8M00", 8e6, None),
        ("10K0", 10e3, None),
        ("400H", 400.0, None),
        ("10k0", 10e3, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("300k", 300e3, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("7,6k", 7.6e3, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("1,4M", 1.4e6, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("0,1G", 0.1e9, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("110000k", 110e6, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
        ("5M", 5e6, "NON_STANDARD_BANDWIDTH_DESIGNATION"),
    ],
)
def test_bandwidth_designations(raw: str, hz: float, note: str | None) -> None:
    parsed = units.bandwidth_designation_hz(raw)
    assert parsed.value == pytest.approx(hz)
    assert parsed.rule_id == note


@pytest.mark.parametrize("raw", ["300m", "5g", "8M0,5", "M00", "1,5M00", "300 kHz"])
def test_ambiguous_bandwidth_designations_are_refused(raw: str) -> None:
    assert units.bandwidth_designation_hz(raw) == units.Parsed(None, "UNPARSEABLE_VALUE")
