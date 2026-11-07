"""Parser tests on a small made-up workbook that copies the challenge workbook's layout.

All values here are invented for the test. The real file is checked in test_traficom_golden.py.
"""

from pathlib import Path
from typing import Any

import pytest
from astrasync_data.traficom_workbook import (
    ENGLISH,
    FINNISH,
    SHEET,
    TraficomWorkbookAdapter,
    parse_row,
)
from openpyxl import Workbook

ROW = {
    "Station number": 9001,
    "Class of licence": "BC",
    "Longitude": "24.50000",
    "Latitude": "60.50000",
    "Ground height (m)": 40,
    "Mast height (m)": 100,
    "Mast type": "KIINTEÄ",
    "Channel bandwidth": "300.000 kHz",
    "TX frequency": "90.000 MHz",
    "RX frequency": "90.000 MHz",
    "Ant height AGL (m)": 80,
    "Ant height ASL (m)": 120,
    "Ant gain (dB)": 6.5,
    "Class of transmission": "F9EHF",
    "Transmission bandwidth": "300k",
    "Radiation direction (°)": 90,
    "Polarisation": "H",
    "Radioation power": 10,
    "Radioation power (ITU)": "E",
    "Radiation power unit": "kW",
    "Transmission line (dB)": "0.0",
    "Directivity": "ND",
}


def cells(**changes: Any) -> tuple[Any, ...]:
    row = {**ROW, **changes}
    return tuple(row[h] for h in ENGLISH)


def write_workbook(path: Path, data: list[tuple[Any, ...]], *, header: tuple[str, ...] = ENGLISH):
    book = Workbook()
    sheet = book.active
    sheet.title = SHEET
    sheet.append(["Made-up test workbook"])
    for _ in range(9):
        sheet.append([])
    sheet.append(list(header))
    sheet.append(list(FINNISH))
    for row in data:
        sheet.append(list(row))
    book.save(path)


def records(path: Path, batch_rows: int = 100) -> list[dict[str, Any]]:
    return [
        r
        for batch in TraficomWorkbookAdapter().iter_record_batches(path, batch_rows=batch_rows)
        for r in batch
    ]


def finding(record: dict[str, Any], rule_id: str) -> dict[str, Any]:
    matches = [f for f in record["quality_findings"] if f["rule_id"] == rule_id]
    assert matches, f"{rule_id} not in {record['quality_findings']}"
    return matches[0]


def test_reads_rows_after_the_two_header_rows_and_keeps_excel_row_numbers(tmp_path: Path) -> None:
    path = tmp_path / "book.xlsx"
    write_workbook(path, [cells(), (None,) * 22, cells(**{"Station number": 9002})])
    parsed = records(path, batch_rows=1)
    assert [r["source_row_or_key"] for r in parsed] == ["13", "15"]  # The blank row is skipped.
    assert parsed[0]["source_table_or_sheet"] == SHEET
    assert parsed[0]["field_aliases"]["tx_frequency"] == ["TX frequency", "TX-taajuus"]
    assert parsed[0]["field_aliases"]["radiation_power"] == ["Radioation power", "Sät.teho"]


def test_a_clean_row_is_normalized_with_explicit_units(tmp_path: Path) -> None:
    record = parse_row(13, cells())
    assert record["record_status"] == "VALID"
    assert record["quality_findings"] == [
        {
            "field_key": "transmission_bandwidth",
            "raw_value": "300k",
            "normalized_value": "300000.0",
            "rule_id": "NON_STANDARD_BANDWIDTH_DESIGNATION",
            "severity": "INFO",
        }
    ]
    station = record["reference_station"]
    assert station["tx_frequency_hz"] == pytest.approx(90e6)
    assert station["channel_bandwidth_hz"] == pytest.approx(300e3)
    assert station["emission_bandwidth_hz"] == pytest.approx(300e3)
    assert (station["longitude_deg"], station["latitude_deg"]) == (24.5, 60.5)
    assert (station["radiation_power_value"], station["radiation_power_unit"]) == (10, "kW")
    assert record["frequency_start_mhz"] == record["frequency_end_mhz"] == pytest.approx(90.0)
    assert record["raw_fields"]["station_number"] == "9001"
    assert record["raw_fields"]["mast_type"] == "KIINTEÄ"
    assert set(record["analysis_eligibility"].values()) == {"VALID"}


def test_a_missing_tx_frequency_blocks_frequency_work_but_keeps_the_row() -> None:
    record = parse_row(108, cells(**{"TX frequency": ""}))
    assert record["record_status"] == "INSUFFICIENT_DATA"
    assert finding(record, "MISSING_VALUE")["field_key"] == "tx_frequency"
    assert record["reference_station"]["tx_frequency_hz"] is None
    assert record["frequency_start_mhz"] is None
    assert record["analysis_eligibility"]["FREQUENCY_SCREENING"] == "INSUFFICIENT_DATA"


def test_a_frequency_without_a_unit_is_not_guessed() -> None:
    record = parse_row(13, cells(**{"TX frequency": "26"}))
    assert finding(record, "UNIT_UNSPECIFIED")["severity"] == "BLOCKING"
    assert record["reference_station"]["tx_frequency_hz"] is None
    assert record["record_status"] == "REVIEW_REQUIRED"
    assert record["analysis_eligibility"]["FREQUENCY_SCREENING"] == "REVIEW_REQUIRED"


def test_a_negative_antenna_height_is_kept_flagged_and_excluded() -> None:
    record = parse_row(108, cells(**{"Ant height AGL (m)": -28}))
    flag = finding(record, "INVALID_OR_UNREALISTIC_HEIGHT")
    assert (flag["severity"], flag["raw_value"]) == ("BLOCKING", "-28")
    assert record["reference_station"]["antenna_height_agl_m"] == -28  # Original, not corrected.
    assert record["analysis_eligibility"]["FREQUENCY_SCREENING"] == "VALID"
    assert record["analysis_eligibility"]["POWER_DEPENDENT_CALCULATION"] == "REVIEW_REQUIRED"
    assert record["record_status"] == "REVIEW_REQUIRED"


def test_missing_power_and_gain_are_null_not_zero() -> None:
    record = parse_row(
        13,
        cells(**{"Radioation power": None, "Radiation power unit": None, "Ant gain (dB)": ""}),
    )
    station = record["reference_station"]
    assert station["radiation_power_value"] is None
    assert station["antenna_gain_db"] is None
    assert record["analysis_eligibility"]["POWER_DEPENDENT_CALCULATION"] == "INSUFFICIENT_DATA"
    assert record["analysis_eligibility"]["GAIN_DEPENDENT_CALCULATION"] == "INSUFFICIENT_DATA"
    assert record["record_status"] == "VALID"  # Missing optional inputs are noted, not errors.
    assert {f["rule_id"] for f in record["quality_findings"]} >= {"MISSING_VALUE"}


def test_power_with_an_unknown_unit_is_not_used() -> None:
    record = parse_row(13, cells(**{"Radiation power unit": "dBW"}))
    assert finding(record, "UNIT_UNSPECIFIED")["field_key"] == "radiation_power_unit"
    assert record["reference_station"]["radiation_power_value"] is None


def test_physical_consistency_and_location_warnings() -> None:
    record = parse_row(13, cells(**{"Ant height ASL (m)": 10, "Longitude": "35.00000"}))
    assert finding(record, "ASL_BELOW_GROUND_HEIGHT")["severity"] == "WARNING"
    assert finding(record, "OUTSIDE_COARSE_FINLAND_BOX")["severity"] == "WARNING"
    assert record["record_status"] == "VALID_WITH_WARNINGS"


def test_an_impossible_coordinate_is_refused() -> None:
    record = parse_row(13, cells(**{"Latitude": "95.0"}))
    assert finding(record, "OUT_OF_RANGE")["field_key"] == "latitude"
    assert record["reference_station"]["latitude_deg"] is None


def test_values_in_unmapped_columns_are_kept_and_flagged() -> None:
    record = parse_row(13, (*cells(), None, "surprise"))
    assert record["raw_fields"]["column_24"] == "surprise"
    assert finding(record, "UNMAPPED_COLUMN_VALUE")["severity"] == "WARNING"


def test_a_workbook_with_other_headers_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "renamed.xlsx"
    corrected = tuple("Radiation power" if h == "Radioation power" else h for h in ENGLISH)
    write_workbook(path, [cells()], header=corrected)
    with pytest.raises(ValueError, match="header row"):
        records(path)


def test_a_file_that_is_not_a_workbook_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "not.xlsx"
    path.write_bytes(b"station,frequency\n1,2\n")
    with pytest.raises(ValueError, match="readable XLSX"):
        records(path)


def test_records_satisfy_the_backend_contract(tmp_path: Path) -> None:
    contract = pytest.importorskip("astrasync_api.contract.models")
    path = tmp_path / "book.xlsx"
    write_workbook(
        path,
        [
            cells(),
            cells(**{"TX frequency": "", "Ant height AGL (m)": -28}),
            cells(**{"TX frequency": "26"}),
        ],
    )
    for record in records(path):
        validated = contract.AdapterRecord.model_validate(record)
        contract.ReferenceStationRecord.model_validate(
            {
                **validated.reference_station,
                "source_record_id": "TEST-1",
                "is_synthetic": True,
                "parse_status": validated.record_status,
            }
        )
