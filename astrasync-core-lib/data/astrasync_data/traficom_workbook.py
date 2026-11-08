"""Parser for the Traficom challenge workbook `Frequencies of interest` (version 05112026).

The workbook is synthetic, non-real reference data supplied for the Since AI 2026 challenge. It is
not an ITU IFIC issue and not the national M4 allocation. Mapping follows
`docs/architecture/SYNTHETIC_DATA_ALIGNMENT.md`, except where the workbook itself differs, as
recorded in `traficom-integration/contract/DECISIONS.md` (D-PARSE-*).

Rules:
- Headers are matched exactly, including the source's own spelling (`Radioation power`). A
  workbook with different headers is refused rather than mapped by position.
- Every original cell is kept as text. Normalized values are null when unknown: a missing value is
  never zero, and a number without a unit never gets a guessed unit.
- Implausible values (a negative antenna height) are kept as given, flagged and excluded from
  calculations. No correction or "minimum 1 m" scenario is applied here.
"""

from collections.abc import Iterator
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from . import units

SOURCE_TYPE = "CHALLENGE_SYNTHETIC_REFERENCE"
PARSER_VERSION = "traficom-frequencies-of-interest/1.0.0"
SCHEMA_VERSION = "traficom-frequencies-of-interest/v05112026"
SHEET = "Frequencies of interest"

# (key, English header in row N, Finnish header in row N+1), in column order.
COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("station_number", "Station number", "Asemanro"),
    ("licence_class", "Class of licence", "Lupalaji"),
    ("longitude", "Longitude", "Longitudi"),
    ("latitude", "Latitude", "Latitudi"),
    ("ground_height_m", "Ground height (m)", "Maankork (m)"),
    ("mast_height_m", "Mast height (m)", "Mastonkork (m)"),
    ("mast_type", "Mast type", "Mastotyyppi"),
    ("channel_bandwidth", "Channel bandwidth", "Kan.lev."),
    ("tx_frequency", "TX frequency", "TX-taajuus"),
    ("rx_frequency", "RX frequency", "RX-taajuus"),
    ("antenna_height_agl_m", "Ant height AGL (m)", "Ant.kork.maa (m)"),
    ("antenna_height_asl_m", "Ant height ASL (m)", "Ant.kork.meri (m)"),
    ("antenna_gain_db", "Ant gain (dB)", "Ant.vahv (dB)"),
    ("transmission_class", "Class of transmission", "Läheteluokka"),
    ("transmission_bandwidth", "Transmission bandwidth", "Lähetteen leveys"),
    ("radiation_direction_deg", "Radiation direction (°)", "Max.sät.suunta (°)"),
    ("polarisation", "Polarisation", "Polarisaatio"),
    ("radiation_power", "Radioation power", "Sät.teho"),
    ("radiation_power_itu", "Radioation power (ITU)", "Sät.teho (ITU)"),
    ("radiation_power_unit", "Radiation power unit", "Sät.teh.yks."),
    ("transmission_line_db", "Transmission line (dB)", "Siirtolinja (dB)"),
    ("directivity", "Directivity", "Suunnattavuus"),
)
ENGLISH = tuple(english for _, english, _ in COLUMNS)
FINNISH = tuple(finnish for _, _, finnish in COLUMNS)
KEYS = tuple(key for key, _, _ in COLUMNS)
FIELD_ALIASES = {key: [english, finnish] for key, english, finnish in COLUMNS}
HEADER_SEARCH_ROWS = 30

POWER_UNITS = frozenset({"mW", "W", "kW", "MW"})
# A coarse screen only: passing it does not show a point is inside Finland.
COARSE_FINLAND_BOX = {"lon": (19.0, 32.0), "lat": (59.0, 71.0)}

# Severity when a field is missing; None means a blank is unremarkable for that field.
MISSING_SEVERITY = {
    "station_number": "WARNING",
    "licence_class": "INFO",
    "longitude": "WARNING",
    "latitude": "WARNING",
    "tx_frequency": "BLOCKING",
    "rx_frequency": "INFO",
    "channel_bandwidth": "WARNING",
    "transmission_bandwidth": "WARNING",
    "antenna_height_agl_m": "WARNING",
    "antenna_gain_db": "INFO",
    "radiation_power": "INFO",
}


def cell_text(value: Any) -> str | None:
    """The cell as the text a person would read, so the original survives normalization."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, float) and value.is_integer():
        return repr(value)  # Keeps `12.0` distinct from an integer cell `12`.
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return str(value)


class TraficomWorkbookAdapter:
    """``SourceAdapter`` for the challenge workbook. Streams rows, so memory stays bounded."""

    source_type = SOURCE_TYPE
    parser_version = PARSER_VERSION

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        # A file handle, because stored artifacts have no `.xlsx` name for openpyxl to check.
        handle = artifact_path.open("rb")
        try:
            workbook = load_workbook(handle, read_only=True, data_only=True)
        except Exception as exc:  # noqa: BLE001 - any unreadable file is quarantined.
            handle.close()
            raise ValueError("Not a readable XLSX workbook") from exc
        try:
            if SHEET not in workbook.sheetnames:
                raise ValueError(f"Worksheet {SHEET!r} not found")
            sheet = workbook[SHEET]
            rows = sheet.iter_rows(values_only=True)
            header_row = _find_header(rows)
            batch: list[dict[str, Any]] = []
            for excel_row, cells in enumerate(rows, start=header_row + 2):
                if all(cell_text(c) in (None, "") for c in cells):
                    continue  # Blank rows are layout, not records.
                batch.append(parse_row(excel_row, cells))
                if len(batch) >= batch_rows:
                    yield batch
                    batch = []
            if batch:
                yield batch
        finally:
            workbook.close()
            handle.close()


def _find_header(rows: Iterator[tuple[Any, ...]]) -> int:
    """Consumes rows through the Finnish alias row; returns the English header's row number."""
    for number in range(1, HEADER_SEARCH_ROWS + 1):
        cells = next(rows, None)
        if cells is None:
            break
        if tuple(cell_text(c) for c in cells[: len(ENGLISH)]) == ENGLISH:
            aliases = next(rows, ())
            if tuple(cell_text(c) for c in aliases[: len(FINNISH)]) != FINNISH:
                raise ValueError(f"Row {number + 1} is not the expected Finnish header row")
            return number
    raise ValueError("The expected English header row was not found")


class _Row:
    def __init__(self, excel_row: int, raw: dict[str, str | None]) -> None:
        self.excel_row = excel_row
        self.raw = raw
        self.findings: list[dict[str, Any]] = []

    def flag(
        self, key: str, rule_id: str, severity: str, normalized: float | str | None = None
    ) -> None:
        self.findings.append(
            {
                "field_key": key,
                "raw_value": self.raw.get(key),
                "normalized_value": None if normalized is None else str(normalized),
                "rule_id": rule_id,
                "severity": severity,
            }
        )

    def parsed(self, key: str, result: units.Parsed, problem: str = "WARNING") -> float | None:
        """Records why a value is null, at the field's own severity for a blank."""
        if result.value is None:
            if result.rule_id == "MISSING_VALUE":
                severity = MISSING_SEVERITY.get(key)
                if severity is not None:
                    self.flag(key, "MISSING_VALUE", severity)
            elif result.rule_id is not None:
                self.flag(key, result.rule_id, problem)
        elif result.rule_id is not None:
            self.flag(key, result.rule_id, "INFO", result.value)
        return result.value


def parse_row(excel_row: int, cells: tuple[Any, ...]) -> dict[str, Any]:
    """One worksheet row as an ``AdapterRecord`` dictionary."""
    raw = {key: cell_text(cells[i]) if i < len(cells) else None for i, key in enumerate(KEYS)}
    row = _Row(excel_row, raw)
    for extra, value in enumerate(cells[len(KEYS) :], start=len(KEYS) + 1):
        if cell_text(value) not in (None, ""):
            row.raw[f"column_{extra}"] = cell_text(value)
            row.flag(f"column_{extra}", "UNMAPPED_COLUMN_VALUE", "WARNING")

    if units.is_blank(raw["station_number"]):
        row.flag("station_number", "MISSING_VALUE", "WARNING")
    if units.is_blank(raw["licence_class"]):
        row.flag("licence_class", "MISSING_VALUE", "INFO")

    longitude = _coordinate(row, "longitude", 180.0)
    latitude = _coordinate(row, "latitude", 90.0)
    if longitude is not None and latitude is not None:
        (lon_min, lon_max), (lat_min, lat_max) = (
            COARSE_FINLAND_BOX["lon"],
            COARSE_FINLAND_BOX["lat"],
        )
        if not (lon_min <= longitude <= lon_max and lat_min <= latitude <= lat_max):
            row.flag("longitude", "OUTSIDE_COARSE_FINLAND_BOX", "WARNING")

    tx_hz = row.parsed("tx_frequency", units.frequency_hz(raw["tx_frequency"]), "BLOCKING")
    rx_hz = row.parsed("rx_frequency", units.frequency_hz(raw["rx_frequency"]))
    channel_hz = row.parsed("channel_bandwidth", units.frequency_hz(raw["channel_bandwidth"]))
    emission_hz = row.parsed(
        "transmission_bandwidth", units.bandwidth_designation_hz(raw["transmission_bandwidth"])
    )

    effective_hz, bandwidth_rule = _effective_bandwidth(row, channel_hz, emission_hz)

    ground_m = row.parsed("ground_height_m", units.number(raw["ground_height_m"]))
    mast_m = row.parsed("mast_height_m", units.number(raw["mast_height_m"]))
    agl_m = row.parsed("antenna_height_agl_m", units.number(raw["antenna_height_agl_m"]))
    asl_m = row.parsed("antenna_height_asl_m", units.number(raw["antenna_height_asl_m"]))
    if agl_m is not None and agl_m < 0:
        row.flag("antenna_height_agl_m", "INVALID_OR_UNREALISTIC_HEIGHT", "BLOCKING", agl_m)
    if asl_m is not None and ground_m is not None and asl_m < ground_m:
        row.flag("antenna_height_asl_m", "ASL_BELOW_GROUND_HEIGHT", "WARNING", asl_m)

    gain_db = row.parsed("antenna_gain_db", units.number(raw["antenna_gain_db"]))
    line_db = row.parsed("transmission_line_db", units.number(raw["transmission_line_db"]))
    direction = row.parsed("radiation_direction_deg", units.number(raw["radiation_direction_deg"]))
    if direction is not None and not 0 <= direction <= 360:
        row.flag("radiation_direction_deg", "OUT_OF_RANGE", "WARNING", direction)

    power, power_unit = _power(row)

    eligibility = {
        "FREQUENCY_SCREENING": _eligible(row, tx_hz, ("tx_frequency",)),
        "POWER_DEPENDENT_CALCULATION": _eligible(
            row,
            None if None in (tx_hz, power, longitude, latitude, agl_m) else 1.0,
            ("tx_frequency", "radiation_power", "antenna_height_agl_m", "longitude", "latitude"),
        ),
        "GAIN_DEPENDENT_CALCULATION": _eligible(
            row,
            None if None in (tx_hz, power, gain_db, longitude, latitude, agl_m) else 1.0,
            ("tx_frequency", "radiation_power", "antenna_height_agl_m", "antenna_gain_db"),
        ),
    }

    status = _status(row.findings) or (
        "VALID_WITH_WARNINGS" if any(f["severity"] == "WARNING" for f in row.findings) else "VALID"
    )

    tx_mhz = tx_hz / 1e6 if tx_hz is not None else None
    return {
        "source_table_or_sheet": SHEET,
        "source_row_or_key": str(excel_row),
        "source_page": None,
        "notice_id": None,
        "issue_key": None,
        "station_number": None if units.is_blank(raw["station_number"]) else raw["station_number"],
        "network_id": None,
        "administration": None,
        # The TX centre frequency only; any interval around it would be a labelled assumption.
        "frequency_start_mhz": tx_mhz,
        "frequency_end_mhz": tx_mhz,
        "record_status": status,
        "schema_version": SCHEMA_VERSION,
        "raw_fields": row.raw,
        "field_aliases": FIELD_ALIASES,
        "analysis_eligibility": eligibility,
        "quality_findings": row.findings,
        "reference_station": {
            "station_number_raw": raw["station_number"],
            "licence_class_code": _code(raw["licence_class"]),
            "licence_class_normalized": _licence_class(raw["licence_class"]),
            "longitude_deg": longitude,
            "latitude_deg": latitude,
            "ground_elevation_m": ground_m,
            "mast_height_m": mast_m,
            "antenna_height_agl_m": agl_m,
            "antenna_height_asl_m": asl_m,
            "antenna_gain_db": gain_db,
            "tx_frequency_hz": tx_hz,
            "rx_frequency_hz": rx_hz,
            "channel_bandwidth_hz": channel_hz,
            "emission_bandwidth_hz": emission_hz,
            "effective_bandwidth_hz": effective_hz,
            "effective_bandwidth_rule": bandwidth_rule,
            "polarization_code": _code(raw["polarisation"]),
            "radiation_power_value": power,
            "radiation_power_unit": power_unit,
            "radiation_power_itu_code_raw": _code(raw["radiation_power_itu"]),
            "transmission_line_db": line_db,
            "directivity_code": _code(raw["directivity"]),
        },
    }


# Licence classes kept as published; anything else (or blank) screens as MUUT ("others"), with the
# original value preserved in ``licence_class_code`` and ``raw_fields``. Organizer guidance: the
# licence class is not the key field for relevance (docs/TRAFICOM_CHALLENGE_CLARIFICATIONS.md, C2).
KNOWN_LICENCE_CLASSES = frozenset({"BC", "BT", "FX", "MVV", "MUUT"})
# Channel and transmission bandwidths that differ by more than this are a data-quality mismatch.
BANDWIDTH_MISMATCH_TOLERANCE = 0.01


def _licence_class(raw: str | None) -> str:
    code = _code(raw)
    return code if code in KNOWN_LICENCE_CLASSES else "MUUT"


def _effective_bandwidth(
    row: _Row, channel_hz: float | None, emission_hz: float | None
) -> tuple[float | None, str | None]:
    """Screening bandwidth, stored beside (never over) the raw channel and transmission widths.

    Organizer clarification C3/C4: the workbook has transcription errors (station 440557: 2500 kHz
    channel, 118600k transmission); where the two disagree the smaller valid value is used. For
    the BC 9 kHz / 10 kHz pairs this selects the 9 kHz European broadcast channel. This is not an
    occupied, regulatory-reference or receiver bandwidth; those are handled by the RF methods.
    """
    values = [v for v in (channel_hz, emission_hz) if v is not None and v > 0]
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], (
            "CHANNEL_BANDWIDTH_ONLY" if channel_hz is not None else "TRANSMISSION_BANDWIDTH_ONLY"
        )
    if abs(values[0] - values[1]) <= BANDWIDTH_MISMATCH_TOLERANCE * max(values):
        return values[0], "CONSISTENT"
    smaller = min(values)
    row.flag("transmission_bandwidth", "BANDWIDTH_MISMATCH", "WARNING", smaller)
    return smaller, "MISMATCH_SMALLER_VALID_VALUE"


def _status(findings: list[dict[str, Any]]) -> str | None:
    """For blocking findings: missing inputs are insufficient data; anything else needs review."""
    blocking = [f for f in findings if f["severity"] == "BLOCKING"]
    if not blocking:
        return None
    if all(f["rule_id"] == "MISSING_VALUE" for f in blocking):
        return "INSUFFICIENT_DATA"
    return "REVIEW_REQUIRED"


def _code(raw: str | None) -> str | None:
    return None if units.is_blank(raw) else raw


def _coordinate(row: _Row, key: str, limit: float) -> float | None:
    value = row.parsed(key, units.number(row.raw[key]))
    if value is not None and not -limit <= value <= limit:
        row.flag(key, "OUT_OF_RANGE", "BLOCKING", value)
        return None
    return value


def _power(row: _Row) -> tuple[float | None, str | None]:
    """The source's power figure in its own unit. Whether it is ERP or EIRP is not stated."""
    value = row.parsed("radiation_power", units.number(row.raw["radiation_power"]))
    unit = _code(row.raw["radiation_power_unit"])
    if value is None:
        return None, unit
    if unit is None or unit.strip() not in POWER_UNITS:
        row.flag("radiation_power_unit", "UNIT_UNSPECIFIED", "WARNING")
        return None, unit
    if value <= 0:
        row.flag("radiation_power", "NON_POSITIVE_VALUE", "WARNING", value)
        return None, unit
    return value, unit.strip()


def _eligible(row: _Row, needed: float | None, keys: tuple[str, ...]) -> str:
    status = _status([f for f in row.findings if f["field_key"] in keys])
    if status is not None:
        return status
    return "VALID" if needed is not None else "INSUFFICIENT_DATA"
