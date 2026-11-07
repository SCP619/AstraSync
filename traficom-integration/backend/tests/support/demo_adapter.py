"""Test-only ``SourceAdapter`` for a made-up format, to exercise the pipeline around a parser.

NOT the Traficom workbook parser and not a pattern for one: real source parsing, including units,
belongs to the Data/AI contributor. Its one unit rule exists to carry a flagged record end to end.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

FORMAT_HEADER = "DEMO-SYNTHETIC-FORMAT,1"
COLUMNS = ("station", "tx_frequency", "power")


class DemoAdapter:
    source_type = "CHALLENGE_SYNTHETIC_REFERENCE"
    parser_version = "demo-adapter/1"

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        with artifact_path.open(encoding="utf-8") as lines:
            if lines.readline().strip() != FORMAT_HEADER:
                raise ValueError("Not the demo format")
            batch: list[dict[str, Any]] = []
            for row, line in enumerate(lines, start=2):
                batch.append(self._record(row, line.rstrip("\n").split(",")))
                if len(batch) >= batch_rows:
                    yield batch
                    batch = []
            if batch:
                yield batch

    def _record(self, row: int, cells: list[str]) -> dict[str, Any]:
        raw = dict(zip(COLUMNS, cells, strict=False))
        frequency = raw.get("tx_frequency", "")
        findings: list[dict[str, Any]] = []
        mhz = None
        if frequency.endswith(" MHz"):
            mhz = float(frequency.removesuffix(" MHz"))
        else:
            findings.append(
                {
                    "field_key": "tx_frequency",
                    "raw_value": frequency,
                    "normalized_value": None,
                    "rule_id": "UNIT_UNSPECIFIED",
                    "severity": "BLOCKING",
                }
            )
        status = "REVIEW_REQUIRED" if findings else "VALID"
        return {
            "source_table_or_sheet": "demo-sheet",
            "source_row_or_key": str(row),
            "source_page": None,
            "notice_id": None,
            "issue_key": "DEMO-ISSUE-1",
            "station_number": raw.get("station"),
            "network_id": None,
            "administration": "DEMO",
            "frequency_start_mhz": mhz,
            "frequency_end_mhz": mhz,
            "record_status": status,
            "schema_version": "demo/1",
            "raw_fields": raw,
            "field_aliases": {"tx_frequency": ["TX frequency"]},
            "analysis_eligibility": {"DEMO_METHOD": "INSUFFICIENT_DATA" if findings else "VALID"},
            "quality_findings": findings,
            "reference_station": {
                "station_number_raw": raw.get("station"),
                "licence_class_code": None,
                "longitude_deg": None,
                "latitude_deg": None,
                "ground_elevation_m": None,
                "mast_height_m": None,
                "antenna_height_agl_m": None,
                "antenna_height_asl_m": None,
                "antenna_gain_db": None,
                "tx_frequency_hz": mhz * 1e6 if mhz else None,
                "rx_frequency_hz": None,
                "channel_bandwidth_hz": None,
                "emission_bandwidth_hz": None,
                "polarization_code": None,
                "radiation_power_value": None,
                "radiation_power_unit": None,
                "radiation_power_itu_code_raw": raw.get("power"),
                "transmission_line_db": None,
                "directivity_code": None,
            },
        }
