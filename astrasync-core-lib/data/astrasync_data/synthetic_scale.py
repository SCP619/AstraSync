"""Synthetic scale data for Stage 6 benchmarks: generated rows in the challenge workbook's layout.

FOR PERFORMANCE TESTING ONLY. Every row is generated from a seeded random stream. None of it is
Traficom, ITU or real station data, and it must never be presented as notices or assignments.
The first line of every file says so, and the parser refuses a CSV without that line.

Format (UTF-8 CSV):
    line 1: the MARKER line
    line 2: the 22 English headers of the workbook, exactly
    line 3: the 22 Finnish headers
    line 4+: one record per line, cells as the workbook would show them

Rows are parsed by the same rules as the workbook (``traficom_workbook.parse_row``), so unit,
missing-value and anomaly handling is identical. A small, seeded share of rows carries the
workbook's known anomaly types, so flag counts can be reconciled exactly.
"""

import csv
import io
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from .traficom_workbook import ENGLISH, FINNISH, SHEET, parse_row

MARKER = "# ASTRASYNC-SYNTHETIC-SCALE-DATA v1: generated for benchmarks, not real data"
GENERATOR_VERSION = "synthetic-scale/1.0.0"

# (centre MHz range, channel bandwidth text, emission designation, licence class)
_PROFILES = (
    ((87.5, 108.0), "300.000 kHz", "300k", "BC"),
    ((146.0, 174.0), "25 kHz", "16k", "MVV"),
    ((410.0, 470.0), "25 kHz", "16k", "FX"),
    ((2025.0, 2110.0), "5.000 MHz", "5000k", "FX"),
    ((5925.0, 6425.0), "28000.000 kHz", "28000k", "FX"),
    ((10700.0, 11700.0), "56000.000 kHz", "56000k", "FX"),
)


@dataclass(frozen=True)
class AnomalyRates:
    missing_tx: float = 0.002
    unitless_tx: float = 0.001
    negative_agl: float = 0.001


@dataclass
class GenerationSummary:
    rows: int
    bytes_written: int
    missing_tx: int
    unitless_tx: int
    negative_agl: int


def _row(rng: random.Random, number: int, rates: AnomalyRates, tally: dict[str, int]) -> list[str]:
    (low, high), channel, emission, licence = rng.choice(_PROFILES)
    tx = rng.uniform(low, high)
    tx_text = f"{tx:.3f} MHz"
    draw = rng.random()
    if draw < rates.missing_tx:
        tx_text = ""
        tally["missing_tx"] += 1
    elif draw < rates.missing_tx + rates.unitless_tx:
        tx_text = f"{tx:.0f}"  # A bare number: the parser must not give it a unit.
        tally["unitless_tx"] += 1
    ground = rng.randint(0, 300)
    agl = rng.randint(5, 120)
    if rng.random() < rates.negative_agl:
        agl = -rng.randint(1, 30)
        tally["negative_agl"] += 1
    gain = f"{rng.uniform(0, 30):.1f}" if rng.random() < 0.3 else ""
    power, unit = (
        (str(rng.choice((1, 5, 10, 50, 100, 500))), rng.choice(("W", "kW")))
        if (rng.random() < 0.6)
        else ("", "")
    )
    return [
        str(number),
        licence,
        f"{rng.uniform(20.5, 31.5):.5f}",
        f"{rng.uniform(59.8, 70.0):.5f}",
        str(ground),
        str(rng.randint(10, 150)),
        "KIINTEÄ",
        channel,
        tx_text,
        f"{tx + 10:.3f} MHz" if rng.random() < 0.7 else "",
        str(agl),
        str(ground + max(agl, 0)),
        gain,
        "F3E",
        emission,
        str(rng.randint(0, 359)),
        rng.choice(("V", "H")),
        power,
        "E",
        unit,
        "",
        rng.choice(("D", "ND")),
    ]


def generate(
    destination: TextIO,
    *,
    rows: int | None = None,
    target_bytes: int | None = None,
    seed: int = 6,
    rates: AnomalyRates = AnomalyRates(),  # noqa: B008 - immutable default.
) -> GenerationSummary:
    """Writes rows until either limit is reached. Deterministic for the same seed and limits."""
    if rows is None and target_bytes is None:
        raise ValueError("Give rows or target_bytes")
    rng = random.Random(seed)  # noqa: S311 - test data, not security.
    tally = {"missing_tx": 0, "unitless_tx": 0, "negative_agl": 0}
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    written = 0
    head = MARKER + "\n"
    writer.writerow(ENGLISH)
    writer.writerow(FINNISH)
    head += buffer.getvalue()
    destination.write(head)
    written += len(head.encode())
    count = 0
    while (rows is None or count < rows) and (target_bytes is None or written < target_bytes):
        buffer.seek(0)
        buffer.truncate()
        for _ in range(1000):
            count += 1
            writer.writerow(_row(rng, 100_000 + count, rates, tally))
            if rows is not None and count >= rows:
                break
        chunk = buffer.getvalue()
        destination.write(chunk)
        written += len(chunk.encode())
    return GenerationSummary(count, written, **tally)


class SyntheticScaleCsvReader:
    """Streams records from a generated file. Memory stays bounded by the batch size."""

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        with artifact_path.open(encoding="utf-8", newline="") as handle:
            if handle.readline().rstrip("\n") != MARKER:
                raise ValueError("Not a synthetic scale data file")
            reader = csv.reader(handle)
            if tuple(next(reader, ())) != ENGLISH or tuple(next(reader, ())) != FINNISH:
                raise ValueError("The header rows are not the workbook's")
            batch: list[dict[str, Any]] = []
            for line, cells in enumerate(reader, start=4):
                if not any(cells):
                    continue
                record = parse_row(line, tuple(cells))
                record["source_table_or_sheet"] = f"{SHEET} (synthetic scale CSV)"
                record["schema_version"] = GENERATOR_VERSION
                batch.append(record)
                if len(batch) >= batch_rows:
                    yield batch
                    batch = []
            if batch:
                yield batch
