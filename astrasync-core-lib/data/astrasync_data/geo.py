"""Geometry for Finland relevance screening: distances, Finland boundary, land/sea, GSO look angles.

Boundary and land data are Natural Earth (public domain), see the JSON files' provenance. They
are for screening distances and path-zone labels, not legal boundaries. Spherical Earth with
radius 6371 km for ground distances; WGS-84 is not used, which keeps the error below about 0.5 %.
"""

from __future__ import annotations

import json
import math
from bisect import bisect_left
from functools import cache
from pathlib import Path

EARTH_RADIUS_KM = 6371.0
GSO_RADIUS_KM = 42164.0  # Geostationary orbit radius from the Earth's centre.
_HERE = Path(__file__).parent
# Reference points in Finland for GSO visibility: south coast, capital, east, far north.
FINLAND_POINTS = (
    ("Hanko", 59.823, 22.968),
    ("Helsinki", 60.170, 24.940),
    ("Joensuu", 62.601, 29.763),
    ("Utsjoki", 69.908, 27.027),
)
FINLAND_LATITUDE_RANGE = (59.7, 70.1)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def intermediate(
    lat1: float, lon1: float, lat2: float, lon2: float, f: float
) -> tuple[float, float]:
    """The point a fraction f along the great circle."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    d = haversine_km(lat1, lon1, lat2, lon2) / EARTH_RADIUS_KM
    if d == 0:
        return lat1, lon1
    a = math.sin((1 - f) * d) / math.sin(d)
    b = math.sin(f * d) / math.sin(d)
    x = a * math.cos(p1) * math.cos(l1) + b * math.cos(p2) * math.cos(l2)
    y = a * math.cos(p1) * math.sin(l1) + b * math.cos(p2) * math.sin(l2)
    z = a * math.sin(p1) + b * math.sin(p2)
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def _ring_contains(ring: list[list[float]], lon: float, lat: float) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


@cache
def _finland() -> tuple[list[list[list[float]]], list[tuple[float, float]]]:
    document = json.loads((_HERE / "finland_boundary.json").read_text(encoding="utf-8"))
    rings = document["rings"]
    vertices = [(lat, lon) for ring in rings for lon, lat in ring]
    return rings, vertices


def in_finland(lat: float, lon: float) -> bool:
    rings, _ = _finland()
    return any(_ring_contains(ring, lon, lat) for ring in rings)


def nearest_finland_point(lat: float, lon: float) -> tuple[float, float, float]:
    """(distance km, lat, lon) of the nearest boundary vertex; 0 km when inside Finland."""
    if in_finland(lat, lon):
        return 0.0, lat, lon
    _, vertices = _finland()
    best = min(vertices, key=lambda v: haversine_km(lat, lon, v[0], v[1]))
    return haversine_km(lat, lon, best[0], best[1]), best[0], best[1]


@cache
def _land_mask() -> tuple[
    tuple[float, float, float, float], float, list[list[tuple[float, float]]]
]:
    """Per latitude row, the land spans in longitude, by scanline filling of the land rings."""
    document = json.loads((_HERE / "region_land.json").read_text(encoding="utf-8"))
    lon0, lat0, lon1, lat1 = document["bbox_lon_lat"]
    step = 0.05
    rows = int(round((lat1 - lat0) / step))
    edges = []
    for ring in document["rings"]:
        for (xa, ya), (xb, yb) in zip(ring, ring[1:] + ring[:1], strict=True):
            if ya != yb:
                edges.append((xa, ya, xb, yb))
    spans: list[list[tuple[float, float]]] = []
    for r in range(rows):
        lat = lat0 + (r + 0.5) * step
        xs = sorted(
            xa + (lat - ya) * (xb - xa) / (yb - ya)
            for xa, ya, xb, yb in edges
            if (ya > lat) != (yb > lat)
        )
        spans.append([(xs[k], xs[k + 1]) for k in range(0, len(xs) - 1, 2)])
    return (lon0, lat0, lon1, lat1), step, spans


def is_land(lat: float, lon: float) -> bool | None:
    """True/False inside the land data's box; None outside it (unknown, never assumed)."""
    (lon0, lat0, lon1, lat1), step, spans = _land_mask()
    if not (lat0 <= lat < lat1 and lon0 <= lon <= lon1):
        return None
    row = spans[int((lat - lat0) / step)]
    starts = [a for a, _ in row]
    k = bisect_left(starts, lon) - 1
    return k >= 0 and row[k][0] <= lon <= row[k][1]


def path_zones(
    lat1: float, lon1: float, lat2: float, lon2: float, step_km: float = 1.0
) -> list[list[float | str]] | None:
    """P.1546 path zones [[km, "Land"|"Sea"], ...] from the transmitter; None if unknown."""
    total = haversine_km(lat1, lon1, lat2, lon2)
    samples = max(2, int(total / step_km))
    zones: list[list[float | str]] = []
    for k in range(samples):
        lat, lon = intermediate(lat1, lon1, lat2, lon2, (k + 0.5) / samples)
        land = is_land(lat, lon)
        if land is None:
            return None
        zone = "Land" if land else "Sea"
        length = total / samples
        if zones and zones[-1][1] == zone:
            zones[-1][0] = float(zones[-1][0]) + length
        else:
            zones.append([length, zone])
    return zones


def gso_look(lat: float, lon: float, satellite_lon: float) -> tuple[float, float]:
    """(elevation deg, slant range km) from a point on a spherical Earth to a GSO position."""
    phi = math.radians(lat)
    dl = math.radians(satellite_lon - lon)
    cos_gamma = math.cos(phi) * math.cos(dl)
    slant = math.sqrt(
        EARTH_RADIUS_KM**2 + GSO_RADIUS_KM**2 - 2 * EARTH_RADIUS_KM * GSO_RADIUS_KM * cos_gamma
    )
    sin_gamma = math.sqrt(max(0.0, 1 - cos_gamma**2))
    elevation = math.degrees(math.atan2(cos_gamma - EARTH_RADIUS_KM / GSO_RADIUS_KM, sin_gamma))
    return elevation, slant


def ngso_reach(
    inclination_deg: float, altitude_km: float, latitude_deg: float
) -> tuple[bool, float]:
    """Whether a circular-orbit satellite can be above the horizon at ``latitude_deg`` and the
    minimum slant range there (km), from inclination and altitude only (spherical Earth)."""
    folded = min(inclination_deg, 180 - inclination_deg)
    coverage = math.degrees(math.acos(EARTH_RADIUS_KM / (EARTH_RADIUS_KM + altitude_km)))
    gap = max(0.0, abs(latitude_deg) - folded)
    if gap > coverage:
        return False, math.inf
    radius = EARTH_RADIUS_KM + altitude_km
    angle = math.radians(gap)
    slant = math.sqrt(
        EARTH_RADIUS_KM**2 + radius**2 - 2 * EARTH_RADIUS_KM * radius * math.cos(angle)
    )
    return True, slant
