"""Build ``astrasync_data/finland_screening_boundaries.json``: Finland's land borders and the outer
limit of its territorial sea, as polylines for border field-strength screening.

    python tools/build_screening_boundaries.py \
        --countries ne_10m_admin_0_countries.geojson \
        --territorial-sea-lines TerritorialSeaArea_L.json --out data/astrasync_data/...

Land borders: the Finland (FIN) ring vertices that are also vertices of Russia, Norway or Sweden
in Natural Earth 1:10m Admin 0 Countries (public domain), split into runs per neighbour.
Territorial sea: the ``avoin:TerritorialSeaArea_L`` layer of Traficom's open INSPIRE WFS
(dataset "Aluevesien rajat", CC BY 4.0), requested in EPSG:4326. Both are screening geometry, not
legal boundaries. The coastline is never used as the territorial-sea limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

NEIGHBOURS = {"RUS": "Russia", "NOR": "Norway", "SWE": "Sweden"}


def _rings(feature: dict) -> list[list[list[float]]]:
    geometry = feature["geometry"]
    polygons = (
        [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    )
    return [ring for polygon in polygons for ring in polygon]


def _key(point: list[float]) -> tuple[float, float]:
    return (round(point[0], 6), round(point[1], 6))


def land_borders(countries: dict) -> list[dict]:
    by_code = {f["properties"].get("ADM0_A3"): f for f in countries["features"]}
    neighbour_vertices = {
        code: {_key(p) for ring in _rings(by_code[code]) for p in ring} for code in NEIGHBOURS
    }
    lines = []
    for ring in _rings(by_code["FIN"]):
        current: list[list[float]] = []
        current_code = None
        for point in ring:
            code = next((c for c, v in neighbour_vertices.items() if _key(point) in v), None)
            if code is not None and code == current_code:
                current.append(point)
                continue
            if len(current) >= 2:
                lines.append({"neighbour": current_code, "coordinates": current})
            current, current_code = ([point], code) if code else ([], None)
        if len(current) >= 2:
            lines.append({"neighbour": current_code, "coordinates": current})
    return [
        {
            "kind": "LAND_BORDER",
            "label": f"Finland-{NEIGHBOURS[line['neighbour']]} land border",
            "neighbour": line["neighbour"],
            "coordinates": [[round(x, 6), round(y, 6)] for x, y in line["coordinates"]],
        }
        for line in lines
    ]


def territorial_sea(lines: dict) -> list[dict]:
    out = []
    for feature in lines["features"]:
        geometry = feature["geometry"]
        parts = (
            [geometry["coordinates"]]
            if geometry["type"] == "LineString"
            else geometry["coordinates"]
        )
        for part in parts:
            out.append(
                {
                    "kind": "TERRITORIAL_SEA_OUTER_LIMIT",
                    "label": f"Territorial sea limit {feature['properties'].get('IDENTIFIER')}",
                    "source_identifier": feature["properties"].get("IDENTIFIER"),
                    "source_date": feature["properties"].get("SORDAT"),
                    "coordinates": [[round(x, 6), round(y, 6)] for x, y in part],
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--countries", type=Path, required=True)
    parser.add_argument("--territorial-sea-lines", type=Path, required=True)
    parser.add_argument("--retrieved", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    countries = json.loads(args.countries.read_text(encoding="utf-8"))
    sea = json.loads(args.territorial_sea_lines.read_text(encoding="utf-8"))
    document = {
        "description": (
            "Finland's land borders and territorial-sea outer limit as lon/lat polylines "
            "(EPSG:4326) for border field-strength screening (ECC T/R 25-08 'at the border-line'; "
            "organizer clarification: land borders and the outer limit of the territorial sea). "
            "Screening geometry, not legal boundaries."
        ),
        "crs": "EPSG:4326 (lon, lat degrees)",
        "provenance": [
            {
                "part": "LAND_BORDER",
                "dataset": "Natural Earth 1:10m Admin 0 Countries",
                "publisher": "Natural Earth",
                "source": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
                "geojson/ne_10m_admin_0_countries.geojson",
                "licence": "Public domain (Natural Earth terms of use)",
                "source_sha256": hashlib.sha256(args.countries.read_bytes()).hexdigest(),
                "method": "Finland ring vertices shared with RUS, NOR or SWE, split per neighbour",
                "retrieved": args.retrieved,
            },
            {
                "part": "TERRITORIAL_SEA_OUTER_LIMIT",
                "dataset": "Aluevesien rajat (territorial waters boundaries), layer "
                "avoin:TerritorialSeaArea_L",
                "publisher": "Liikenne- ja viestintävirasto Traficom",
                "source": "https://julkinen.traficom.fi/inspirepalvelu/avoin/wfs (WFS 2.0.0, "
                "srsName EPSG:4326); catalogue https://avoindata.suomi.fi/data/dataset/"
                "aluevesien-rajat",
                "licence": "Creative Commons Attribution 4.0",
                "source_sha256": hashlib.sha256(
                    args.territorial_sea_lines.read_bytes()
                ).hexdigest(),
                "retrieved": args.retrieved,
            },
        ],
        "lines": land_borders(countries) + territorial_sea(sea),
    }
    args.out.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
