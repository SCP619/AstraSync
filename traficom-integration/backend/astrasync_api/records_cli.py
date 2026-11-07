"""Operator commands for the Parquet record store, run with the worker's settings.

    python -m astrasync_api.records_cli build [--artifact ID]   # datasets for indexed artifacts
    python -m astrasync_api.records_cli verify [--artifact ID]  # full SHA-256 check of datasets

``build`` re-parses each immutable master with the same parser version and publishes only when
the counts equal the recorded reconciliation (``ingest.build_record_dataset``). It never deletes
the PostgreSQL index rows. ``verify`` exits non-zero if any dataset differs from its manifest.
"""

import argparse
import os
import sys

from sqlalchemy import select

from .config import Settings, SettingsError
from .contract.enums import ArtifactStatus
from .ingest import DatasetBuildRefused, build_record_dataset
from .library_tables import RecordDatasetRow, SourceArtifactRow
from .worker import build_runtime

_INDEXED = (ArtifactStatus.INDEXED.value, ArtifactStatus.INDEXED_WITH_WARNINGS.value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--artifact", help="one artifact ID; default: all")
    args = parser.parse_args(argv)
    context = build_runtime(Settings.from_env(os.environ)).context
    if context.records is None:
        raise SettingsError("Set ASTRASYNC_RECORD_STORE_PATH to use the record store")
    with context.sessions() as session:
        if args.command == "build":
            query = select(SourceArtifactRow.artifact_id).where(
                SourceArtifactRow.status.in_(_INDEXED)
            )
        else:
            query = select(RecordDatasetRow.artifact_id)
        ids = [args.artifact] if args.artifact else list(session.scalars(query))
    failures = 0
    for artifact_id in ids:
        if args.command == "build":
            try:
                row = build_record_dataset(context, artifact_id)
                print(f"{artifact_id} built: {row.record_count} records")
            except DatasetBuildRefused as exc:
                failures += 1
                print(f"{artifact_id} refused: {exc}", file=sys.stderr)
        else:
            with context.sessions() as session:
                dataset = session.get(RecordDatasetRow, artifact_id)
            ok = dataset is not None and context.records.verify(dataset)
            failures += 0 if ok else 1
            print(f"{artifact_id} {'ok' if ok else 'DAMAGED OR MISSING'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
