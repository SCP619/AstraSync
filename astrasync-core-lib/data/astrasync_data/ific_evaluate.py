"""Reproducible evaluation of one IFIC issue: ``python -m astrasync_data.ific_evaluate``.

    python -m astrasync_data.ific_evaluate terrestrial \
        --issue brific3076.zip --previous brific3075.zip \
        --m4 Taajuusjakotaulukko-v13.json \
        --workbook Traficom_SinceAI_Frequencies_of_interest_v05112026.xlsx --out out/3076

Writes ``manifest.json`` (inputs with SHA-256, parser, rule and method versions, publisher
reconciliation), ``findings.json.gz`` (all findings), ``findings_high.json``, ``findings.csv``,
``comparison.json`` and ``report.md``.
The same inputs give the same outputs: nothing depends on the clock except the stated run time.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import border_screening
from . import ific_analysis as A
from . import itu_ific as I
from .traficom_m4_table import TraficomM4TableAdapter
from .traficom_workbook import TraficomWorkbookAdapter

OFFICIAL_URLS = {
    I.SPACE_SOURCE_TYPE: "https://www.itu.int/sns/ific10/ific{n}.zip",
    I.TERRESTRIAL_SOURCE_TYPE: "https://www.itu.int/en/ITU-R/terrestrial/brific/BRIFIC/MDB/brific{n}.zip",
}
M4_URL = "https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _file(path: Path, url: str | None, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "official_url": url,
    }


def _records(adapter: Any, path: Path) -> list[dict[str, Any]]:
    return [r for batch in adapter.iter_record_batches(path, batch_rows=5000) for r in batch]


def load_references(m4: Path, workbook: Path) -> A.References:
    m4_records = _records(TraficomM4TableAdapter(), m4)
    station_records = _records(TraficomWorkbookAdapter(), workbook)
    return A.References(
        A.IntervalIndex(A.m4_references(m4_records)),
        A.IntervalIndex(A.station_references(station_records)),
        {"m4_rows": len(m4_records), "special_interest_rows": len(station_records)},
    )


def _read_issue(path: Path, kind: str) -> tuple[list[dict[str, Any]], I.IficSummary]:
    reader = I.read_space if kind == I.SPACE_SOURCE_TYPE else I.read_terrestrial
    with I.open_database(path, kind) as database:
        return reader(database, I.issue_from_name(path.name, kind))


def _methods() -> dict[str, Any]:
    from astrasync_physics import p1546, space_pfd, terrestrial_p1546

    return {
        "TERR_P1546": {
            "plugin": terrestrial_p1546.TerrestrialP1546(),
            "version": terrestrial_p1546.METHOD_VERSION,
            "implementation_sha": p1546.IMPLEMENTATION_SHA,
            "validation": terrestrial_p1546.VALIDATION,
        },
        "SPACE_PFD_FREE_SPACE": {
            "plugin": space_pfd.SpacePfdFreeSpace(),
            "version": space_pfd.METHOD_VERSION,
            "implementation_sha": space_pfd.IMPLEMENTATION_SHA,
            "validation": {"status": "ANALYTIC_FORMULA_UNIT_TESTED"},
        },
    }


def evaluate(
    kind: str, issue_path: Path, previous_path: Path | None, m4: Path, workbook: Path, out: Path
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    refs = load_references(m4, workbook)
    records, summary = _read_issue(issue_path, kind)
    previous_records, previous_summary = (None, None)
    if previous_path is not None:
        previous_records, previous_summary = _read_issue(previous_path, kind)
    methods = _methods()
    if kind == I.TERRESTRIAL_SOURCE_TYPE:
        result = A.analyse_terrestrial(
            records, refs, previous_records, p1546_method=methods["TERR_P1546"]["plugin"]
        )
        trends = A.terrestrial_trends(records, previous_records)
    else:
        previous_ids = (
            {r["notice_id"] for r in previous_records} if previous_records is not None else None
        )
        result = A.analyse_space(
            records, refs, previous_ids, pfd_method=methods["SPACE_PFD_FREE_SPACE"]["plugin"]
        )
        trends = None
    findings = result["findings"]
    comparison = _comparison(findings, summary, previous_summary)
    manifest = {
        "artifact": f"AstraSync evaluation of {kind} {summary.issue}",
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "issue": summary.issue,
        "publication_date": summary.publication_date,
        "kind": kind,
        "inputs": [
            _file(issue_path, OFFICIAL_URLS[kind].format(n=summary.issue), "IFIC issue"),
            *(
                [
                    _file(
                        previous_path,
                        OFFICIAL_URLS[kind].format(n=previous_summary.issue),
                        "previous IFIC issue",
                    )
                ]
                if previous_path and previous_summary
                else []
            ),
            _file(m4, M4_URL, "Finnish table of frequencies (M4), Traficom open data, CC BY 4.0"),
            _file(workbook, None, "Challenge special-interest workbook (synthetic data)"),
        ],
        "parsers": {
            "ific": I.SPACE_PARSER_VERSION
            if kind == I.SPACE_SOURCE_TYPE
            else I.TERRESTRIAL_PARSER_VERSION,
            "m4": TraficomM4TableAdapter.parser_version,
            "workbook": TraficomWorkbookAdapter.parser_version,
        },
        "rule_version": A.RULE_VERSION,
        "methods": {
            k: {key: v for key, v in m.items() if key != "plugin"} for k, m in methods.items()
        },
        "references": refs.provenance,
        "parse_summary": summary.counts,
        "previous_parse_summary": previous_summary.counts if previous_summary else None,
        "screening_parameters": {
            "terrestrial_time_percent": A.SCREEN_TIME_PERCENT,
            "terrestrial_location_percent": A.SCREEN_LOCATION_PERCENT,
            "terrestrial_rx_height_m": A.SCREEN_RX_HEIGHT_M,
            "terrestrial_rx_area": A.SCREEN_RX_AREA,
            "space_pfd_reference_bandwidth_hz": A.PFD_REFERENCE_BANDWIDTH_HZ,
            "note": "AstraSync screening defaults, not the conditions of an approved criterion.",
        },
        "criteria": (
            {
                "terrestrial": border_screening.criterion_set()["source"],
                "criterion_set_id": border_screening.criterion_set()["criterion_set_id"],
                "challenge_extension_above_470_mhz": border_screening.criterion_set()[
                    "challenge_extension_above_470_mhz"
                ],
                "boundaries": border_screening.boundaries()["provenance"],
                "border_spacing_km": border_screening.DEFAULT_SPACING_KM,
                "border_window_km": border_screening.DEFAULT_WINDOW_KM,
                "concern_margin_db": border_screening.DEFAULT_CONCERN_MARGIN_DB,
                "meaning": "Indicative coordination threshold: exceeding it indicates coordination "
                "with Finland, not harmful interference or non-compliance.",
            }
            if kind == I.TERRESTRIAL_SOURCE_TYPE
            else "None approved for space. No PFD limit comparison is made."
        ),
        "environment": {"python": sys.version.split()[0], "platform": platform.platform()},
    }
    _write_json(out / "manifest.json", manifest)
    full = {
        "issue": summary.issue,
        "kind": kind,
        "findings": findings,
        "skipped": result.get("skipped"),
    }
    # The full set is large: it is written compressed, with the HIGH tier also as plain JSON.
    with gzip.open(out / "findings.json.gz", "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(full, handle, ensure_ascii=False, default=str)
    _write_json(
        out / "findings_high.json",
        {
            **full,
            "findings": [f for f in findings if f["priority"]["tier"] == "HIGH"],
            "note": "HIGH tier only; findings.json.gz holds every finding.",
        },
    )
    _write_json(out / "comparison.json", {**comparison, "trends": trends})
    _write_csv(out / "findings.csv", findings, kind)
    if kind == I.TERRESTRIAL_SOURCE_TYPE:
        _write_border_points(out / "border_points.csv", findings)
        concerns = Counter((f.get("concern") or {}).get("classification") for f in findings)
        _write_json(
            out / f"terrestrial_ific_{summary.issue}_cases.json",
            {
                "issue": summary.issue,
                "data_status": "REAL_IFIC_SCREENING_RESULTS (expert review required)",
                "criterion": border_screening.criterion_set(),
                "concern_counts": dict(concerns),
                "cases": [
                    f
                    for f in findings
                    if (f.get("concern") or {}).get("classification")
                    in ("VERIFIED_CRITERION_EXCEEDANCE", "COORDINATION_REVIEW", "POTENTIAL_CONCERN")
                ],
            },
        )
    (out / "report.md").write_text(
        _report(manifest, findings, comparison, trends, kind), encoding="utf-8", newline="\n"
    )
    return {"issue": summary.issue, "findings": len(findings), "out": str(out)}


def _border_columns(f: dict[str, Any]) -> list[Any]:
    border = f.get("border_screening") or {}
    point = border.get("max_point") or {}
    criterion = f.get("criterion") or {}
    concern = f.get("concern") or {}
    coordination = f.get("coordination") or {}
    return [
        border.get("max_field_strength_dbuv_m"),
        point.get("kind"),
        point.get("label"),
        point.get("lat"),
        point.get("lon"),
        point.get("distance_km"),
        border.get("points_evaluated"),
        criterion.get("basis"),
        criterion.get("base_threshold_dbuv_m"),
        criterion.get("bandwidth_correction_db"),
        criterion.get("threshold_dbuv_m"),
        concern.get("margin_db"),
        concern.get("classification"),
        coordination.get("finland_mentioned"),
        json.dumps(coordination.get("rows") or [], ensure_ascii=False),
    ]


def _write_border_points(path: Path, findings: list[dict[str, Any]]) -> None:
    """Every notice's strongest boundary points (up to five), so no exposure is hidden."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "notice_id",
                "assignment_id",
                "rank_at_notice",
                "boundary_kind",
                "boundary_label",
                "lat",
                "lon",
                "distance_km",
                "field_strength_dbuv_m",
                "threshold_dbuv_m",
                "margin_db",
                "calculation_sha256",
            ]
        )
        for f in findings:
            border = f.get("border_screening") or {}
            threshold = (f.get("criterion") or {}).get("threshold_dbuv_m")
            for rank, point in enumerate(border.get("top_points") or [], 1):
                value = point["field_strength_dbuv_m"]
                writer.writerow(
                    [
                        f["notice_id"],
                        f["assignment_id"],
                        rank,
                        point["kind"],
                        point["label"],
                        point["lat"],
                        point["lon"],
                        point["distance_km"],
                        value,
                        threshold,
                        None if threshold is None else round(value - threshold, 2),
                        point.get("calculation_sha256"),
                    ]
                )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _comparison(
    findings: list[dict[str, Any]], summary: I.IficSummary, previous: I.IficSummary | None
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for f in findings:
        key = f["change"]["change_type"]
        counts[key] = counts.get(key, 0) + 1
    in_previous = sum(
        1
        for f in findings
        if f["change"].get("in_previous_issue") or f["change"].get("previous_issue")
    )
    return {
        "issue": summary.issue,
        "previous_issue": previous.issue if previous else None,
        "change_types": counts,
        "also_published_in_previous_issue": in_previous if previous else None,
        "rules": "NEW, MODIFIED and WITHDRAWN come from the notice itself (terrestrial intent "
        "ADD/MODIFY/SUPPRESS; space ntf_occurs, tgt_ntc_id, f_int_ext). An item absent from an "
        "issue is never treated as withdrawn: each IFIC carries that issue's notices only.",
    }


def _write_csv(path: Path, findings: list[dict[str, Any]], kind: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if kind == I.TERRESTRIAL_SOURCE_TYPE:
            writer.writerow(
                [
                    "rank",
                    "notice_id",
                    "assignment_id",
                    "administration",
                    "station_class",
                    "site",
                    "frequency_mhz",
                    "bandwidth_khz",
                    "change",
                    "distance_to_finland_km",
                    "special_interest_overlaps",
                    "max_field_strength_dbuv_m",
                    "border_max_field_strength_dbuv_m",
                    "border_point_kind",
                    "border_point_label",
                    "border_point_lat",
                    "border_point_lon",
                    "border_point_distance_km",
                    "border_points_evaluated",
                    "criterion_basis",
                    "base_threshold_dbuv_m",
                    "bandwidth_correction_db",
                    "threshold_dbuv_m",
                    "margin_db",
                    "concern_classification",
                    "coordination_finland_mentioned",
                    "coordination_rows",
                    "priority_score",
                    "tier",
                    "status",
                ]
            )
            for i, f in enumerate(findings, 1):
                writer.writerow(
                    [
                        i,
                        f["notice_id"],
                        f["assignment_id"],
                        f["administration"],
                        f["station_class"],
                        f["site_name"],
                        f["frequency_mhz"],
                        f["bandwidth_khz"],
                        f["change"]["change_type"],
                        f["stage_c_geography"].get("distance_to_finland_km"),
                        f["stage_a_frequency"].get("station_count"),
                        None
                        if f["max_field_strength"] is None
                        else round(f["max_field_strength"], 2),
                        *_border_columns(f),
                        f["priority"]["score"],
                        f["priority"]["tier"],
                        f["finding_status"],
                    ]
                )
        else:
            writer.writerow(
                [
                    "rank",
                    "notice_id",
                    "administration",
                    "notice_type",
                    "satellite",
                    "special_sections",
                    "change",
                    "geometry",
                    "groups",
                    "downlink_groups_on_special_interest_frequencies",
                    "max_pfd_db_w_m2_hz_upper_bound",
                    "priority_score",
                    "tier",
                    "status",
                ]
            )
            for i, f in enumerate(findings, 1):
                writer.writerow(
                    [
                        i,
                        f["notice_id"],
                        f["administration"],
                        f["notice_type"],
                        f["satellite_name"] or f["earth_station_name"],
                        " ".join(f["special_sections"]),
                        f["change"]["change_type"],
                        f["stage_c_geometry"]["status"],
                        f["stage_a_frequency"]["groups"],
                        f["stage_a_frequency"][
                            "downlink_groups_overlapping_special_interest_stations"
                        ],
                        None if f["max_pfd"] is None else round(f["max_pfd"], 2),
                        f["priority"]["score"],
                        f["priority"]["tier"],
                        f["finding_status"],
                    ]
                )


def _report(
    manifest: dict[str, Any],
    findings: list[dict[str, Any]],
    comparison: dict[str, Any],
    trends: dict[str, Any] | None,
    kind: str,
) -> str:
    title = "Space" if kind == I.SPACE_SOURCE_TYPE else "Terrestrial"
    tiers: dict[str, int] = {}
    statuses: dict[str, int] = {}
    for f in findings:
        tiers[f["priority"]["tier"]] = tiers.get(f["priority"]["tier"], 0) + 1
        statuses[f["finding_status"]] = statuses.get(f["finding_status"], 0) + 1
    lines = [
        f"# AstraSync evaluation: {title} IFIC {manifest['issue']}",
        "",
        f"Publication date (from the database): {manifest['publication_date']}. "
        f"Generated {manifest['generated_at_utc']} by rule set `{manifest['rule_version']}`.",
        "",
        "**What this is.** A deterministic screening of every notice in the issue against "
        "Finnish frequency use (M4 table and the challenge's special-interest stations), with "
        "explainable priorities and, where the notice holds the inputs, technical calculations. "
        + (
            "**Criterion.** Land-mobile notices are screened along Finland's land borders and "
            "territorial-sea outer limit with ITU-R P.1546-6 (10 % time, 50 % locations, 10 m) "
            "against the indicative coordination thresholds of ECC T/R 25-08 A1.2.3 (edition 6 "
            "June 2025), applied above 470 MHz as a challenge extension approved by the "
            "organizers. An exceedance indicates coordination with Finland; it is not harmful "
            "interference or non-compliance. Every flagged item needs expert review."
            if kind == I.TERRESTRIAL_SOURCE_TYPE
            else "**What it is not.** No approved space PFD criterion is configured, so nothing "
            "here is a limit exceedance or a statement of harmful interference. Every "
            "high-priority item needs expert review."
        ),
        "",
        "## Inputs",
        "",
        "| Role | File | Bytes | SHA-256 | Source |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in manifest["inputs"]:
        lines.append(
            f"| {item['role']} | `{item['filename']}` | {item['bytes']} | "
            f"`{item['sha256'][:16]}…` | {item['official_url'] or 'challenge platform'} |"
        )
    lines += [
        "",
        "## Parse and reconciliation",
        "",
        "```json",
        json.dumps(manifest["parse_summary"], indent=1),
        "```",
        "",
    ]
    lines += [
        "## Changes against the previous issue",
        "",
        "```json",
        json.dumps({k: v for k, v in comparison.items() if k != "rules"}, indent=1),
        "```",
        "",
        comparison["rules"],
        "",
    ]
    lines += [
        "## Results",
        "",
        f"Notices screened: {len(findings)}. Priority tiers: "
        f"{json.dumps(tiers)}. Statuses: {json.dumps(statuses)}.",
        "",
    ]
    lines += ["### Method and assumptions", ""]
    if kind == I.TERRESTRIAL_SOURCE_TYPE:
        lines += [
            "- Scope: land mobile notices (station classes FB, ML, FL) published in this issue.",
            "- A: overlap with M4 sub-bands and special-interest station intervals "
            "(centre ± half channel). B: Finnish MOBILE / LAND MOBILE allocation in the band. "
            "C: great-circle distance to Finland's boundary. D: P.1546 inputs present.",
            f"- Field strength: ITU-R P.1546-6 (port validated against the ITU-R WP 3K reference "
            f"implementation, 54 cases, max deviation 5.1e-5 dB), "
            f"{manifest['screening_parameters']['terrestrial_time_percent']} % time, "
            f"{manifest['screening_parameters']['terrestrial_location_percent']} % locations, "
            f"receiver {manifest['screening_parameters']['terrestrial_rx_height_m']} m "
            "(or the special-interest station's antenna height), rural, heff = ha (no terrain "
            "data), land/sea zones from Natural Earth, maximum e.r.p. (no antenna pattern).",
        ]
    else:
        lines += [
            "- Scope: every frequency group of every notice published in this issue.",
            "- A: overlap with special-interest station intervals (M4 overlap recorded). B: "
            "downlink in a band where Finland has a terrestrial service; service area FIN. C: GSO "
            "elevation from four Finnish points, or NGSO reach of Finnish latitudes. D: PFD "
            "inputs present.",
            "- PFD: free-space inverse-square (SPACE_PFD_FREE_SPACE) with an **upper bound** "
            "e.i.r.p. density: notified maximum power density + maximum beam gain, as if the "
            "beam peak pointed at Finland, at the minimum slant range. Result per 1 Hz.",
        ]
    high, medium = A.TIER_THRESHOLDS["SPACE" if kind == I.SPACE_SOURCE_TYPE else "TERRESTRIAL"]
    lines += [
        "- Priority score components are listed per finding in `findings.json.gz`; tiers: "
        f"HIGH ≥ {high}, MEDIUM ≥ {medium}. Priority is for ordering expert work; it is "
        "not a statement of concern.",
        "",
        "### Highest-priority items",
        "",
    ]
    for f in findings[:25]:
        lines.append(_explain(f, kind))
    flagged = [f for f in findings if f.get("data_quality_anomaly_count")]
    if flagged:
        lines += [
            "",
            "## Data-quality anomalies in published notices",
            "",
            "Values that cannot be right as published (for example a maximum power "
            "density above the carrier's peak power). They are excluded from calculations "
            "and are candidates for a request for clarification to the notifying "
            "administration.",
            "",
        ]
        for f in flagged:
            for anomaly in f["data_quality_anomalies"][:3]:
                lines.append(
                    f"- {f['administration']} {f['satellite_name'] or f['notice_id']} "
                    f"(notice `{f['notice_id']}`), group {anomaly['group_id']}, "
                    f"{anomaly['emission']}: {anomaly['rule']} — pwr_ds_max "
                    f"{anomaly['pwr_ds_max_dbw_hz']} dBW/Hz, pwr_ds_min "
                    f"{anomaly['pwr_ds_min_dbw_hz']} dBW/Hz, pep_max "
                    f"{anomaly['pep_max_dbw']} dBW."
                )
    if trends:
        lines += [
            "",
            "## Neighbouring administrations: activity",
            "",
            trends["definition"],
            "",
            "| Administration | Dimension | Value | This issue | Previous |",
            "| --- | --- | --- | ---: | ---: |",
        ]
        for o in trends["observations"][:60]:
            lines.append(
                f"| {o['administration']} | {o['dimension']} | {o['value']} | "
                f"{o['notices_this_issue']} | {o['notices_previous_issue']} |"
            )
    lines += [
        "",
        "## Limitations",
        "",
        "- Terrestrial criterion: ECC T/R 25-08 A1.2.3 coordination thresholds (normative "
        "29.7-470 MHz; above 470 MHz a challenge extension). Bandwidth correction assumes a "
        "uniform spectral power distribution. The 1 % time variant for digital systems "
        "(footnote 2) is not applied. No 10 m to 3 m receiving-height correction (organizers: "
        "not required).",
        "- Boundaries: Natural Earth 1:10m land borders and the Traficom territorial-sea limit "
        "(WFS); screening geometry, not legal boundaries. The territorial-sea layer ends near "
        "65.5 N in the Bay of Bothnia.",
        "- Space: no approved PFD criterion; RR Article 21 Table 21-4 values must be entered "
        "from the authoritative edition before comparison.",
        "- Special-interest stations are synthetic challenge data.",
        "- Terrestrial: no terrain database (heff = ha, no clearance-angle correction); "
        "antenna patterns are not applied, so values are for the direction of maximum "
        "radiation.",
        "- Space: PFD values are upper bounds, not predictions; antenna patterns, pointing, "
        "power control and EPFD aggregation are not modelled.",
        "- Space field meanings follow the SNS v9.1 data dictionary; ITU publishes no v10 "
        "dictionary.",
        "",
    ]
    return "\n".join(lines)


def _explain(f: dict[str, Any], kind: str) -> str:
    p = f["priority"]
    reasons = ", ".join(k for k, v in p["components"].items() if v)
    if kind == I.TERRESTRIAL_SOURCE_TYPE:
        geo_part = f["stage_c_geography"].get("distance_to_finland_km")
        best = max(f["calculations"], key=lambda c: c["numeric_value"], default=None)
        calc = (
            f"{best['numeric_value']:.1f} dB(µV/m) at {best['receiver']} "
            f"(P.1546-6, {best['inputs']['distance_km']:.1f} km)"
            if best
            else "no calculation"
        )
        return (
            f"- **{f['administration']} {f['station_class']} {f['site_name']}** — notice "
            f"`{f['notice_id']}` (assignment {f['assignment_id']}, "
            f"{', '.join(f['publications'] or [])}), {f['frequency_mhz']} MHz / "
            f"{f['bandwidth_khz']} kHz, {f['change']['change_type']}; {geo_part} km from "
            f"Finland; {f['stage_a_frequency'].get('station_count', 0)} special-interest "
            f"overlaps; {calc}. Score {p['score']} ({p['tier']}): {reasons}. "
            f"Status {f['finding_status']}."
        )
    pfd = (
        f"{f['max_pfd']:.1f} dB(W/m²) in 1 Hz upper bound" if f["max_pfd"] is not None else "no PFD"
    )
    return (
        f"- **{f['administration']} {f['satellite_name'] or f['earth_station_name']}** — "
        f"notice `{f['notice_id']}` ({f['notice_type']}, {' '.join(f['special_sections'])}), "
        f"{f['change']['change_type']}; geometry {f['stage_c_geometry']['status']}; "
        f"{f['stage_a_frequency']['downlink_groups_overlapping_special_interest_stations']} "
        f"downlink groups on special-interest frequencies; {pfd}. Score {p['score']} "
        f"({p['tier']}): {reasons}. Status {f['finding_status']}."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("kind", choices=["space", "terrestrial"])
    parser.add_argument("--issue", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--m4", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    kind = I.SPACE_SOURCE_TYPE if args.kind == "space" else I.TERRESTRIAL_SOURCE_TYPE
    print(json.dumps(evaluate(kind, args.issue, args.previous, args.m4, args.workbook, args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
