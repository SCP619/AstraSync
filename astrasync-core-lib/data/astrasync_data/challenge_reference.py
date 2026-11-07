"""One ``SourceAdapter`` for the challenge reference source type, choosing the parser by content.

The worker registers one adapter per source type. Challenge reference data arrives either as the
Traficom workbook (XLSX) or as generated synthetic scale data (CSV with its marker line). The
file's leading bytes decide, never its name; anything else is refused.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .synthetic_scale import MARKER, SyntheticScaleCsvReader
from .traficom_workbook import SOURCE_TYPE, TraficomWorkbookAdapter

ZIP_MAGIC = b"PK\x03\x04"


class ChallengeReferenceAdapter:
    source_type = SOURCE_TYPE
    parser_version = "challenge-reference/1.0.0"

    def __init__(self) -> None:
        self._workbook = TraficomWorkbookAdapter()
        self._scale = SyntheticScaleCsvReader()

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        with artifact_path.open("rb") as handle:
            head = handle.read(len(MARKER.encode()))
        if head.startswith(ZIP_MAGIC):
            return self._workbook.iter_record_batches(artifact_path, batch_rows=batch_rows)
        if head == MARKER.encode():
            return self._scale.iter_record_batches(artifact_path, batch_rows=batch_rows)
        raise ValueError("Neither the challenge workbook nor synthetic scale data")
