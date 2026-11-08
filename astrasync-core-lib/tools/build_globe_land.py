"""Build the dashboard globe's land outlines: ``ui/src/dashboard/globe/land.json``.

    python tools/build_globe_land.py --land ne_50m_land.geojson \
        --out ../traficom-integration/ui/src/dashboard/globe/land.json

Natural Earth 1:50m land (public domain), simplified with Douglas-Peucker (tolerance in degrees)
and rounded to 0.05 degrees, plus Finland's outline from ``finland_boundary.json``. The globe
paints these into a canvas texture at start-up, so no imagery has to be downloaded.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "data" / "astrasync_data"


def _perpendicular(p: list[float], a: list[float], b: list[float]) -> float:
    if a == b:
        return math.dist(p, a)
    (x, y), (x1, y1), (x2, y2) = p, a, b
    return abs((y2 - y1) * x - (x2 - x1) * y + x2 * y1 - y2 * x1) / math.dist(a, b)


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        best, index = 0.0, -1
        for i in range(start + 1, end):
            d = _perpendicular(points[i], points[start], points[end])
            if d > best:
                best, index = d, i
        if best > tolerance and index > 0:
            keep[index] = True
            stack += [(start, index), (index, end)]
    return [p for p, k in zip(points, keep, strict=True) if k]


def _round(points: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for lon, lat in points:
        q = [round(lon * 20) / 20, round(lat * 20) / 20]
        if not out or out[-1] != q:
            out.append(q)
    return out


def rings(geometry: dict) -> list[list[list[float]]]:
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    return [polygon[0] for polygon in polygons]  # Outer rings only; lakes are not drawn.


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--land", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=0.25)
    args = parser.parse_args()
    land = json.loads(args.land.read_text(encoding="utf-8"))
    out_rings = []
    for feature in land["features"]:
        for ring in rings(feature["geometry"]):
            simple = _round(simplify(ring, args.tolerance))
            if len(simple) >= 4:
                out_rings.append(simple)
    finland = json.loads((HERE / "finland_boundary.json").read_text(encoding="utf-8"))
    fin = [_round(simplify(r, 0.03)) for r in finland["rings"]]
    document = {
        "source": "Natural Earth 1:50m land and 1:10m Finland (public domain), simplified",
        "land": out_rings,
        "finland": [r for r in fin if len(r) >= 4],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
    print(len(out_rings), "land rings,", args.out.stat().st_size // 1024, "KiB")


if __name__ == "__main__":
    main()
