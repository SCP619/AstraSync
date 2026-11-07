"""Parser tests for the Traficom open-data allocation table (see fixtures/README.md for source)."""

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest
from astrasync_data.traficom_m4_table import TraficomM4TableAdapter

EXCERPT = Path(__file__).parent / "fixtures" / "traficom_m4_excerpt.json"
SNAPSHOT = os.environ.get("ASTRASYNC_TRAFICOM_M4_SNAPSHOT")


def excerpt() -> dict[str, Any]:
    return dict(json.loads(EXCERPT.read_text(encoding="utf-8")))


def parse(tmp_path: Path, document: Any, batch_rows: int = 100) -> list[dict[str, Any]]:
    path = tmp_path / "table.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    batches = TraficomM4TableAdapter().iter_record_batches(path, batch_rows=batch_rows)
    return [record for batch in batches for record in batch]


def test_real_excerpt_rows_use_the_exact_hz_limits(tmp_path: Path) -> None:
    records = parse(tmp_path, excerpt(), batch_rows=2)
    assert [r["source_row_or_key"] for r in records] == ["1", "2", "4436"]
    first = records[0]
    assert (first["frequency_start_mhz"], first["frequency_end_mhz"]) == (0.0083, 0.009)
    assert first["record_status"] == "VALID"
    assert first["quality_findings"] == []
    assert first["administration"] == "FIN"
    assert first["raw_fields"]["Services_in_Finland"] == "METEOROLOGICAL AIDS"
    fss = records[2]
    assert (fss["frequency_start_mhz"], fss["frequency_end_mhz"]) == (10700.0, 10950.0)
    assert fss["raw_fields"]["Services_in_Finland"].startswith("FIXED SATELLITE")


def test_transmitter_power_zero_is_kept_as_raw_text_only(tmp_path: Path) -> None:
    record = parse(tmp_path, excerpt())[0]
    assert record["raw_fields"]["Transmitter_power"] == "0"
    assert record["reference_station"] is None  # Not a station; no power is normalized.


def test_text_and_numeric_limits_must_agree(tmp_path: Path) -> None:
    document = excerpt()
    document["value"][0]["Sub_band_lower_limit"] = "8.4 kHz"
    record = parse(tmp_path, document)[0]
    flag = record["quality_findings"][0]
    assert (flag["rule_id"], flag["severity"]) == ("TEXT_AND_HZ_LIMITS_DISAGREE", "WARNING")
    assert record["frequency_start_mhz"] == 0.0083  # The numeric field is still the value used.
    assert record["record_status"] == "VALID_WITH_WARNINGS"


def test_reversed_limits_are_not_indexed(tmp_path: Path) -> None:
    document = excerpt()
    row = document["value"][0]
    row["Sub_band_lower_limit__Hz_"], row["Sub_band_upper_limit__Hz_"] = 9000, 8300
    row["Sub_band_lower_limit"], row["Sub_band_upper_limit"] = "9 kHz", "8.3 kHz"
    record = parse(tmp_path, document)[0]
    assert record["record_status"] == "REVIEW_REQUIRED"
    assert record["frequency_start_mhz"] is None and record["frequency_end_mhz"] is None
    assert record["analysis_eligibility"]["FINLAND_ALLOCATION_LOOKUP"] == "REVIEW_REQUIRED"


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update({"@odata.context": "https://example.test/$metadata#Other"}),
        lambda d: d.update({"@odata.nextLink": "https://opendata.traficom.fi/next"}),
        lambda d: d["value"][0].update({"New_field": "x"}),
        lambda d: d["value"][0].pop("Comment"),
        lambda d: d["value"].append(copy.deepcopy(d["value"][0])),
        lambda d: d.pop("value"),
    ],
    ids=["other-endpoint", "paged", "new-field", "missing-field", "repeated-id", "no-rows"],
)
def test_changed_or_incomplete_responses_are_refused(tmp_path: Path, change: Any) -> None:
    document = excerpt()
    change(document)
    with pytest.raises(ValueError):
        parse(tmp_path, document)


def test_a_non_json_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "table.json"
    path.write_bytes(b"\xff\xfe not json")
    with pytest.raises(ValueError, match="JSON"):
        list(TraficomM4TableAdapter().iter_record_batches(path, batch_rows=10))


def test_records_satisfy_the_backend_contract(tmp_path: Path) -> None:
    contract = pytest.importorskip("astrasync_api.contract.models")
    for record in parse(tmp_path, excerpt()):
        contract.AdapterRecord.model_validate(record)


@pytest.mark.skipif(not SNAPSHOT, reason="ASTRASYNC_TRAFICOM_M4_SNAPSHOT not set")
def test_full_snapshot_parses_cleanly() -> None:
    assert SNAPSHOT
    batches = TraficomM4TableAdapter().iter_record_batches(Path(SNAPSHOT), batch_rows=1000)
    records = [r for batch in batches for r in batch]
    statuses = {r["record_status"] for r in records}
    flagged = [r for r in records if r["quality_findings"]]
    print(f"rows={len(records)} statuses={statuses} flagged={len(flagged)}")
    assert len(records) > 0
    assert "REVIEW_REQUIRED" not in statuses
    for record in records:
        assert record["frequency_start_mhz"] <= record["frequency_end_mhz"]
