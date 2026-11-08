"""ITU-R P.1546-6 port checked against the WP 3K reference implementation's own results.

The reference repository (https://github.com/eeveetza/p1546) is not vendored. Point
``ASTRASYNC_P1546_REFERENCE`` at its ``matlab`` folder to run the comparison; each log in
``validation_results`` holds the inputs and the reference's intermediate and final values.

Inputs the logs print only indirectly are recovered exactly from the logged intermediate values:
eff2 from the scatter angle theta_s (eq 35), and the slope-path terrain height difference from
the logged slope correction (eq 37). Logged inputs carry six significant digits, so results are
compared to 0.01 dB.
"""

import math
import os
from pathlib import Path

import pytest
from astrasync_physics import p1546

REFERENCE = os.environ.get("ASTRASYNC_P1546_REFERENCE")
TOLERANCE_DB = 0.01


def _logs() -> list[Path]:
    if not REFERENCE:
        return []
    return sorted((Path(REFERENCE) / "validation_results").glob("*_log.csv"))


def _read(path: Path) -> dict[str, tuple[str, str]]:
    values: dict[str, tuple[str, str]] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        # Some reference logs use ";" as the separator, the rest ",".
        cells = line.split(";") if line.count(";") > line.count(",") else line.split(",")
        if len(cells) >= 4 and not line.startswith("#"):
            values[cells[0].strip()] = (cells[1].strip(), cells[3].strip())
    return values


def _number(values: dict[str, tuple[str, str]], key: str) -> float | None:
    raw = values.get(key, ("", ""))[1]
    return float(raw) if raw else None


def _case(values: dict[str, tuple[str, str]]) -> dict[str, object]:
    def n(key: str) -> float | None:
        return _number(values, key)

    land = n("Land path (km)") or 0.0
    sea = n("Sea path (km)") or 0.0
    sea_type = values.get("Sea path (km)", ("", ""))[0] or "Cold"
    distances, zones = [], []
    if land > 0:
        distances.append(land)
        zones.append("Land")
    if sea > 0:
        distances.append(sea)
        zones.append(sea_type)
    d = land + sea
    ha = n("Tx antenna height a. g. ha (m)")
    h2 = n("Rx antenna height a. g. h2 (m)")
    height_difference = None
    slope = n("Rx slope-path correction (dB)")
    if ha is not None and slope is not None:
        dd = max(d, 1.0)
        d_slope = dd / 10 ** (slope / 20)
        height_difference = math.sqrt(max(d_slope**2 - dd**2, 0.0) / 1e-6)
    eff1 = n("Tx effective TCA  theta_eff1 (deg)")
    theta_s = n("Path scattering theta_s (deg)")
    eff2 = None
    if eff1 is not None and theta_s is not None:
        geometric = 180 * max(d, 1.0) / math.pi / 4 * 3 / 6370
        eff2 = theta_s - eff1 - geometric if theta_s > 0 else -(geometric + eff1)
    return {
        "f_mhz": n("Frequency f (MHz)"),
        "t_percent": n("Percentage time t (%)"),
        "heff_m": n("Tx antenna height h1 (m)"),
        "h2_m": h2,
        "r2_m": n("Rx clutter height R2 (m)") or 0.0,
        "area": values["Rx clutter type"][1],
        "distances_km": distances,
        "zones": zones,
        "terrain_info": int(n("Terrain profile information available") or 0),
        "q_percent": n("Percentage location q (%)") or 50.0,
        "wa_m": n("Square area width wa for variability (m)"),
        "ptx_kw": n("Tx Power (kW)") or 1.0,
        "ha_m": ha,
        "r1_m": n("Tx clutter height R1 (m)"),
        "tca_deg": n("Terrain clearance angle tca (deg)"),
        "eff1_deg": eff1 if eff2 is not None else None,
        "eff2_deg": eff2,
        "height_difference_m": height_difference,
        "h1_m": n("Tx antenna height h1 (m)"),
    }


@pytest.mark.skipif(not _logs(), reason="ASTRASYNC_P1546_REFERENCE is not set")
@pytest.mark.parametrize("log", _logs(), ids=lambda path: path.stem)
def test_matches_the_reference_implementation(log: Path) -> None:
    values = _read(log)
    expected = _number(values, "Resulting field strength for given PTx (dBuV/m)")
    expected_loss = _number(values, "Resulting basic transmission loss (dB)")
    assert expected is not None and expected_loss is not None
    result = p1546.field_strength(**_case(values))  # type: ignore[arg-type]
    assert abs(result.field_strength_dbuv_m - expected) <= TOLERANCE_DB, (
        result.field_strength_dbuv_m,
        expected,
        result.trace,
    )
    assert abs(result.basic_transmission_loss_db - expected_loss) <= TOLERANCE_DB


def test_free_space_limit_and_known_properties() -> None:
    """Checks that need no reference files: the maximum and monotonic behaviour."""
    near = p1546.field_strength(450, 50, 75, 10, 10, "Rural", [10], ["Land"], 0, ha_m=75)
    far = p1546.field_strength(450, 50, 75, 10, 10, "Rural", [100], ["Land"], 0, ha_m=75)
    assert far.field_strength_dbuv_m < near.field_strength_dbuv_m
    assert near.field_strength_dbuv_m <= near.emax_dbuv_m
    doubled = p1546.field_strength(
        450, 50, 75, 10, 10, "Rural", [100], ["Land"], 0, ha_m=75, ptx_kw=2.0
    )
    assert doubled.field_strength_dbuv_m - far.field_strength_dbuv_m == pytest.approx(
        10 * math.log10(2)
    )


def test_inputs_outside_the_recommendation_are_refused() -> None:
    with pytest.raises(p1546.P1546InputError):
        p1546.field_strength(450, 60, 75, 10, 10, "Rural", [10], ["Land"], 0)
    with pytest.raises(p1546.P1546InputError):
        p1546.field_strength(450, 50, 75, 10, 10, "Rural", [1200], ["Land"], 0)
    with pytest.raises(p1546.P1546InputError):
        p1546.field_strength(450, 50, 75, 10, 10, "Moon", [10], ["Land"], 0)


def test_qi_matches_standard_normal_quantiles() -> None:
    assert p1546.qi(0.5) == pytest.approx(0.0, abs=1e-3)
    assert p1546.qi(0.1) == pytest.approx(1.2816, abs=1e-3)
    assert p1546.qi(0.9) == pytest.approx(-1.2816, abs=1e-3)
