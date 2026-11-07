"""Parsed records as immutable Parquet datasets, one per artifact, read through DuckDB.

PostgreSQL keeps the transactional facts (the artifact, its integrity checks, the job and the
dataset manifest, ``record_datasets``). High-volume parsed records, their quality findings and
normalized station fields live in two Parquet files per artifact.

Publication is crash-safe. A writer fills ``staging/<artifact>/<attempt>/``, closes and syncs both
files, hashes them and renames the directory into ``datasets/<tenant>/<artifact>/<attempt>/``. The
manifest row is committed in the same transaction that marks the artifact indexed. Readers open
only the paths a manifest names and check each file's size against it, so a partial or orphaned
directory is never read. A retry starts by deleting every unpublished directory of its artifact,
and writes the same content again, because parsing is deterministic.

API clients never send SQL here. Every query is a fixed template with bound parameters, run on a
fresh in-memory DuckDB connection that can read only this store's root and cannot load extensions
or change its own settings.

Reads return the same ORM row classes that the PostgreSQL index uses, as transient objects that are
never added to a session, so response building is identical for both stores.
"""

import hashlib
import json
import os
import re
import shutil
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import select
from sqlalchemy.orm import Session

from .authz import ObjectAccessPolicy
from .identity import Principal
from .library_tables import (
    RecordDatasetRow,
    RecordQualityFindingRow,
    ReferenceStationRow,
    SourceRecordLocationRow,
    SourceSearchRow,
)

FORMAT_VERSION = "records-parquet/1"
RIGHT_READ = "READ"
ROW_GROUP_ROWS = 5_000
_RECORDS = "records.parquet"
_FINDINGS = "findings.parquet"
_SEGMENT = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}$")
_HASH_CHUNK = 8 * 1024 * 1024

RECORD_SCHEMA = pa.schema(
    [
        ("artifact_id", pa.string()),
        ("ordinal", pa.int64()),
        ("source_table_or_sheet", pa.string()),
        ("source_row_or_key", pa.string()),
        ("source_page", pa.int32()),
        ("notice_id", pa.string()),
        ("raw_record_sha256", pa.string()),
        # JSON text, written in the adapter's key order so raw values read back unchanged.
        ("raw_fields", pa.string()),
        ("field_aliases", pa.string()),
        ("analysis_eligibility", pa.string()),
        ("schema_version", pa.string()),
        ("issue_key", pa.string()),
        ("station_number", pa.string()),
        ("network_id", pa.string()),
        ("administration", pa.string()),
        ("frequency_start_mhz", pa.float64()),
        ("frequency_end_mhz", pa.float64()),
        ("text_terms", pa.string()),
        ("record_status", pa.string()),
        ("reference_station", pa.string()),
    ]
)
FINDING_SCHEMA = pa.schema(
    [
        ("artifact_id", pa.string()),
        ("ordinal", pa.int64()),
        ("finding_index", pa.int32()),
        ("field_key", pa.string()),
        ("raw_value", pa.string()),
        ("normalized_value", pa.string()),
        ("rule_id", pa.string()),
        ("severity", pa.string()),
        ("status", pa.string()),
        ("reviewer_override_id", pa.string()),
    ]
)


class DatasetDamaged(RuntimeError):
    """A published dataset file is missing or does not match its manifest."""


@dataclass(frozen=True)
class PublishedDataset:
    relative_path: str
    record_count: int
    finding_count: int
    records_sha256: str
    records_bytes: int
    findings_sha256: str
    findings_bytes: int


def _segment(value: str) -> str:
    if not _SEGMENT.fullmatch(value) or value in (".", ".."):
        raise ValueError("Unsafe path segment for the record store")
    return value


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync(path: Path) -> None:
    # Windows refuses to flush a read-only handle, so open for update (nothing is written).
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


class DatasetWriter:
    """Streams one artifact's records into staging. Nothing is visible until ``publish``."""

    def __init__(self, root: Path, tenant_id: str, artifact_id: str) -> None:
        self._root = root
        self._tenant = _segment(tenant_id)
        self._artifact = _segment(artifact_id)
        self._token = uuid4().hex
        self._staging = root / "staging" / self._artifact / self._token
        self._staging.mkdir(parents=True)
        self._records = pq.ParquetWriter(
            self._staging / _RECORDS, RECORD_SCHEMA, compression="zstd"
        )
        self._findings = pq.ParquetWriter(
            self._staging / _FINDINGS, FINDING_SCHEMA, compression="zstd"
        )
        self._pending_records: list[dict[str, Any]] = []
        self._pending_findings: list[dict[str, Any]] = []
        self.record_count = 0
        self.finding_count = 0
        self._closed = False

    def write_batch(
        self,
        locations: Sequence[dict[str, Any]],
        searches: Sequence[dict[str, Any]],
        stations: Sequence[dict[str, Any]],
        findings: Sequence[dict[str, Any]],
    ) -> None:
        """Takes the rows the PostgreSQL index would insert, so both stores hold the same values."""
        station_fields = {row["source_record_id"]: row["fields"] for row in stations}
        ordinals: dict[str, int] = {}
        for location, search in zip(locations, searches, strict=True):
            if location["source_record_id"] != search["source_record_id"]:
                raise ValueError("Location and search rows are out of step")
            if location["artifact_id"] != self._artifact:
                raise ValueError("A record of another artifact was given to this writer")
            ordinals[location["source_record_id"]] = location["ordinal"]
            station = station_fields.get(location["source_record_id"])
            self._pending_records.append(
                {
                    "artifact_id": self._artifact,
                    "ordinal": location["ordinal"],
                    "source_table_or_sheet": location["source_table_or_sheet"],
                    "source_row_or_key": location["source_row_or_key"],
                    "source_page": location["source_page"],
                    "notice_id": location["notice_id"],
                    "raw_record_sha256": location["raw_record_sha256"],
                    "raw_fields": _json(location["raw_fields"]),
                    "field_aliases": _json(location["field_aliases"]),
                    "analysis_eligibility": _json(location["analysis_eligibility"]),
                    "schema_version": location["schema_version"],
                    "issue_key": search["issue_key"],
                    "station_number": search["station_number"],
                    "network_id": search["network_id"],
                    "administration": search["administration"],
                    "frequency_start_mhz": search["frequency_start_mhz"],
                    "frequency_end_mhz": search["frequency_end_mhz"],
                    "text_terms": search["text_terms"],
                    "record_status": search["record_status"],
                    "reference_station": _json(station) if station is not None else None,
                }
            )
        for finding in findings:
            record_id = finding["source_record_id"]
            prefix, _, index = finding["finding_id"].rpartition("-")
            if prefix != record_id:
                raise ValueError("A finding ID does not belong to its record")
            self._pending_findings.append(
                {
                    "artifact_id": self._artifact,
                    "ordinal": ordinals[record_id],
                    "finding_index": int(index),
                    "field_key": finding["field_key"],
                    "raw_value": finding["raw_value"],
                    "normalized_value": finding["normalized_value"],
                    "rule_id": finding["rule_id"],
                    "severity": finding["severity"],
                    "status": finding["status"],
                    "reviewer_override_id": finding.get("reviewer_override_id"),
                }
            )
        if len(self._pending_records) >= ROW_GROUP_ROWS:
            self._flush()

    def _flush(self) -> None:
        if self._pending_records:
            self._records.write_table(pa.Table.from_pylist(self._pending_records, RECORD_SCHEMA))
            self.record_count += len(self._pending_records)
            self._pending_records = []
        if self._pending_findings:
            self._findings.write_table(pa.Table.from_pylist(self._pending_findings, FINDING_SCHEMA))
            self.finding_count += len(self._pending_findings)
            self._pending_findings = []

    def _close(self) -> None:
        if not self._closed:
            self._closed = True
            self._records.close()
            self._findings.close()

    def publish(self) -> PublishedDataset:
        """Makes the files durable and moves them to their final place. The caller then commits
        the manifest row; until it does, readers still cannot see this dataset."""
        self._flush()
        self._close()
        records, findings = self._staging / _RECORDS, self._staging / _FINDINGS
        for path in (records, findings):
            _fsync(path)
        published = PublishedDataset(
            relative_path=f"datasets/{self._tenant}/{self._artifact}/{self._token}",
            record_count=self.record_count,
            finding_count=self.finding_count,
            records_sha256=_sha256(records),
            records_bytes=records.stat().st_size,
            findings_sha256=_sha256(findings),
            findings_bytes=findings.stat().st_size,
        )
        target = self._root / published.relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self._staging, target)  # One rename: the directory is complete or absent.
        try:
            self._staging.parent.rmdir()  # The artifact's staging folder, if no other attempt.
        except OSError:
            pass
        return published

    def discard(self) -> None:
        self._close()
        shutil.rmtree(self._staging, ignore_errors=True)


class ParquetRecordStore:
    def __init__(self, root: Path, *, memory_limit: str = "1GB", threads: int = 4) -> None:
        self.root = root
        self._memory_limit = memory_limit
        self._threads = threads
        # One locked-down connection per thread. It holds no tables or state between queries;
        # opening and locking a new one costs about 20 ms, more than most queries.
        self._local = threading.local()
        root.mkdir(parents=True, exist_ok=True)

    # --- Writing ------------------------------------------------------------------------------

    def begin(self, tenant_id: str, artifact_id: str) -> DatasetWriter:
        """Call only for an artifact that is not indexed: then nothing of it is published, and
        every directory it has here is left over from an earlier attempt."""
        self.discard_unpublished(tenant_id, artifact_id)
        return DatasetWriter(self.root, tenant_id, artifact_id)

    def discard_unpublished(self, tenant_id: str, artifact_id: str) -> None:
        for path in (
            self.root / "staging" / _segment(artifact_id),
            self.root / "datasets" / _segment(tenant_id) / _segment(artifact_id),
        ):
            if path.exists():
                shutil.rmtree(path)

    # --- Reading ------------------------------------------------------------------------------

    def _file(self, dataset: RecordDatasetRow, name: str, expected_bytes: int) -> str:
        path = (self.root / dataset.relative_path / name).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise DatasetDamaged("A manifest path points outside the record store")
        try:
            size = path.stat().st_size
        except FileNotFoundError as exc:
            raise DatasetDamaged(f"Dataset file missing for {dataset.artifact_id}") from exc
        if size != expected_bytes:
            raise DatasetDamaged(f"Dataset file size differs from manifest: {dataset.artifact_id}")
        return path.as_posix()

    def _records_file(self, dataset: RecordDatasetRow) -> str:
        return self._file(dataset, _RECORDS, dataset.records_bytes)

    def _findings_file(self, dataset: RecordDatasetRow) -> str:
        return self._file(dataset, _FINDINGS, dataset.findings_bytes)

    def verify(self, dataset: RecordDatasetRow) -> bool:
        """Full content check against the manifest digests."""
        try:
            records = Path(self._records_file(dataset))
            findings = Path(self._findings_file(dataset))
        except DatasetDamaged:
            return False
        return (
            _sha256(records) == dataset.records_sha256
            and _sha256(findings) == dataset.findings_sha256
        )

    def _connect(self) -> duckdb.DuckDBPyConnection:
        connection = duckdb.connect(":memory:")
        connection.execute("SET allowed_directories = ?", [[self.root.resolve().as_posix() + "/"]])
        connection.execute("SET enable_external_access = false")
        connection.execute("SET autoinstall_known_extensions = false")
        connection.execute("SET autoload_known_extensions = false")
        connection.execute(f"SET memory_limit = '{self._memory_limit}'")
        connection.execute(f"SET threads = {int(self._threads)}")
        connection.execute("SET lock_configuration = true")
        return connection

    def _query(self, sql: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        connection = getattr(self._local, "connection", None)
        if connection is None:
            connection = self._local.connection = self._connect()
        cursor = connection.execute(sql, parameters)
        names = [column[0] for column in cursor.description or ()]
        return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]

    def search(
        self,
        datasets: Sequence[RecordDatasetRow],
        *,
        query_text: str | None,
        station_number: str | None,
        frequency_start_mhz: float | None,
        frequency_end_mhz: float | None,
        after: str | None,
        limit: int,
    ) -> list[SourceSearchRow]:
        """The PostgreSQL index's search, over the given (already permission-filtered) datasets."""
        if not datasets:
            return []
        by_artifact = {dataset.artifact_id: dataset for dataset in datasets}
        conditions = ["TRUE"]
        parameters: dict[str, Any] = {
            "files": [self._records_file(dataset) for dataset in datasets],
            "limit": limit,
        }
        if query_text:
            conditions.append("contains(text_terms, $text)")
            parameters["text"] = query_text.lower()
        if station_number is not None:
            conditions.append("station_number = $station")
            parameters["station"] = station_number
        if frequency_start_mhz is not None:
            conditions.append("frequency_end_mhz >= $start")
            parameters["start"] = frequency_start_mhz
        if frequency_end_mhz is not None:
            conditions.append("frequency_start_mhz <= $end")
            parameters["end"] = frequency_end_mhz
        if after is not None:
            conditions.append("source_record_id > $after")
            parameters["after"] = after
        # Only fixed fragments are joined into the text; every value is a bound parameter.
        rows = self._query(
            "SELECT * FROM ("  # noqa: S608
            "SELECT artifact_id || '-' || CAST(ordinal AS VARCHAR) AS source_record_id, "
            "artifact_id, issue_key, station_number, network_id, administration, "
            "frequency_start_mhz, frequency_end_mhz, text_terms, record_status "
            "FROM read_parquet($files)) "
            f"WHERE {' AND '.join(conditions)} "
            "ORDER BY source_record_id LIMIT $limit",
            parameters,
        )
        return [_search_row(by_artifact[row["artifact_id"]], row) for row in rows]

    def preview(
        self,
        dataset: RecordDatasetRow,
        *,
        page: int | None,
        table: str | None,
        row: int | None,
        after_ordinal: int | None,
        limit: int,
    ) -> list[SourceRecordLocationRow]:
        conditions = ["TRUE"]
        parameters: dict[str, Any] = {"file": self._records_file(dataset), "limit": limit}
        if page is not None:
            conditions.append("source_page = $page")
            parameters["page"] = page
        if table is not None:
            conditions.append("source_table_or_sheet = $table")
            parameters["table"] = table
        if row is not None:
            conditions.append("source_row_or_key = $row")
            parameters["row"] = str(row)
        if after_ordinal is not None:
            conditions.append("ordinal > $after")
            parameters["after"] = after_ordinal
        rows = self._query(
            f"SELECT * FROM read_parquet($file) WHERE {' AND '.join(conditions)} "  # noqa: S608
            "ORDER BY ordinal LIMIT $limit",
            parameters,
        )
        return [_location_row(dataset, item) for item in rows]

    def record(
        self, dataset: RecordDatasetRow, ordinal: int
    ) -> tuple[SourceRecordLocationRow, SourceSearchRow, ReferenceStationRow | None] | None:
        # Datasets are immutable, so the last record read on this thread can be reused (a detail
        # request reads it for the location and again for the station fields).
        key = (dataset.relative_path, dataset.records_bytes, ordinal)
        last = getattr(self._local, "last_record", None)
        if last is not None and last[0] == key:
            self._records_file(dataset)  # Still refuse a file that changed since.
            return last[1]  # type: ignore[no-any-return]
        found = self._read_record(dataset, ordinal)
        self._local.last_record = (key, found)
        return found

    def _read_record(
        self, dataset: RecordDatasetRow, ordinal: int
    ) -> tuple[SourceRecordLocationRow, SourceSearchRow, ReferenceStationRow | None] | None:
        rows = self._query(
            "SELECT * FROM read_parquet($file) WHERE ordinal = $ordinal",
            {"file": self._records_file(dataset), "ordinal": ordinal},
        )
        if not rows:
            return None
        row = rows[0]
        record_id = f"{dataset.artifact_id}-{ordinal}"
        station = (
            ReferenceStationRow(
                source_record_id=record_id, fields=json.loads(row["reference_station"])
            )
            if row["reference_station"] is not None
            else None
        )
        return (
            _location_row(dataset, row),
            _search_row(dataset, {**row, "source_record_id": record_id}),
            station,
        )

    def findings(self, dataset: RecordDatasetRow, ordinal: int) -> list[RecordQualityFindingRow]:
        rows = self._query(
            "SELECT * FROM read_parquet($file) WHERE ordinal = $ordinal ORDER BY finding_index",
            {"file": self._findings_file(dataset), "ordinal": ordinal},
        )
        record_id = f"{dataset.artifact_id}-{ordinal}"
        found = [
            RecordQualityFindingRow(
                finding_id=f"{record_id}-{row['finding_index']}",
                source_record_id=record_id,
                field_key=row["field_key"],
                raw_value=row["raw_value"],
                normalized_value=row["normalized_value"],
                rule_id=row["rule_id"],
                severity=row["severity"],
                status=row["status"],
                reviewer_override_id=row["reviewer_override_id"],
            )
            for row in rows
        ]
        # The PostgreSQL index orders findings by their ID string; keep that order.
        return sorted(found, key=lambda finding: finding.finding_id)

    def overlapping(
        self, dataset: RecordDatasetRow, start_mhz: float, end_mhz: float
    ) -> list[tuple[SourceSearchRow, SourceRecordLocationRow]]:
        rows = self._query(
            "SELECT * FROM read_parquet($file) "
            "WHERE frequency_end_mhz >= $start AND frequency_start_mhz <= $end ORDER BY ordinal",
            {"file": self._records_file(dataset), "start": start_mhz, "end": end_mhz},
        )
        return [
            (
                _search_row(dataset, {**row, "source_record_id": _record_id(dataset, row)}),
                _location_row(dataset, row),
            )
            for row in rows
        ]

    def stations(self, dataset: RecordDatasetRow) -> list[tuple[SourceSearchRow, dict[str, Any]]]:
        rows = self._query(
            "SELECT * EXCLUDE (raw_fields, field_aliases) FROM read_parquet($file) "
            "WHERE reference_station IS NOT NULL ORDER BY ordinal",
            {"file": self._records_file(dataset)},
        )
        return [
            (
                _search_row(dataset, {**row, "source_record_id": _record_id(dataset, row)}),
                json.loads(row["reference_station"]),
            )
            for row in rows
        ]


def _record_id(dataset: RecordDatasetRow, row: dict[str, Any]) -> str:
    return f"{dataset.artifact_id}-{row['ordinal']}"


def _location_row(dataset: RecordDatasetRow, row: dict[str, Any]) -> SourceRecordLocationRow:
    return SourceRecordLocationRow(
        source_record_id=_record_id(dataset, row),
        tenant_id=dataset.tenant_id,
        artifact_id=dataset.artifact_id,
        ordinal=row["ordinal"],
        source_table_or_sheet=row["source_table_or_sheet"],
        source_row_or_key=row["source_row_or_key"],
        source_page=row["source_page"],
        notice_id=row["notice_id"],
        raw_record_sha256=row["raw_record_sha256"],
        raw_fields=json.loads(row["raw_fields"]),
        field_aliases=json.loads(row["field_aliases"]),
        analysis_eligibility=json.loads(row["analysis_eligibility"]),
        parser_version=dataset.parser_version,
        schema_version=row["schema_version"],
    )


def _search_row(dataset: RecordDatasetRow, row: dict[str, Any]) -> SourceSearchRow:
    return SourceSearchRow(
        source_record_id=row["source_record_id"],
        tenant_id=dataset.tenant_id,
        source_id=dataset.source_id,
        artifact_id=dataset.artifact_id,
        issue_key=row["issue_key"],
        publisher=dataset.publisher,
        filename_original=dataset.filename_original,
        station_number=row["station_number"],
        network_id=row["network_id"],
        administration=row["administration"],
        frequency_start_mhz=row["frequency_start_mhz"],
        frequency_end_mhz=row["frequency_end_mhz"],
        text_terms=row["text_terms"],
        classification=dataset.classification,
        record_status=row["record_status"],
        is_synthetic=dataset.is_synthetic,
    )


# --- Manifest lookups (PostgreSQL) ------------------------------------------------------------


def readable_datasets(
    session: Session,
    policy: ObjectAccessPolicy,
    principal: Principal,
    artifact_id: str | None = None,
) -> list[RecordDatasetRow]:
    """The same permission filter the search index applies per record, at dataset level."""
    table = RecordDatasetRow
    query = select(table).where(
        policy.readable_clause(
            principal,
            RIGHT_READ,
            tenant_column=table.tenant_id,
            source_column=table.source_id,
            classification_column=table.classification,
            synthetic_column=table.is_synthetic,
        )
    )
    if artifact_id is not None:
        query = query.where(table.artifact_id == artifact_id)
    return list(session.scalars(query.order_by(table.artifact_id)))


def parse_record_id(source_record_id: str) -> tuple[str, int] | None:
    artifact_id, _, ordinal = source_record_id.rpartition("-")
    if not artifact_id or not ordinal.isascii() or not ordinal.isdecimal() or len(ordinal) > 18:
        return None
    return artifact_id, int(ordinal)


def dataset_for_record(
    session: Session, source_record_id: str, tenant_id: str
) -> tuple[RecordDatasetRow, int] | None:
    parsed = parse_record_id(source_record_id)
    if parsed is None:
        return None
    dataset = session.get(RecordDatasetRow, parsed[0])
    if dataset is None or dataset.tenant_id != tenant_id:
        return None
    # Ordinals can have gaps (rejected rows are not stored), so presence is checked on read.
    return dataset, parsed[1]
