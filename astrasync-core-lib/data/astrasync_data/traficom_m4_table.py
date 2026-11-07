"""Parser for Traficom's open-data frequency allocation table (`Taajuusjakotaulukko`, API v13).

Source: https://opendata.traficom.fi/api/v13/Taajuusjakotaulukko, an OData JSON document.
Licence: Creative Commons BY 4.0, as stated in the API's own OpenAPI document; attribute
Traficom when showing or exporting the data.

This is the machine-readable table of frequencies in Finland that belongs to Regulation M4. The
API does not state which M4 edition a snapshot reflects, so none is assumed here. Record the
retrieval time and ETag beside the artifact.

Rules:
- The field set must match API v13 exactly. A changed schema, or a paged (incomplete) response,
  is refused rather than partly read.
- Band limits come from the numeric Hz fields. The text limits ("8.3 kHz") are checked against
  them and any disagreement is flagged, never silently resolved.
- `Transmitter_power` is an integer that the API sets to 0 when nothing is given, so 0 means
  unknown here, and the field is kept as raw text only.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from . import units

SOURCE_TYPE = "M4_ALLOCATION"
PARSER_VERSION = "traficom-opendata-taajuusjakotaulukko/1.0.0"
SCHEMA_VERSION = "traficom-opendata/v13/Taajuusjakotaulukko"
TABLE = "Taajuusjakotaulukko"
ODATA_CONTEXT = "https://opendata.traficom.fi/OpenData/api/v13/$metadata#Taajuusjakotaulukko"
MAX_BYTES = 256 * 1024 * 1024
ADMINISTRATION = "FIN"  # The national table of Finland.

FIELDS = (
    "ID",
    "Frequency_band_lower_limit",
    "Frequency_band_upper_limit",
    "Services_in_Finland",
    "Additional_information",
    "Sub_band_lower_limit",
    "Sub_band_upper_limit",
    "Sub_band_lower_limit__Hz_",
    "Sub_band_upper_limit__Hz_",
    "Sub_band_width",
    "Sub_band_usage",
    "Mode_of_traffic",
    "Class_of_station",
    "Direction",
    "Radiated_power",
    "Transmitter_power",
    "Channel_spacing",
    "Bandwidth",
    "Duplex_separation",
    "Duplex_band_lower_limit",
    "Duplex_band_upper_limit",
    "Class_of_emission",
    "Standard_type",
    "Comment",
)
FIELD_ALIASES = {name: [name] for name in FIELDS}
# A text limit and its Hz value may differ by rounding in the text, never by more than this.
TEXT_TOLERANCE_HZ = 0.5


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


class TraficomM4TableAdapter:
    """``SourceAdapter`` for one snapshot of the allocation table."""

    source_type = SOURCE_TYPE
    parser_version = PARSER_VERSION

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        if artifact_path.stat().st_size > MAX_BYTES:
            raise ValueError("Larger than any expected table snapshot")
        try:
            document = json.loads(artifact_path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Not a JSON document") from exc
        rows = _rows(document)
        batch: list[dict[str, Any]] = []
        for row in rows:
            batch.append(parse_row(row))
            if len(batch) >= batch_rows:
                yield batch
                batch = []
        if batch:
            yield batch


def _rows(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or document.get("@odata.context") != ODATA_CONTEXT:
        raise ValueError("Not the Taajuusjakotaulukko v13 response")
    if "@odata.nextLink" in document:
        raise ValueError("Paged response: this snapshot is incomplete")
    rows = document.get("value")
    if not isinstance(rows, list):
        raise ValueError("No value list")
    ids: set[Any] = set()
    for row in rows:
        if not isinstance(row, dict) or tuple(row) != FIELDS:
            raise ValueError("A row does not have the v13 field set")
        if row["ID"] in ids:
            raise ValueError("Repeated row ID")
        ids.add(row["ID"])
    return rows


def parse_row(row: dict[str, Any]) -> dict[str, Any]:
    raw = {name: _text(row[name]) for name in FIELDS}
    findings: list[dict[str, Any]] = []

    def flag(key: str, rule_id: str, severity: str, normalized: float | None = None) -> None:
        findings.append(
            {
                "field_key": key,
                "raw_value": raw.get(key),
                "normalized_value": None if normalized is None else str(normalized),
                "rule_id": rule_id,
                "severity": severity,
            }
        )

    limits: dict[str, float | None] = {}
    for side in ("lower", "upper"):
        key = f"Sub_band_{side}_limit__Hz_"
        value = row[key]
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            flag(key, "UNPARSEABLE_VALUE", "BLOCKING")
            limits[side] = None
            continue
        limits[side] = float(value)
        text_key = f"Sub_band_{side}_limit"
        from_text = units.frequency_hz(raw[text_key])
        if from_text.value is None:
            flag(text_key, from_text.rule_id or "UNPARSEABLE_VALUE", "WARNING")
        elif abs(from_text.value - float(value)) > TEXT_TOLERANCE_HZ:
            flag(text_key, "TEXT_AND_HZ_LIMITS_DISAGREE", "WARNING", from_text.value)

    lower, upper = limits["lower"], limits["upper"]
    if lower is not None and upper is not None and lower > upper:
        flag("Sub_band_lower_limit__Hz_", "LOWER_LIMIT_ABOVE_UPPER", "BLOCKING", lower)
        lower = upper = None

    blocking = any(f["severity"] == "BLOCKING" for f in findings)
    warning = any(f["severity"] == "WARNING" for f in findings)
    status = "REVIEW_REQUIRED" if blocking else "VALID_WITH_WARNINGS" if warning else "VALID"
    return {
        "source_table_or_sheet": TABLE,
        "source_row_or_key": raw["ID"],
        "source_page": None,
        "notice_id": None,
        "issue_key": None,
        "station_number": None,
        "network_id": None,
        "administration": ADMINISTRATION,
        "frequency_start_mhz": None if lower is None else lower / 1e6,
        "frequency_end_mhz": None if upper is None else upper / 1e6,
        "record_status": status,
        "schema_version": SCHEMA_VERSION,
        "raw_fields": raw,
        "field_aliases": FIELD_ALIASES,
        "analysis_eligibility": {
            "FINLAND_ALLOCATION_LOOKUP": "REVIEW_REQUIRED" if blocking else "VALID"
        },
        "quality_findings": findings,
        "reference_station": None,
    }
