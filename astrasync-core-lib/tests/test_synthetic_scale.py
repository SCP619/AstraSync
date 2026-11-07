"""The synthetic scale generator and its reader. Generated data is never real data."""

import io
from collections import Counter
from pathlib import Path

import pytest
from astrasync_data.challenge_reference import ChallengeReferenceAdapter
from astrasync_data.synthetic_scale import MARKER, AnomalyRates, generate


def write(tmp_path: Path, **kwargs: object) -> tuple[Path, object]:
    path = tmp_path / "scale.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        summary = generate(handle, **kwargs)  # type: ignore[arg-type]
    return path, summary


def records(path: Path, batch_rows: int = 500) -> list[dict[str, object]]:
    adapter = ChallengeReferenceAdapter()
    return [r for b in adapter.iter_record_batches(path, batch_rows=batch_rows) for r in b]


def test_output_is_labelled_and_deterministic() -> None:
    first, second = io.StringIO(), io.StringIO()
    generate(first, rows=200, seed=1)
    generate(second, rows=200, seed=1)
    assert first.getvalue() == second.getvalue()
    assert first.getvalue().splitlines()[0] == MARKER
    assert "not real data" in MARKER


def test_every_row_is_read_back_with_exact_counts(tmp_path: Path) -> None:
    rates = AnomalyRates(missing_tx=0.05, unitless_tx=0.05, negative_agl=0.05)
    path, summary = write(tmp_path, rows=5_000, seed=3, rates=rates)
    parsed = records(path)
    assert len(parsed) == summary.rows == 5_000  # type: ignore[attr-defined]
    assert parsed[0]["source_row_or_key"] == "4"  # Data starts after marker and two headers.

    def rows_with(key: str, rule: str) -> int:
        return sum(
            any(f["field_key"] == key and f["rule_id"] == rule for f in r["quality_findings"])  # type: ignore[attr-defined]
            for r in parsed
        )

    assert rows_with("tx_frequency", "MISSING_VALUE") == summary.missing_tx  # type: ignore[attr-defined]
    assert rows_with("tx_frequency", "UNIT_UNSPECIFIED") == summary.unitless_tx  # type: ignore[attr-defined]
    assert (
        rows_with("antenna_height_agl_m", "INVALID_OR_UNREALISTIC_HEIGHT") == summary.negative_agl  # type: ignore[attr-defined]
    )
    statuses = Counter(r["record_status"] for r in parsed)
    assert statuses["VALID"] > 0 and statuses["REVIEW_REQUIRED"] > 0


def test_generation_can_stop_at_a_byte_target(tmp_path: Path) -> None:
    path, summary = write(tmp_path, target_bytes=200_000)
    size = path.stat().st_size
    assert summary.bytes_written == size  # type: ignore[attr-defined]
    assert 200_000 <= size < 200_000 + 200 * 1000  # Stops within one 1,000-row chunk.


def test_dispatcher_refuses_unknown_content(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text("Station number,TX frequency\n1,87.9 MHz\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Neither"):
        records(path)


def test_records_satisfy_the_backend_contract(tmp_path: Path) -> None:
    contract = pytest.importorskip("astrasync_api.contract.models")
    path, _ = write(tmp_path, rows=300, rates=AnomalyRates(0.1, 0.1, 0.1))
    for record in records(path):
        contract.AdapterRecord.model_validate(record)
