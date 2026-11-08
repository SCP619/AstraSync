"""The evaluation workbook mirrors the run's CSV files (made-up values)."""

from pathlib import Path

from astrasync_data.ific_evaluate import write_xlsx
from openpyxl import load_workbook

MANIFEST = {
    "artifact": "AstraSync evaluation of TEST 1",
    "issue": 1,
    "publication_date": "2026-01-01",
    "generated_at_utc": "2026-01-02T03:04:05+00:00",
    "rule_version": "test/1",
    "criteria": {"criterion_set_id": "X"},
    "screening_parameters": {"t": 10},
    "inputs": [
        {"role": "r", "filename": "f", "bytes": 1, "sha256": "a" * 64, "official_url": None}
    ],
}


def test_sheets_match_the_csv_and_numbers_stay_numbers(tmp_path: Path) -> None:
    (tmp_path / "findings.csv").write_text(
        "rank,notice_id,margin_db,site\n1,N1,14.84,KOSTOMUKSHA\n2,N2,,X\n", encoding="utf-8"
    )
    (tmp_path / "border_points.csv").write_text("notice_id,lat\nN1,64.5\n", encoding="utf-8")
    path = tmp_path / "out.xlsx"
    write_xlsx(tmp_path, path, MANIFEST)
    book = load_workbook(path)
    assert book.sheetnames == ["About", "Results", "Border points", "Inputs"]
    results = list(book["Results"].values)
    assert results[0] == ("rank", "notice_id", "margin_db", "site")
    assert results[1] == (1, "N1", 14.84, "KOSTOMUKSHA")
    assert results[2][2] is None
    assert book["About"]["B3"].value.startswith("Real IFIC data")


def test_space_runs_have_no_border_sheet(tmp_path: Path) -> None:
    (tmp_path / "findings.csv").write_text("rank,notice_id\n1,S1\n", encoding="utf-8")
    write_xlsx(tmp_path, tmp_path / "s.xlsx", MANIFEST)
    assert "Border points" not in load_workbook(tmp_path / "s.xlsx").sheetnames
