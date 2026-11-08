"""Recommendation ITU-R P.1546-6: point-to-area field strength, 30 MHz to 4 000 MHz.

A line-by-line Python port of ``P1546FieldStrMixed.m`` v16, the reference implementation approved
by ITU-R Working Party 3K (I. Stevanovic, OFCOM; https://github.com/eeveetza/p1546, Zenodo
10.5281/zenodo.6206015). The tabulated curves (figures 1-24) are read from ``p1546_tables.json``,
extracted unchanged from that file. Changes from the original, as its licence asks: translated to
Python by AstraSync on 2026-11-08; the debug log writer and plotting are omitted; the transmitter
and receiver terrain heights of the slope-path correction may be given as one height difference.

Behaviour kept exactly as in the reference, including two details a reader may not expect:
- In Step 8.2 for sea paths with d >= D20 the height interpolation uses a natural logarithm in the
  denominator (``log(20/10)``), as in the reference code.
- Annex 7 (climatic regions) and the Annex 5 section 4.3a) terrain-database form of C_h1 are not
  implemented, as in the reference.

Validation: ``tests/test_p1546.py`` compares this port with every result in the reference's
``validation_results`` folder. The comparison data stays outside the repository; the test is
skipped, and says so, when ``ASTRASYNC_P1546_REFERENCE`` does not point at it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

TABLES_PATH = Path(__file__).with_name("p1546_tables.json")
IMPLEMENTATION_SHA = hashlib.sha256(
    Path(__file__).read_bytes() + TABLES_PATH.read_bytes()
).hexdigest()

DISTANCES_KM = (
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    70,
    75,
    80,
    85,
    90,
    95,
    100,
    110,
    120,
    130,
    140,
    150,
    160,
    170,
    180,
    190,
    200,
    225,
    250,
    275,
    300,
    325,
    350,
    375,
    400,
    425,
    450,
    475,
    500,
    525,
    550,
    575,
    600,
    625,
    650,
    675,
    700,
    725,
    750,
    775,
    800,
    825,
    850,
    875,
    900,
    925,
    950,
    975,
    1000,
)
HEIGHTS_M = (10.0, 20.0, 37.5, 75.0, 150.0, 300.0, 600.0, 1200.0)
LAND_AREAS = ("Rural", "Suburban", "Urban", "Dense Urban")
AREAS = (*LAND_AREAS, "Sea")
ZONES = ("Land", "Sea", "Cold", "Warm")
# (time %, path code, nominal frequency MHz) -> figure number; path 1 land, 2 sea, 3 cold, 4 warm.
_FIGURES = (
    (50, 1, 100),
    (10, 1, 100),
    (1, 1, 100),
    (50, 2, 100),
    (10, 3, 100),
    (1, 3, 100),
    (10, 4, 100),
    (1, 4, 100),
    (50, 1, 600),
    (10, 1, 600),
    (1, 1, 600),
    (50, 2, 600),
    (10, 3, 600),
    (1, 3, 600),
    (10, 4, 600),
    (1, 4, 600),
    (50, 1, 2000),
    (10, 1, 2000),
    (1, 1, 2000),
    (50, 2, 2000),
    (10, 3, 2000),
    (1, 3, 2000),
    (10, 4, 2000),
    (1, 4, 2000),
)


class P1546InputError(ValueError):
    """An input outside what the Recommendation (or the reference code) accepts."""


@dataclass(frozen=True)
class _Figure:
    time: int
    path: int
    freq: int
    number: int


@cache
def _tables() -> dict[int, dict[float, dict[float, float]]]:
    """figure number -> h1 -> distance -> E."""
    document = json.loads(TABLES_PATH.read_text(encoding="utf-8"))
    result: dict[int, dict[float, dict[float, float]]] = {}
    for figure in document["figures"]:
        by_height: dict[float, dict[float, float]] = {}
        for column, height in enumerate(document["heights_m"]):
            by_height[float(height)] = {
                float(d): float(row[column])
                for d, row in zip(figure["distances_km"], figure["field_strength"], strict=True)
            }
        result[int(figure["figure"])] = by_height
    return result


def _search_closest(values: Sequence[float], v: float) -> tuple[float, float]:
    """``searchclosest``: the nominal values below and above v (both v when it is nominal)."""
    if values[-1] < v:
        return values[-2], values[-1]
    if values[0] > v:
        return values[0], values[1]
    low, high = 0, len(values) - 1
    while low <= high:
        mid = (low + high) // 2
        diff = values[mid] - v
        if diff == 0:
            return v, v
        if diff < 0:
            low = mid + 1
        else:
            high = mid - 1
    return values[high], values[low]


def _figures(general_path: str) -> list[_Figure]:
    rows = [_Figure(t, p, f, i + 1) for i, (t, p, f) in enumerate(_FIGURES)]
    if general_path == "Sea":
        return [row for row in rows if row.path > 1]
    return [row for row in rows if row.path == 1]


def _general(zone: str) -> str:
    return "Sea" if zone in ("Warm", "Cold", "Sea") else "Land"


def h1_calc(
    d: float, heff: float, ha: float | None, hb: float | None, path: str, terrain_info: int
) -> float:
    """Annex 5 section 3: transmitting/base antenna height h1."""
    if path.lower() == "land":
        if d < 15:
            if terrain_info == 0:
                if d <= 3:
                    return ha if ha is not None else heff  # (4)
                return ha + (heff - ha) * (d - 3) / 12 if ha is not None else heff  # (5)
            return hb if hb is not None else heff  # (6)
        return heff  # (7)
    if path.lower() == "sea":
        return 3.0 if heff < 3 else heff
    return math.nan


def _step_19a(t: float, dland: float, dsea: float) -> float:
    """Maximum field strength, Annex 5 section 2, eqs (1)-(3) and (42)."""
    if t < 1 or t > 50:
        raise P1546InputError("The percentage time is outside [1, 50] %")
    dtotal = dland + dsea
    efs = 106.9 - 20 * math.log10(dtotal)
    ese = 2.38 * (1 - math.exp(-dtotal / 8.94)) * math.log10(50 / t)
    return efs + dsea * ese / dtotal


def _d06(f: float, h1: float, h2: float) -> float:
    """Section 18: path length for 0.6 Fresnel clearance, eq (41)."""
    h1 = max(h1, 0.0)
    df = 0.0000389 * f * h1 * h2
    dh = 4.1 * (math.sqrt(h1) + math.sqrt(h2))
    return max(df * dh / (df + dh), 0.001)


def _j(nu: float) -> float:
    """Eq (12a)."""
    return 6.9 + 20 * math.log10(math.sqrt((nu - 0.1) ** 2 + 1) + nu - 0.1)


def _v(fnom: float, h1: float) -> float:
    factor = {100: 1.35, 600: 3.31, 2000: 6.0}.get(int(fnom))
    if factor is None:
        raise P1546InputError("Invalid nominal frequency")
    return factor * math.degrees(math.atan(-h1 / 9000))  # (12b), (12c)


def _step_814_815(figure: int, h1: float, dinf: float, dsup: float, d: float) -> float:
    column = _tables()[figure][float(h1)]
    e_inf = column[float(dinf)]
    if dsup != dinf:
        e_sup = column[float(dsup)]
        return e_inf + (e_sup - e_inf) * math.log10(d / dinf) / math.log10(dsup / dinf)  # (13)
    return column[float(dsup)]


def _step_81(figure: int, h1: float, dinf: float, dsup: float, d: float, emax: float) -> float:
    hinf, hsup = _search_closest(HEIGHTS_M, h1)
    e_sup = _step_814_815(figure, hsup, dinf, dsup, d)
    if hinf != hsup:
        e_inf = _step_814_815(figure, hinf, dinf, dsup, d)
        eh1 = e_inf + (e_sup - e_inf) * math.log10(h1 / hinf) / math.log10(hsup / hinf)  # (8)
    else:
        eh1 = e_sup
    return min(eh1, emax)


def _ezero(e10: float, e20: float, fnom: float) -> float:
    v = _v(fnom, -10)
    j = _j(v) if v > -0.7806 else 0.0
    return e10 + 0.5 * ((e10 - e20) + (6.03 - j))  # (9a), (9b), (12)


def _step_82(
    figure: int,
    h1: float,
    dinf: float,
    dsup: float,
    d: float,
    path: str,
    fnom: float,
    emax: float,
    t: float,
) -> float:
    """Annex 5 section 4.2 (and 4.3 b) for h1 < 10 m."""
    e10 = _step_814_815(figure, 10.0, dinf, dsup, d)
    e20 = _step_814_815(figure, 20.0, dinf, dsup, d)
    ezero = _ezero(e10, e20, fnom)
    if path == "Land":
        if h1 >= 0:
            return ezero + 0.1 * h1 * (e10 - ezero)  # (9)
        v = _v(fnom, h1)
        j = _j(v) if v > -0.7806 else 0.0
        return ezero + 6.03 - j  # (12)
    if h1 < 1:
        raise P1546InputError("h1 cannot be less than 1 m for a sea path")
    dh1 = _d06(fnom, h1, 10)  # (10a)
    d20 = _d06(fnom, 20, 10)  # (10b)
    if d <= dh1:
        return emax  # (11a)
    if d < d20:
        dinf1, dsup1 = _search_closest(DISTANCES_KM, d20)
        e10d20 = _step_814_815(figure, 10.0, dinf1, dsup1, d20)
        e20d20 = _step_814_815(figure, 20.0, dinf1, dsup1, d20)
        ed20 = e10d20 + (e20d20 - e10d20) * math.log10(h1 / 10) / math.log10(20 / 10)
        edh1 = _step_19a(t, 0, dh1)
        return edh1 + (ed20 - edh1) * math.log10(d / dh1) / math.log10(d20 / dh1)  # (11b)
    # As in the reference code: natural logarithm in the denominator.
    e1 = e10 + (e20 - e10) * math.log10(h1 / 10) / math.log(20 / 10)
    e2 = ezero + 0.1 * h1 * (e10 - ezero)
    fs = (d - d20) / d
    return e1 * (1 - fs) + e2 * fs  # (11c)


def _step_7(
    figures: list[_Figure],
    h1: float,
    dinf: float,
    dsup: float,
    d: float,
    general_path: str,
    f: float,
    emax: float,
    t: float,
) -> float:
    """Steps 7-9: nominal frequencies and interpolation in frequency, eq (14)."""
    finf, fsup = _search_closest((100, 600, 2000), f)
    nominal = [finf, fsup]
    values = [0.0, 0.0]
    for j in range(1 if finf == fsup else 0, 2):
        figure = next(row.number for row in figures if row.freq == nominal[j])
        if h1 >= 10:
            values[j] = min(_step_81(figure, h1, dinf, dsup, d, emax), emax)
        else:
            values[j] = _step_82(figure, h1, dinf, dsup, d, general_path, nominal[j], emax, t)
    if finf != fsup:
        e = values[0] + (values[1] - values[0]) * math.log10(f / finf) / math.log10(fsup / finf)
        return min(e, emax) if f > 2000 else e
    return values[1]


def _step_6_10(
    figures: list[_Figure],
    h1: float,
    dinf: float,
    dsup: float,
    d: float,
    path: str,
    f: float,
    emax: float,
    t: float,
) -> float:
    """Steps 6-10: nominal time percentages and interpolation in time, eq (16)."""
    tinf, tsup = _search_closest((1, 10, 50), t)
    nominal = [tinf, tsup]
    values = [0.0, 0.0]
    general_path = _general(path)
    for index in range(1 if tinf == tsup else 0, 2):
        wanted = nominal[index]
        if wanted in (10, 1) and path == "Warm":
            chosen = [row for row in figures if row.time == wanted and row.path == 4]
        else:
            chosen = [row for row in figures if row.time == wanted]
        df = _d06(f, h1, 10)
        d600 = _d06(600, h1, 10)
        if general_path == "Sea" and f < 100 and d < d600:
            if d <= df:
                values[index] = _step_19a(t, 0, d)  # (15a)
            else:
                edf = _step_19a(t, 0, df)
                d600inf, d600sup = _search_closest(DISTANCES_KM, d600)
                ed600 = _step_7(chosen, h1, d600inf, d600sup, d600, general_path, f, emax, t)
                values[index] = edf + (ed600 - edf) * math.log10(d / df) / math.log10(d600 / df)
        else:
            values[index] = _step_7(chosen, h1, dinf, dsup, d, general_path, f, emax, t)
    if tinf != tsup:
        q_sup, q_inf, q_t = qi(tsup / 100), qi(tinf / 100), qi(t / 100)
        return values[1] * (q_inf - q_t) / (q_inf - q_sup) + values[0] * (q_t - q_sup) / (
            q_inf - q_sup
        )
    return values[1]


def _step_11a(
    eland: list[float], esea: list[float], dland: list[float], dsea: list[float]
) -> float:
    """Mixed paths, Annex 5 section 8 (RRC-06 method), eqs (22)-(26)."""
    dl_total, ds_total = sum(dland), sum(dsea)
    total = dl_total + ds_total
    if dl_total == 0:
        return sum(d * e for d, e in zip(dsea, esea, strict=True)) / total  # (22)
    if ds_total == 0:
        return sum(d * e for d, e in zip(dland, eland, strict=True)) / total
    land = sum(e * d for e, d in zip(eland, dland, strict=True)) / dl_total
    sea = sum(e * d for e, d in zip(esea, dsea, strict=True)) / ds_total
    delta = sea - land  # (26)
    v = max(1.0, 1.0 + delta / 40)
    a0 = 1 - (1 - ds_total / total) ** (2 / 3)
    a = float(a0**v)
    return float((1 - a) * land + a * sea)  # (23)


def _step_12a(f: float, tca: float) -> tuple[float, float]:
    """Terrain clearance angle correction, Annex 5 section 11."""
    tca = min(max(tca, 0.55), 40.0)
    nup = 0.036 * math.sqrt(f)
    nu = 0.065 * tca * math.sqrt(f)
    j1 = _j(nup) if nup > -0.7806 else 0.0
    j2 = _j(nu) if nu > -0.7806 else 0.0
    return j1 - j2, nu


def _step_13a(d: float, f: float, t: float, eff1: float, eff2: float) -> tuple[float, float]:
    """Tropospheric scatter, Annex 5 section 13, eqs (35)-(36)."""
    theta_s = max(180 * d / math.pi / 4 * 3 / 6370 + eff1 + eff2, 0.0)
    e = (
        24.4
        - 20 * math.log10(d)
        - 10 * theta_s
        - (5 * math.log10(f) - 2.5 * (math.log10(f) - 3.3) ** 2)
        + 0.15 * 325
        + 10.1 * (-math.log10(0.02 * t)) ** 0.7
    )
    return e, theta_s


def _step_14a(
    h1: float, d: float, r2: float, h2: float, f: float, area: str
) -> tuple[float, float]:
    """Receiving/mobile antenna height correction, Annex 5 section 9."""
    k_h2 = 3.2 + 6.2 * math.log10(f)
    if area in LAND_AREAS:
        if h2 < 1:
            raise P1546InputError("h2 < 1 m is not valid adjacent to land")
        rp = max((1000 * d * r2 - 15 * h1) / (1000 * d - 15), 1.0)  # (27)
        if area in ("Urban", "Dense Urban", "Suburban"):
            if h2 < rp:
                h_dif = rp - h2
                theta_clut = math.degrees(math.atan(h_dif / 27))
                nu = 0.0108 * math.sqrt(f) * math.sqrt(h_dif * theta_clut)
                correction = 6.03 - _j(nu)  # (28a)
            else:
                correction = k_h2 * math.log10(h2 / rp)  # (28b)
            if rp < 10:
                correction -= k_h2 * math.log10(10 / rp)
            return correction, rp
        return k_h2 * math.log10(h2 / 10), 10.0
    if area != "Sea":
        raise P1546InputError(f"Unknown receiver area {area!r}")
    if h2 < 3:
        raise P1546InputError("h2 < 3 m is not valid adjacent to sea")
    c10 = k_h2 * math.log10(h2 / 10)
    if h2 >= 10:
        return c10, 10.0
    d10 = _d06(f, h1, 10)
    dh2 = _d06(f, h1, h2)
    if d >= d10:
        return c10, 10.0
    if d <= dh2:
        return 0.0, 10.0
    return c10 * math.log10(d / dh2) / math.log10(d10 / dh2), 10.0


def _step_15a(ha: float, r1: float, f: float) -> float:
    """Transmitter/base clutter correction, Annex 5 section 10, eq (30)."""
    k_nu = 0.0108 * math.sqrt(f)
    hdif1 = ha - r1
    theta_clut = math.degrees(math.atan(hdif1 / 27))
    product = hdif1 * theta_clut  # Non-negative: both factors share a sign.
    nu = k_nu * math.sqrt(product) if r1 >= ha else -k_nu * math.sqrt(product)
    return -_j(nu) if nu > -0.7806 else 0.0


def _dslope(ha: float, h2: float, d: float, height_difference_m: float | None) -> float:
    """Slope distance, eqs (37a, b)."""
    difference = ha - h2 if height_difference_m is None else height_difference_m
    return math.sqrt(d * d + 1e-6 * difference**2)


def _step_16a(ha: float, h2: float, d: float, height_difference_m: float | None) -> float:
    return 20 * math.log10(d / _dslope(ha, h2, d, height_difference_m))  # (37)


def _step_17a(
    ha: float, h2: float, d: float, e_sup: float, height_difference_m: float | None
) -> float:
    """Distances below 1 km, Annex 5 section 15, eq (38)."""
    d_slope = _dslope(ha, h2, d, height_difference_m)
    if d <= 0.04:
        return 106.9 - 20 * math.log10(d_slope)
    dinf_slope = _dslope(ha, h2, 0.04, height_difference_m)
    dsup_slope = _dslope(ha, h2, 1.0, height_difference_m)
    e_inf = 106.9 - 20 * math.log10(dinf_slope)
    return e_inf + (e_sup - e_inf) * math.log10(d_slope / dinf_slope) / math.log10(
        dsup_slope / dinf_slope
    )


def _step_18a(
    e_median: float, q: float, f: float, terrain_info: int, wa: float | None, area: str
) -> float:
    """Location variability, Annex 5 section 12."""
    if q < 1 or q > 99:
        raise P1546InputError("The percentage of locations is outside [1, 99] %")
    if area == "Sea":
        sigma = 0.0
    elif terrain_info == 0:
        sigma = {"Urban": 8.0, "Dense Urban": 8.0, "Suburban": 10.0, "Rural": 12.0}[area]
    else:
        if wa is None:
            raise P1546InputError("wa is required when terrain information is used")
        sigma = ((0.024 * f) / 1000.0 + 0.52) * wa**0.28
    return e_median + qi(q / 100) * sigma


def qi(x: float) -> float:
    """Annex 5 section 16: inverse complementary cumulative normal distribution, eq (39)."""

    def t(y: float) -> float:
        return math.sqrt(-2 * math.log(y))

    def c(z: float) -> float:
        tz = t(z)
        return ((0.010328 * tz + 0.802853) * tz + 2.515517) / (
            ((0.001308 * tz + 0.189269) * tz + 1.432788) * tz + 1
        )

    if x <= 0.5:
        return t(x) - c(x)
    return -(t(1 - x) - c(1 - x))


@dataclass(frozen=True)
class P1546Result:
    field_strength_dbuv_m: float
    basic_transmission_loss_db: float
    h1_m: float
    emax_dbuv_m: float
    trace: dict[str, float | None]


def field_strength(
    f_mhz: float,
    t_percent: float,
    heff_m: float,
    h2_m: float,
    r2_m: float,
    area: str,
    distances_km: Sequence[float],
    zones: Sequence[str],
    terrain_info: int,
    *,
    q_percent: float = 50.0,
    wa_m: float | None = None,
    ptx_kw: float = 1.0,
    ha_m: float | None = None,
    hb_m: float | None = None,
    r1_m: float | None = None,
    tca_deg: float | None = None,
    eff1_deg: float | None = None,
    eff2_deg: float | None = None,
    height_difference_m: float | None = None,
    h1_m: float | None = None,
) -> P1546Result:
    """``P1546FieldStrMixed``. Returns E in dB(uV/m) for ``ptx_kw`` kW e.r.p. and Lb in dB.

    ``height_difference_m`` is (ha + htter) - (h2 + hrter) of eq (37b) when terrain heights are
    known. ``h1_m`` replaces the Annex 5 section 3 calculation when the caller already has h1.
    """
    if not 1 <= t_percent <= 50:
        raise P1546InputError("t must be within [1, 50] %")
    if len(distances_km) != len(zones) or not distances_km:
        raise P1546InputError("Each path zone needs one length")
    if any(zone not in ZONES for zone in zones):
        raise P1546InputError(f"Path zones must be among {ZONES}")
    if area not in AREAS:
        raise P1546InputError(f"area must be among {AREAS}")
    if any(length < 0 for length in distances_km):
        raise P1546InputError("Path lengths must not be negative")
    dtot = float(sum(distances_km))
    if not 0 < dtot <= 1000:
        raise P1546InputError("The total path length must be within (0, 1000] km")
    if ptx_kw <= 0:
        raise P1546InputError("e.r.p. must be positive")

    zones = list(zones)
    if len(zones) > 1 and "Warm" in zones and "Cold" in zones:
        zones = ["Warm" if zone == "Cold" else zone for zone in zones]
    first = "Land" if len(zones) > 1 else zones[0]
    general_first = _general(first)
    h1 = (
        h1_m if h1_m is not None else h1_calc(dtot, heff_m, ha_m, hb_m, general_first, terrain_info)
    )
    if math.isnan(h1):
        raise P1546InputError("h1 could not be determined")
    h1 = min(h1, 3000.0)
    if terrain_info == 1 and q_percent != 50 and (wa_m is None or wa_m <= 0):
        raise P1546InputError("wa is required when terrain information is used and q != 50")

    d = dtot
    if dtot < 1:
        dinf = dsup = 1.0
    else:
        dinf, dsup = _search_closest(DISTANCES_KM, d)
    dland = [length for length, zone in zip(distances_km, zones, strict=True) if zone == "Land"]
    dsea = [length for length, zone in zip(distances_km, zones, strict=True) if zone != "Land"]

    trace: dict[str, float | None] = {"h1_m": h1}
    emax = _step_19a(t_percent, sum(dland), sum(dsea))
    if ha_m is not None:
        emax += _step_16a(ha_m, h2_m, d, height_difference_m)
    trace["emax_dbuv_m"] = emax

    eland: list[float] = []
    esea: list[float] = []
    for zone in zones:
        figures = _figures(_general(zone))
        value = _step_6_10(figures, h1, dinf, dsup, max(d, 1.0), zone, f_mhz, emax, t_percent)
        (eland if zone == "Land" else esea).append(value)
    e = _step_11a(eland, esea, dland, dsea)
    trace["e_after_mixed_path_dbuv_m"] = e

    if tca_deg is not None:
        correction, nu = _step_12a(f_mhz, tca_deg)
        e += correction
        trace["tca_correction_db"] = correction
        trace["tca_nu"] = nu
    if eff1_deg is not None and eff2_deg is not None:
        ets, theta_s = _step_13a(max(d, 1.0), f_mhz, t_percent, eff1_deg, eff2_deg)
        e = max(e, ets)
        trace["troposcatter_dbuv_m"] = ets
        trace["theta_s_deg"] = theta_s
    correction, rp = _step_14a(h1, max(d, 1.0), r2_m, h2_m, f_mhz, area)
    e += correction
    trace["rx_height_correction_db"] = correction
    trace["rx_representative_clutter_m"] = rp
    if ha_m is not None and r1_m is not None:
        correction = _step_15a(ha_m, r1_m, f_mhz)
        e += correction
        trace["tx_clutter_correction_db"] = correction
    if ha_m is not None:
        correction = _step_16a(ha_m, h2_m, max(d, 1.0), height_difference_m)
        e += correction
        trace["slope_path_correction_db"] = correction
    if dtot < 0.9999999999:
        if ha_m is None:
            raise P1546InputError("ha is required for paths shorter than 1 km")
        e = _step_17a(ha_m, h2_m, d, e, height_difference_m)
        trace["short_path_dbuv_m"] = e
    if q_percent != 50 and area != "Sea":
        e = _step_18a(e, q_percent, f_mhz, terrain_info, wa_m, area)
        trace["location_corrected_dbuv_m"] = e
    e = min(e, emax)
    loss = 139.3 - e + 20 * math.log10(f_mhz)  # Step 20, eq (40), for 1 kW.
    e += 10 * math.log10(ptx_kw)
    return P1546Result(
        field_strength_dbuv_m=e,
        basic_transmission_loss_db=loss,
        h1_m=h1,
        emax_dbuv_m=emax,
        trace=trace,
    )
