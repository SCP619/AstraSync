"""Build the judge demonstration dataset: synthetic notices run through the real screening code.

    python tools/build_judge_demo.py --out ../traficom-integration/ui/src/demo/judge-demo.json

Every input below is invented (administration "DEMO", site names "DEMO ..."); every number in the
output is computed by the same functions the evaluation uses (P.1546-6, border screening against
ECC T/R 25-08 A1.2.3, the free-space PFD upper bound, the workbook parser). The output contains
no IFIC record, no workbook row and nothing protected, so it may ship as a public static asset.
The same code version gives the same file (no clock, no randomness).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from astrasync_data import border_screening as B
from astrasync_data import ific_analysis as A
from astrasync_data.traficom_workbook import ENGLISH, parse_row
from astrasync_physics.space_pfd import SpacePfdFreeSpace
from astrasync_physics.terrestrial_p1546 import TerrestrialP1546

DATASET_VERSION = "judge-demo/1.0.0"


def _record(table: str, key: str, start: float, end: float, **norm: Any) -> dict[str, Any]:
    return {
        "source_table_or_sheet": table,
        "source_row_or_key": key,
        "notice_id": norm.pop("notice_id", key),
        "issue_key": "DEMO",
        "administration": "DEMO",
        "frequency_start_mhz": start,
        "frequency_end_mhz": end,
        "raw_fields": {
            f"norm.{k}": None if v is None else v if isinstance(v, str) else json.dumps(v)
            for k, v in norm.items()
        },
    }


def _notice(key: str, site: str, lat: float, lon: float, f: float, erp: float, **over: Any):
    fields = {
        "notice_id": f"DEMO-T-{key}",
        "role": "NOTICE",
        "intent": "ADD",
        "assignment_id": f"DEMO-A-{key}",
        "station_class": "FB",
        "is_land_mobile": True,
        "assigned_frequency_mhz": f,
        "bandwidth_khz": 12.5,
        "latitude_deg": lat,
        "longitude_deg": lon,
        "radiated_power_dbw": erp,
        "radiated_power_type": "ERP",
        "antenna_height_agl_m": 40.0,
        "site_name": site,
        "site_country": "DEMO",
        "targets": [],
        "publications": ["DEMO"],
    }
    fields.update(over)
    return _record("fxm_terra", key, f - 0.00625, f + 0.00625, **fields)


def _terrestrial(finding: dict[str, Any], title: str, story: str) -> dict[str, Any]:
    border = finding["border_screening"]
    return {
        "id": finding["notice_id"],
        "domain": "TERRESTRIAL",
        "title": title,
        "story": story,
        "site": finding["site_name"],
        "frequency_mhz": finding["frequency_mhz"],
        "bandwidth_khz": finding["bandwidth_khz"],
        "concern": finding["concern"],
        "criterion": finding["criterion"],
        "coordination": finding["coordination"],
        "border": {
            k: border.get(k)
            for k in (
                "status",
                "points_evaluated",
                "max_field_strength_dbuv_m",
                "max_point",
                "max_by_boundary_kind",
                "parameters",
                "spacing_km",
                "window_km",
            )
        },
        "priority": finding["priority"],
        "regulatory_finding": finding["regulatory_finding"],
    }


def build() -> dict[str, Any]:
    refs = A.References(A.IntervalIndex([]), A.IntervalIndex([]))
    method = TerrestrialP1546()
    notices = [
        _notice("1", "DEMO BORDER BASE", 61.10, 29.05, 152.0, 17.0),
        _notice("2", "DEMO GULF BASE", 59.62, 25.20, 450.0, 20.0),
        _notice(
            "3",
            "DEMO COORDINATED BASE",
            61.10,
            29.05,
            152.5,
            17.0,
            coordination=[["FIN", "C", "9.21"]],
        ),
        _notice("4", "DEMO NEAR-THRESHOLD BASE", 61.45, 29.95, 160.0, -14.0),
        _notice("5", "DEMO DISTANT BASE", 63.00, 34.50, 160.0, 10.0),
    ]
    result = A.analyse_terrestrial(notices, refs, None, p1546_method=method)
    by_id = {f["notice_id"]: f for f in result["findings"]}
    stories = {
        "DEMO-T-1": (
            "Land-border exceedance",
            "A base station about 20 km from the Finnish land "
            "border. P.1546-6 is evaluated at every border sample in reach; the highest "
            "value exceeds the T/R 25-08 threshold, so coordination is indicated.",
        ),
        "DEMO-T-2": (
            "Territorial-sea exceedance",
            "A station south of the Gulf of Finland: the "
            "highest field strength is at the outer limit of Finland's territorial sea, "
            "not at the coast.",
        ),
        "DEMO-T-3": (
            "Coordinated notice needing review",
            "Same geometry, but the notice records "
            "coordination with Finland. The exceedance stays visible and is routed to "
            "an expert to check the coordination history.",
        ),
        "DEMO-T-4": (
            "Near-threshold case",
            "Within the configurable 6 dB concern window below "
            "the threshold: flagged as a potential concern for review.",
        ),
        "DEMO-T-5": (
            "Below the screening threshold",
            "A distant station: computed, below the threshold by more than the concern window.",
        ),
    }
    scenarios = [_terrestrial(by_id[k], *stories[k]) for k in stories]

    # Workbook data quality: a made-up row with the reported 2500 kHz / 118600k pattern.
    row = {h: None for h in ENGLISH}
    row.update(
        {
            "Station number": 900001,
            "Class of licence": "XYZ",
            "Longitude": "25.0",
            "Latitude": "61.0",
            "Channel bandwidth": "2500 kHz",
            "TX frequency": "1250 MHz",
            "Transmission bandwidth": "118600k",
            "Ant height AGL (m)": 30,
        }
    )
    parsed = parse_row(12, tuple(row[h] for h in ENGLISH))
    station = parsed["reference_station"]
    scenarios.append(
        {
            "id": "DEMO-W-1",
            "domain": "WORKBOOK",
            "title": "Bandwidth mismatch",
            "story": "Channel 2500 kHz but transmission 118600k: both raw values are kept, the "
            "mismatch is flagged and screening uses the smaller value (organizer guidance). "
            "An unknown licence class screens as MUUT.",
            "raw": {
                "channel_bandwidth": "2500 kHz",
                "transmission_bandwidth": "118600k",
                "licence_class": "XYZ",
            },
            "normalized": {
                k: station[k]
                for k in (
                    "channel_bandwidth_hz",
                    "emission_bandwidth_hz",
                    "effective_bandwidth_hz",
                    "effective_bandwidth_rule",
                    "licence_class_normalized",
                )
            },
            "quality_findings": [
                f for f in parsed["quality_findings"] if f["rule_id"] == "BANDWIDTH_MISMATCH"
            ],
        }
    )

    def group(key: str, **over: Any) -> dict[str, Any]:
        fields = {
            "notice_id": f"DEMO-S-{key}",
            "notice_type": "GSO_SPACE_STATION",
            "satellite_name": f"DEMO-SAT-{key}",
            "nominal_longitude_deg": 20.0,
            "direction": "TRANSMIT",
            "group_id": key,
            "max_power_density_dbw_hz": -62.0,
            "beam_max_gain_dbi": 34.0,
            "service_area_countries": [],
            "special_sections": ["DEMO"],
            "station_classes_services": ["EC/CP"],
            "submission_occurrence": "F",
        }
        fields.update(over)
        return _record("grp", key, 10950.0, 10986.0, **fields)

    space = A.analyse_space(
        [group("1"), group("2", notice_id="DEMO-S-2", beam_max_gain_dbi=None)],
        refs,
        pfd_method=SpacePfdFreeSpace(),
    )
    for finding in space["findings"]:
        has_pfd = finding["max_pfd"] is not None
        scenarios.append(
            {
                "id": finding["notice_id"],
                "domain": "SPACE",
                "title": "Space PFD upper bound" if has_pfd else "Missing satellite beam data",
                "story": (
                    "Worst case: the maximum beam gain is assumed to point at the nearest "
                    "node of the Finland grid. The upper bound is compared with ITU RR Table 21-4 "
                    "(10.7-11.7 GHz FSS GSO, 4 kHz); it is not EPFD and not a finding."
                    if has_pfd
                    else "The notice gives no beam gain, so no PFD can be computed. AstraSync "
                    "reports insufficient evidence instead of guessing a gain."
                ),
                "max_pfd_db_w_m2_hz_upper_bound": finding["max_pfd"],
                "concern": finding["concern"],
                "criterion_check": (finding["criterion_checks"] or [{}])[0].get("worst_check"),
                "geometry": finding["stage_c_geometry"],
                "readiness": finding["stage_d_readiness"],
                "regulatory_finding": finding["regulatory_finding"],
            }
        )
    return {
        "dataset": DATASET_VERSION,
        "data_status": "SYNTHETIC DEMONSTRATION DATA: invented notices computed by AstraSync's "
        "real screening code. Not live analysis and not IFIC data.",
        "criterion": B.criterion_set()["source"],
        "boundaries": B.boundaries()["provenance"],
        "scenarios": scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(build(), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
