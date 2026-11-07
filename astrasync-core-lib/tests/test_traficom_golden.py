"""Golden test against the real challenge workbook, which is never committed to git.

Set ASTRASYNC_TRAFICOM_WORKBOOK to its path. Without it this test is skipped, and CI reports it as
skipped rather than passed. Expected figures were read from the workbook itself; where they differ
from the v3 audit, see DECISIONS.md D-PARSE-001.
"""

import hashlib
import os
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from astrasync_data.traficom_workbook import TraficomWorkbookAdapter

WORKBOOK = os.environ.get("ASTRASYNC_TRAFICOM_WORKBOOK")
PUBLISHED_SHA256 = "bb7f481f085fb6c457efc04b9b6bb8250c42ea81bab4b4a0e518c93834e03c8a"

pytestmark = pytest.mark.skipif(not WORKBOOK, reason="ASTRASYNC_TRAFICOM_WORKBOOK not set")


@pytest.fixture(scope="module")
def parsed() -> dict[int, dict[str, Any]]:
    assert WORKBOOK
    path = Path(WORKBOOK)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == PUBLISHED_SHA256
    batches = TraficomWorkbookAdapter().iter_record_batches(path, batch_rows=250)
    return {int(r["source_row_or_key"]): r for batch in batches for r in batch}


def rows_with(parsed: dict[int, dict[str, Any]], key: str, rule_id: str) -> list[int]:
    return sorted(
        row
        for row, record in parsed.items()
        if any(
            f["field_key"] == key and f["rule_id"] == rule_id for f in record["quality_findings"]
        )
    )


def test_exactly_874_records_from_rows_13_to_886(parsed: dict[int, dict[str, Any]]) -> None:
    assert len(parsed) == 874
    assert sorted(parsed) == list(range(13, 887))


def test_repeated_station_numbers_stay_separate_records(parsed: dict[int, dict[str, Any]]) -> None:
    counts = Counter(r["station_number"] for r in parsed.values())
    assert {number for number, n in counts.items() if n > 1} == {"105820", "626855"}


def test_the_three_rows_without_a_tx_frequency(parsed: dict[int, dict[str, Any]]) -> None:
    assert rows_with(parsed, "tx_frequency", "MISSING_VALUE") == [108, 109, 110]
    assert rows_with(parsed, "tx_frequency", "UNIT_UNSPECIFIED") == []
    for row in (108, 109, 110):
        assert parsed[row]["reference_station"]["tx_frequency_hz"] is None


def test_row_108_negative_height(parsed: dict[int, dict[str, Any]]) -> None:
    assert rows_with(parsed, "antenna_height_agl_m", "INVALID_OR_UNREALISTIC_HEIGHT") == [108]
    record = parsed[108]
    assert record["station_number"] == "362450"
    assert record["reference_station"]["antenna_height_agl_m"] == -28
    assert record["record_status"] == "REVIEW_REQUIRED"


def test_row_13_reference_values(parsed: dict[int, dict[str, Any]]) -> None:
    record = parsed[13]
    station = record["reference_station"]
    assert record["station_number"] == "5931"
    assert station["tx_frequency_hz"] == pytest.approx(87.9e6)
    assert station["channel_bandwidth_hz"] == pytest.approx(300e3)
    assert (station["radiation_power_value"], station["radiation_power_unit"]) == (60, "kW")
    assert station["antenna_gain_db"] is None  # Blank in the source.


def test_counts_of_flagged_and_missing_values(parsed: dict[int, dict[str, Any]]) -> None:
    def blank(key: str) -> int:
        return sum(r["raw_fields"][key] in (None, "") for r in parsed.values())

    assert blank("licence_class") == 294
    assert blank("rx_frequency") == 61  # 58 empty cells plus 3 empty strings.
    assert blank("antenna_gain_db") == 789  # 614 empty cells plus 175 empty strings.
    assert blank("radiation_power") == 342
    assert rows_with(parsed, "antenna_height_asl_m", "ASL_BELOW_GROUND_HEIGHT") == [187]
    assert all(
        not any(f["rule_id"] == "OUTSIDE_COARSE_FINLAND_BOX" for f in r["quality_findings"])
        for r in parsed.values()
    )
    assert not any(
        f["rule_id"] in {"UNPARSEABLE_VALUE", "UNMAPPED_COLUMN_VALUE"}
        for r in parsed.values()
        for f in r["quality_findings"]
    )


def test_no_unit_or_value_was_guessed(parsed: dict[int, dict[str, Any]]) -> None:
    for record in parsed.values():
        station, raw = record["reference_station"], record["raw_fields"]
        if raw["tx_frequency"] in (None, ""):
            assert station["tx_frequency_hz"] is None
        if raw["radiation_power"] in (None, ""):
            assert station["radiation_power_value"] is None
        if raw["antenna_gain_db"] in (None, ""):
            assert station["antenna_gain_db"] is None


def test_status_summary(parsed: dict[int, dict[str, Any]]) -> None:
    statuses = Counter(r["record_status"] for r in parsed.values())
    print("record status counts:", dict(statuses))
    assert sum(statuses.values()) == 874
    assert statuses["REVIEW_REQUIRED"] >= 1
    assert statuses["INSUFFICIENT_DATA"] == 2  # Rows 109 and 110; 108 also needs review.


def test_every_record_satisfies_the_backend_contract(parsed: dict[int, dict[str, Any]]) -> None:
    contract = pytest.importorskip("astrasync_api.contract.models")
    for record in parsed.values():
        contract.AdapterRecord.model_validate(record)
