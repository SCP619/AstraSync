"""Object storage for source masters. Bytes never go into the database or into process memory.

``ObjectStore`` is the seam for managed multipart storage. ``LocalObjectStore`` is for the single
machine demo profile only (config.py refuses it elsewhere): it provides no encryption at rest.
"""

import hashlib
import os
import re
import shutil
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_READ_SIZE = 1024 * 1024


class ObjectKeyError(ValueError):
    pass


@dataclass(frozen=True)
class AssembledObject:
    path: Path
    size_bytes: int
    sha256: str


class PartWriter(Protocol):
    size_bytes: int

    def write(self, chunk: bytes) -> None: ...
    def commit(self) -> str: ...
    def discard(self) -> None: ...


class ObjectStore(Protocol):
    def begin_part(self, upload_id: str, part_number: int) -> PartWriter: ...
    def assemble(self, upload_id: str, part_numbers: Sequence[int]) -> AssembledObject: ...
    def new_staging_path(self) -> Path: ...
    def hash_file(self, path: Path) -> AssembledObject: ...
    def promote(self, staged: Path, key_segments: Sequence[str]) -> str: ...
    def quarantine(self, staged: Path, key_segments: Sequence[str]) -> str: ...
    def local_path(self, key: str) -> Path: ...
    def open_read(self, key: str) -> BinaryIO: ...
    def discard_upload(self, upload_id: str) -> None: ...


class _LocalPartWriter:
    def __init__(self, target: Path) -> None:
        self._target = target
        self._temp = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
        self._file: BinaryIO = self._temp.open("xb")
        self._hash = hashlib.sha256()
        self.size_bytes = 0

    def write(self, chunk: bytes) -> None:
        self._file.write(chunk)
        self._hash.update(chunk)
        self.size_bytes += len(chunk)

    def commit(self) -> str:
        self._file.close()
        # A re-sent part replaces the old one whole, so a retry never leaves a mixed part.
        os.replace(self._temp, self._target)
        return self._hash.hexdigest()

    def discard(self) -> None:
        self._file.close()
        self._temp.unlink(missing_ok=True)


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._staging = self._root / "staging"
        self._staging.mkdir(parents=True, exist_ok=True)

    def begin_part(self, upload_id: str, part_number: int) -> PartWriter:
        directory = self._upload_dir(upload_id)
        directory.mkdir(parents=True, exist_ok=True)
        return _LocalPartWriter(directory / f"{part_number:08d}.part")

    def assemble(self, upload_id: str, part_numbers: Sequence[int]) -> AssembledObject:
        """Hash the final assembled bytes. Part digests alone do not prove the whole file."""
        directory = self._upload_dir(upload_id)
        target = directory / "assembled.bin"
        digest = hashlib.sha256()
        size = 0
        with target.open("wb") as output:
            for number in part_numbers:
                with (directory / f"{number:08d}.part").open("rb") as part:
                    while chunk := part.read(_READ_SIZE):
                        output.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
        return AssembledObject(target, size, digest.hexdigest())

    def new_staging_path(self) -> Path:
        return self._staging / f"{uuid4().hex}.download"

    def hash_file(self, path: Path) -> AssembledObject:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as source:
            while chunk := source.read(_READ_SIZE):
                digest.update(chunk)
                size += len(chunk)
        return AssembledObject(path, size, digest.hexdigest())

    def promote(self, staged: Path, key_segments: Sequence[str]) -> str:
        return self._place(staged, ("masters", *key_segments))

    def quarantine(self, staged: Path, key_segments: Sequence[str]) -> str:
        return self._place(staged, ("quarantine", *key_segments))

    def local_path(self, key: str) -> Path:
        return self._resolve(key.split("/"))

    def open_read(self, key: str) -> BinaryIO:
        return self.local_path(key).open("rb")

    def discard_upload(self, upload_id: str) -> None:
        shutil.rmtree(self._upload_dir(upload_id), ignore_errors=True)

    def _upload_dir(self, upload_id: str) -> Path:
        return self._resolve(("staging", "uploads", upload_id))

    def _place(self, staged: Path, segments: Sequence[str]) -> str:
        target = self._resolve(segments)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            # Keys contain the content hash, so a retry finds identical bytes. Never overwrite.
            staged.unlink(missing_ok=True)
        else:
            os.replace(staged, target)
            target.chmod(stat.S_IREAD)
        return "/".join(segments)

    def _resolve(self, segments: Sequence[str]) -> Path:
        for segment in segments:
            if not _SEGMENT.match(segment):
                raise ObjectKeyError("invalid object key")
        path = self._root.joinpath(*segments).resolve()
        if not path.is_relative_to(self._root):
            raise ObjectKeyError("object key escapes the store")
        return path
