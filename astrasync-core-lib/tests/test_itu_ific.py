"""ITU BR IFIC parsers: archive safety always; real issues when the files are available.

Real-data tests use the official downloads, kept outside the repository. Point
``ASTRASYNC_IFIC_DATA`` at a folder holding ``ific3074.zip`` and ``brific3076.zip`` (from
https://www.itu.int/sns/ific10/ and the Terrestrial BR IFIC page). Expected counts are the
publisher's own: BR IFIC 3076 ReadMe (Information Note, 9 July 2026) lists 2415 / 1051 / 44
Article 11 notices in Parts I / II / III and 2 + 14 notices in GE06L/167, 406 + 66 in GE84/365.
"""

import os
import zipfile
from collections import Counter
from pathlib import Path

import pytest
from astrasync_data import itu_ific as I

_DATA_DIR = os.environ.get("ASTRASYNC_IFIC_DATA")
DATA = Path(_DATA_DIR) if _DATA_DIR else None


def _zip(path: Path, members: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def test_issue_numbers_come_from_itu_file_names_only() -> None:
    assert I.issue_from_name("ific3074.zip", I.SPACE_SOURCE_TYPE) == 3074
    assert I.issue_from_name("brific3076.mdb", I.TERRESTRIAL_SOURCE_TYPE) == 3076
    assert I.issue_from_name("brific3076.zip", I.SPACE_SOURCE_TYPE) is None
    assert I.issue_from_name("upload.zip", I.TERRESTRIAL_SOURCE_TYPE) is None


@pytest.mark.parametrize(
    "members",
    [
        {"brific3076.mdb": b"x", "extra.mdb": b"y"},  # More than one member.
        {"../brific3076.mdb": b"x"},  # Path traversal.
        {"brific3076.exe": b"x"},  # Not a database.
        {"brific3075.mdb": b"x"},  # Member issue differs from the archive name.
        {"database.mdb": b"x"},  # Not named like an IFIC database.
    ],
)
def test_unsafe_or_unexpected_archives_are_refused(
    tmp_path: Path, members: dict[str, bytes]
) -> None:
    archive = _zip(tmp_path / "brific3076.zip", members)
    with pytest.raises(I.IficFormatError):
        with I.open_database(archive, I.TERRESTRIAL_SOURCE_TYPE):
            pass


def test_compression_bombs_are_refused(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "brific3076.zip", {"brific3076.mdb": b"\0" * (4 * 1024 * 1024)})
    with pytest.raises(I.IficFormatError, match="ratio"):
        with I.open_database(archive, I.TERRESTRIAL_SOURCE_TYPE):
            pass


def test_other_bytes_are_refused_and_extraction_is_cleaned_up(tmp_path: Path) -> None:
    junk = tmp_path / "brific3076.zip"
    junk.write_bytes(b"%PDF-1.7 not an archive")
    with pytest.raises(I.IficFormatError):
        with I.open_database(junk, I.TERRESTRIAL_SOURCE_TYPE):
            pass
    archive = _zip(tmp_path / "ok3.zip", {"brific3076.mdb": os.urandom(1024)})
    with I.open_database(archive, I.TERRESTRIAL_SOURCE_TYPE, "brific3076.zip") as database:
        extracted = database
        assert extracted.read_bytes()[:4] != b""
    assert not extracted.exists()
    with pytest.raises(I.IficFormatError):
        I.read_terrestrial(_not_a_database(tmp_path))


def _not_a_database(tmp_path: Path) -> Path:
    path = tmp_path / "brific3076.mdb"
    path.write_bytes(b"\x00\x01\x00\x00" + os.urandom(64))
    return path


@pytest.mark.skipif(
    DATA is None or not (DATA / "brific3076.zip").exists(), reason="ASTRASYNC_IFIC_DATA not set"
)
def test_terrestrial_3076_reconciles_with_the_publisher_counts() -> None:
    assert DATA is not None
    with I.open_database(DATA / "brific3076.zip", I.TERRESTRIAL_SOURCE_TYPE) as database:
        records, summary = I.read_terrestrial(database, 3076)
    assert summary.issue == 3076 and summary.publication_date == "2026-07-21"
    parts = summary.counts["publication_parts"]
    other = summary.counts["other_service_publication_parts_not_parsed"]
    assert parts["NTFD_RR:1"] + other.get("fmtv:NTFD_RR:1", 0) == 2415
    assert parts["NTFD_RR:2"] + other.get("fmtv:NTFD_RR:2", 0) == 1051
    assert parts["NTFD_RR:3"] + other.get("fmtv:NTFD_RR:3", 0) == 44
    assert (parts["GE06L:A"], parts["GE06L:B"]) == (2, 14)
    assert (other["fmtv:GE84:A"], other["fmtv:GE84:B"]) == (406, 66)
    roles = Counter(r["raw_fields"]["norm.role"] for r in records)
    assert roles == {"NOTICE": 3481, "RECORDED_CONTEXT": 576}
    assert len(records) == summary.counts["fxm_terra_rows"]  # Every row in, none dropped.


@pytest.mark.skipif(
    DATA is None or not (DATA / "ific3074.zip").exists(), reason="ASTRASYNC_IFIC_DATA not set"
)
def test_space_3074_keeps_every_notice_and_flags_impossible_power_values() -> None:
    assert DATA is not None
    with I.open_database(DATA / "ific3074.zip", I.SPACE_SOURCE_TYPE) as database:
        records, summary = I.read_space(database, 3074)
    assert summary.counts["notices_in_issue"] == 196
    assert len({r["notice_id"] for r in records}) == 196
    flagged = [
        r
        for r in records
        if any(f["rule_id"] == "MAX_DENSITY_ABOVE_PEAK_POWER" for f in r["quality_findings"])
    ]
    # IND LVI, group 126662625: pwr_ds_max +73.0 dBW/Hz against pep_max -4.0 dBW.
    assert {r["source_row_or_key"] for r in flagged} >= {"126662625"}
