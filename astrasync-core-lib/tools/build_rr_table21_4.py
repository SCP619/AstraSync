"""Write ``astrasync_data/criteria/rr_art21_table21_4.json`` from the transcription below.

The values are transcribed by hand from ITU Radio Regulations, Volume 1, Edition of 2024,
Article 21, Table 21-4 (Rev.WRC-23), printed pages 287-291, with footnotes 21.16.1-21.16.19 on
pages 291-294. Only entries whose applicability to Finland (Region 1) can be established from
IFIC screening data are listed; the others are recorded in ``excluded`` with the reason. The
ITU document itself is not redistributed.

    python tools/build_rr_table21_4.py

Every piecewise limit is checked for continuity at the segment boundaries, which catches
transcription slips (the printed table gives each segment separately).
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data/astrasync_data/criteria/rr_art21_table21_4.json"

FSS, BSS, MSS = "FIXED_SATELLITE", "BROADCASTING_SATELLITE", "MOBILE_SATELLITE"
RDSS, MET, SR = "RADIODETERMINATION_SATELLITE", "METEOROLOGICAL_SATELLITE", "SPACE_RESEARCH"
SO, EESS, ISS = "SPACE_OPERATION", "EARTH_EXPLORATION_SATELLITE", "INTER_SATELLITE"


def seg(a: float, b: float, base: float, slope: float = 0.0, ref: float = 0.0) -> dict:
    return {"from_deg": a, "to_deg": b, "base_db": base, "slope_db_per_deg": slope, "ref_deg": ref}


def std(low: float, high: float, slope: float) -> list[dict]:
    """The common 0-5 / 5-25 / 25-90 degree form: low, low + slope (delta - 5), high."""
    return [seg(0, 5, low), seg(5, 25, low, slope, 5), seg(25, 90, high)]


def band(lo: float, hi: float, label: str | None = None) -> dict:
    return {"min_mhz": lo, "max_mhz": hi, "label": label or f"{lo:g}-{hi:g} MHz"}


def lim(segments: list[dict], ref_hz: float) -> dict:
    return {"segments": segments, "reference_bandwidth_hz": ref_hz}


ENTRIES: list[dict] = []


def add(eid, bands, services, orbit, limits, page, notes=(), footnotes=(), parameter=None):
    entry = {
        "entry_id": eid,
        "bands": bands,
        "services": services,
        "orbit": orbit,
        "limits": limits,
        "printed_page": page,
        "footnotes": list(footnotes),
        "notes": list(notes),
    }
    if parameter:
        entry["parameter"] = parameter
    ENTRIES.append(entry)


add(
    "T21-4-01",
    [band(1670, 1700)],
    [EESS, MET],
    "ANY",
    [lim([seg(0, 90, -133)], 1.5e6)],
    287,
    notes=["Value based on sharing with the meteorological aids service."],
)
add(
    "T21-4-02",
    [
        band(1525, 1530, "1 525-1 530 MHz (Region 1)"),
        band(1700, 1710),
        band(2025, 2110),
        band(2200, 2300),
    ],
    [MET, SR, SO, EESS],
    "ANY",
    [lim(std(-154, -144, 0.5), 4e3)],
    287,
    footnotes=["21.16.3"],
)
add(
    "T21-4-03a",
    [band(2500, 2690)],
    [FSS],
    "ANY",
    [lim(std(-136, -125, 11 / 20), 1e6)],
    287,
    footnotes=["21.16.3A (Resolution 903 (Rev.WRC-19) applies)"],
)
add(
    "T21-4-03b",
    [band(2520, 2670)],
    [BSS],
    "ANY",
    [lim(std(-136, -125, 11 / 20), 1e6)],
    287,
    footnotes=["21.16.3A"],
)
add(
    "T21-4-03c",
    [band(2500, 2520)],
    [MSS],
    "ANY",
    [lim(std(-136, -125, 11 / 20), 1e6)],
    287,
    footnotes=["21.16.3A"],
)
add("T21-4-04", [band(3400, 4200)], [FSS], "GSO", [lim(std(-152, -142, 0.5), 4e3)], 287)
add(
    "T21-4-05",
    [band(3400, 4200)],
    [FSS],
    "NGSO",
    [lim(std(-138, -126, 12 / 20), 1e6)],
    287,
    footnotes=["21.16.15", "21.16.16"],
    parameter={
        "name": "Y",
        "definition": "21.16.15: Y = 0 for max(NN, NS) <= 2, else 5 log(max(NN, NS))",
        "segments_use": "Y = 0, the least strict value; Y > 0 only lowers the limit",
    },
)
add(
    "T21-4-06",
    [band(4500, 4800), band(7250, 7900)],
    [FSS, MET, MSS, SR],
    "ANY",
    [lim(std(-152, -142, 0.5), 4e3)],
    288,
)
add("T21-4-07", [band(5150, 5216)], [FSS], "ANY", [lim([seg(0, 90, -164)], 4e3)], 288)
add(
    "T21-4-08",
    [band(6700, 6825)],
    [FSS],
    "ANY",
    [lim(std(-137, -127, 0.5), 1e6)],
    288,
    footnotes=["21.16.7"],
)
add(
    "T21-4-09",
    [band(6825, 7075)],
    [FSS],
    "ANY",
    [lim(std(-154, -144, 0.5), 4e3), lim(std(-134, -124, 0.5), 1e6)],
    288,
    notes=["Both limits apply (4 kHz and 1 MHz)."],
)
add("T21-4-10", [band(8025, 8500)], [EESS, SR], "ANY", [lim(std(-150, -140, 0.5), 4e3)], 288)
add("T21-4-11", [band(10700, 11700)], [FSS], "GSO", [lim(std(-150, -140, 0.5), 4e3)], 288)
add(
    "T21-4-12",
    [band(10700, 11700)],
    [FSS],
    "NGSO_NOT_HIO",
    [lim(std(-126, -116, 0.5), 1e6)],
    288,
    footnotes=["21.16.18"],
)
add(
    "T21-4-13",
    [band(10700, 11700), band(11700, 12500, "11.7-12.5 GHz (Region 1)")],
    [FSS],
    "NGSO_HIO",
    [lim(std(-129, -114, 0.75), 1e6)],
    288,
    footnotes=["21.16.16", "21.16.17"],
)
add(
    "T21-4-14",
    [band(11700, 12500, "11.7-12.5 GHz (Region 1)")],
    [FSS],
    "NGSO_NOT_HIO",
    [lim(std(-124, -114, 0.5), 1e6)],
    289,
    footnotes=["21.16.18"],
)
add(
    "T21-4-15",
    [band(13400, 13650, "13.4-13.65 GHz (Region 1)")],
    [FSS],
    "GSO",
    [
        lim(
            [
                seg(0, 25, -159, 0.4, 0),
                seg(25, 80, -149),
                seg(80, 84, -149, -0.5, 80),
                seg(84, 90, -151),
            ],
            4e3,
        )
    ],
    289,
    footnotes=["21.16.9"],
)
add(
    "T21-4-16a",
    [band(17700, 19300)],
    [FSS, ISS],
    "GSO",
    [lim(std(-115, -105, 0.5), 1e6)],
    289,
    footnotes=["21.16.1", "21.16.2", "21.16.6A"],
    notes=[
        "21.16.2: the additional 18.6-18.8 GHz limit (-95 dB(W/m2) across 200 MHz) is not modelled."
    ],
)
add(
    "T21-4-16b",
    [band(17700, 19300)],
    [MET],
    "ANY_NOT_HIO",
    [lim(std(-115, -105, 0.5), 1e6)],
    289,
    footnotes=["21.16.6A"],
)
add(
    "T21-4-16c",
    [band(17700, 19300)],
    [FSS, ISS],
    "NGSO_NOT_HIO",
    [lim(std(-115, -105, 0.5), 1e6)],
    289,
    footnotes=["21.16.6"],
    parameter={
        "name": "X",
        "definition": "21.16.6: X depends on the number N of satellites in the NGSO FSS "
        "constellation (0 dB for N <= 50)",
        "segments_use": "X = 0, the least strict value; X > 0 only lowers the limit",
    },
)
add(
    "T21-4-17",
    [
        band(19300, 19700),
        band(21400, 22000, "21.4-22 GHz (Regions 1 and 3)"),
        band(22550, 23550),
        band(24450, 24750),
        band(25250, 27500),
    ],
    [FSS, BSS, EESS, ISS, SR],
    "ANY_NOT_HIO",
    [lim(std(-115, -105, 0.5), 1e6)],
    290,
    footnotes=["21.16.6B"],
)
add("T21-4-18", [band(27500, 27501)], [FSS], "ANY", [lim(std(-115, -105, 0.5), 1e6)], 290)
add(
    "T21-4-19",
    [band(31800, 32300)],
    [SR],
    "ANY",
    [lim(std(-120, -105, 0.75), 1e6)],
    290,
    footnotes=["21.16.10"],
)
add("T21-4-20", [band(32300, 33000)], [ISS], "ANY", [lim(std(-135, -115, 1.0), 1e6)], 290)
add(
    "T21-4-21a",
    [band(37000, 38000)],
    [SR],
    "NGSO",
    [lim(std(-120, -105, 0.75), 1e6)],
    290,
    footnotes=["21.16.10"],
)
add("T21-4-21b", [band(37000, 38000)], [SR], "GSO", [lim(std(-125, -105, 1.0), 1e6)], 290)
add(
    "T21-4-22",
    [band(37500, 40000)],
    [FSS, MSS],
    "GSO",
    [
        lim(
            [
                seg(0, 5, -127),
                seg(5, 20, -127, 4 / 3, 5),
                seg(20, 25, -107, 0.4, 20),
                seg(25, 90, -105),
            ],
            1e6,
        )
    ],
    290,
    footnotes=["21.16.14"],
)
add("T21-4-23", [band(40000, 40500)], [FSS, MSS], "ANY", [lim(std(-115, -105, 0.5), 1e6)], 290)
add(
    "T21-4-24",
    [band(40500, 42000)],
    [FSS, BSS],
    "GSO",
    [
        lim(
            [
                seg(0, 5, -120),
                seg(5, 15, -120, 1.0, 5),
                seg(15, 25, -110, 0.5, 15),
                seg(25, 90, -105),
            ],
            1e6,
        )
    ],
    291,
    footnotes=["21.16.14"],
)
add(
    "T21-4-25",
    [band(42000, 42500)],
    [FSS, BSS],
    "GSO",
    [
        lim(
            [
                seg(0, 5, -127),
                seg(5, 20, -127, 4 / 3, 5),
                seg(20, 25, -107, 0.4, 20),
                seg(25, 90, -105),
            ],
            1e6,
        )
    ],
    291,
    footnotes=["21.16.14"],
)
add(
    "T21-4-26",
    [
        band(47500, 47900, "47.5-47.9 GHz (Region 1)"),
        band(48200, 48540, "48.2-48.54 GHz (Region 1)"),
        band(49440, 50200, "49.44-50.2 GHz (Region 1)"),
    ],
    [FSS],
    "GSO",
    [lim(std(-115, -105, 0.5), 1e6)],
    291,
)

EXCLUDED = [
    ("1 518-1 525 MHz", "Territory of the United States in Region 2 only"),
    (
        "1 670-1 690 MHz (second entry, footnote 12)",
        "21.16.5: only where shared with equal rights with the meteorological aids service; not "
        "established for Finland",
    ),
    (
        "1 690-1 700 MHz (Nos. 5.381, 5.382)",
        "Country footnotes; Finland's inclusion not established",
    ),
    (
        "2 500-2 516.5 MHz (No. 5.404), 2 520-2 535 MHz (No. 5.403)",
        "Country footnotes; Finland's inclusion not established",
    ),
    (
        "5 670-5 725 MHz (Nos. 5.453, 5.455)",
        "Country footnotes; Finland's inclusion not established",
    ),
    (
        "9 900-10 400 MHz EESS (active)",
        "21.16.8: mean pfd of a SAR from pulse parameters, not the notified power density",
    ),
    (
        "12.5-12.75 GHz (Region 1 countries in Nos. 5.494, 5.496); 12.2-12.75 GHz (Region 3)",
        "Country or Region condition not established for Finland",
    ),
    (
        "17.7-19.7 GHz highly-inclined orbits (21.16.6B, 21.16.6C)",
        "Depends on Resolution 147 status and Bureau receipt dates not in the screening data",
    ),
    (
        "27.5-30.0 GHz inter-satellite NGSO (21.16.19)",
        "Resolution 679 Annex 2 methodology required",
    ),
    ("31.0-31.3 GHz, 34.7-35.2 GHz space research (Nos. 5.549, 5.550)", "Country footnotes"),
    (
        "37.5-40 GHz, 40.5-42.5 GHz NGSO (21.16.4)",
        "Valid only for systems with 99 or fewer satellites; the count is not in the screening "
        "data",
    ),
]


def document() -> dict:
    return {
        "criterion_set_id": "ITU-RR-ART21-TABLE21-4",
        "version": "1.0.0",
        "source": {
            "document": "ITU Radio Regulations, Volume 1 (Articles), Edition of 2024",
            "article": "Article 21, Section V, No. 21.16 and Table 21-4 (Rev.WRC-23), printed "
            "pages 286-294",
            "source_url": "https://search.itu.int/history/HistoryDigitalCollectionDocLibrary/"
            "1.49.48.en.101.pdf",
            "source_sha256": "040907a35846479b1f34ba628e35964dd4ce6d2b3fc05c2ff9b45e8ff215f5de",
            "retrieved": "2026-11-08",
        },
        "class_of_station_source": {
            "document": "Preface to the BR IFIC (Space Services), Table 3, Edition October 2026",
            "source_url": "https://www.itu.int/en/ITU-R/space/Preface/preface_e.pdf",
        },
        "metric": "PFD at the Earth's surface under free-space propagation, dB(W/m2) in the "
        "reference bandwidth",
        "angle": "delta: angle of arrival above the horizontal plane, degrees",
        "scope_note": "21.16: the limits apply to space-station emissions of the service "
        "indicated where the band is shared with equal rights with the fixed or mobile service, "
        "unless otherwise stated. 21.17: they may be exceeded on the territory of a country whose "
        "administration has so agreed. Only entries applicable to Region 1 / Finland without "
        "unresolved conditions are listed.",
        "highly_inclined_orbit": {
            "inclination_deg": [35, 145],
            "apogee_km_greater_than": 18000,
            "source": "21.16.6B, 21.16.6C, 21.16.17",
        },
        "class_of_station_services": {
            "EC": FSS,
            "EB": BSS,
            "EV": BSS,
            "EI": MSS,
            "EG": MSS,
            "EJ": MSS,
            "EU": MSS,
            "EF": RDSS,
            "EM": MET,
            "EH": SR,
            "ET": SO,
            "ER": SO,
            "EK": SO,
            "ED": SO,
            "EW": EESS,
            "ES": ISS,
        },
        "entries": ENTRIES,
        "excluded": [{"entry": a, "reason": b} for a, b in EXCLUDED],
        "approval": {
            "approved_by": "SCP619 (AstraSync team lead), per the Traficom organizers' "
            "confirmation that RR Article 21 PFD limits are the primary reference",
            "approved_at": "2026-11-08",
            "review_reference": "docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md C10",
        },
    }


def check_continuity(entries: list[dict]) -> None:
    for entry in entries:
        for limit in entry["limits"]:
            segments = limit["segments"]
            for a, b in zip(segments, segments[1:], strict=False):
                end = a["base_db"] + a["slope_db_per_deg"] * (a["to_deg"] - a["ref_deg"])
                start = b["base_db"] + b["slope_db_per_deg"] * (b["from_deg"] - b["ref_deg"])
                if abs(end - start) > 1e-9 or a["to_deg"] != b["from_deg"]:
                    raise ValueError(f"{entry['entry_id']}: discontinuity at {a['to_deg']} deg")


def main() -> None:
    check_continuity(ENTRIES)
    OUT.write_text(json.dumps(document(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(ENTRIES)} entries written to {OUT.name}")


if __name__ == "__main__":
    main()
