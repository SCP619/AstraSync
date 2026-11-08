"""Runs source adapters on untrusted files in a separate, limited process (Stage 8, A16).

The worker never parses an acquired file itself. ``IsolatedAdapter`` starts
``astrasync_api.parser_child`` with:

- an environment holding only what Python needs to start: no database URL, no credentials;
- Python's isolated mode (``-I``): no user site-packages, no current directory on the path;
- a resident-memory limit and a wall-clock limit, enforced by a watchdog over the child process
  tree; a breach kills the child and raises ``ParserLimitExceeded``, a ``ValueError``, so the
  pipeline quarantines the file as unsafe (TR-INT-008, TR-SEC-004). An adapter's own
  ``ValueError`` becomes ``ParserRefused`` (also quarantined); any other failure becomes
  ``ParserCrashed``, which the job retries, because it says nothing about the file;
- JSON lines as the only channel back. Nothing from the child is unpickled or executed.

This is process isolation, not an OS sandbox: the child can still read files the worker's user
can read. Container- or OS-level confinement belongs to the deployment.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

import psutil

# Variables a Python child needs to start on Linux and Windows. Everything else is dropped.
_KEEP_ENV = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL", "TZ")
_POLL_SECONDS = 0.1


class ParserLimitExceeded(ValueError):
    """The parser used more memory or time than allowed; the file is treated as unsafe."""


class ParserRefused(ValueError):
    """The adapter refused the file as unreadable or unsafe (its contract's ``ValueError``)."""


class ParserCrashed(RuntimeError):
    """The parser process failed for another reason. Not a verdict on the file: retryable."""


@dataclass(frozen=True)
class ParserLimits:
    memory_mb: int = 2048
    timeout_seconds: float = 3600.0


def _child_environment() -> dict[str, str]:
    return {name: os.environ[name] for name in _KEEP_ENV if name in os.environ}


def _tree_rss(process: psutil.Process) -> int:
    total = 0
    try:
        children = process.children(recursive=True)
    except psutil.Error:
        # The parser has already exited (its last lines may still be in the pipe): no memory.
        return 0
    for item in (process, *children):
        try:
            total += item.memory_info().rss
        except psutil.Error:
            continue
    return total


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    try:
        root = psutil.Process(process.pid)
        for child in root.children(recursive=True):
            child.kill()
        root.kill()
    except psutil.Error:
        pass
    process.wait()


def _reader(stream: IO[bytes], lines: "queue.Queue[bytes | None]") -> None:
    for line in stream:
        lines.put(line)
    lines.put(None)


class IsolatedAdapter:
    """A ``SourceAdapter`` that delegates to the named adapter in a child process."""

    def __init__(
        self, spec: str, source_type: str, parser_version: str, limits: ParserLimits
    ) -> None:
        self.spec = spec
        self.source_type = source_type
        self.parser_version = parser_version
        self.limits = limits

    def iter_record_batches(
        self, artifact_path: Path, *, batch_rows: int
    ) -> Iterator[list[dict[str, Any]]]:
        process = subprocess.Popen(  # noqa: S603 - fixed module, server-configured spec.
            [
                sys.executable,
                "-I",
                "-m",
                "astrasync_api.parser_child",
                self.spec,
                str(artifact_path),
                str(int(batch_rows)),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_child_environment(),
        )
        if process.stdout is None:  # Unreachable with stdout=PIPE; keeps the type checker exact.
            raise ParserCrashed("no output pipe")
        lines: queue.Queue[bytes | None] = queue.Queue(maxsize=4)
        threading.Thread(target=_reader, args=(process.stdout, lines), daemon=True).start()
        watched = psutil.Process(process.pid)
        deadline = time.monotonic() + self.limits.timeout_seconds
        limit_bytes = self.limits.memory_mb * 1024 * 1024
        finished = False
        try:
            while True:
                if time.monotonic() > deadline:
                    raise ParserLimitExceeded("time limit")
                if _tree_rss(watched) > limit_bytes:
                    raise ParserLimitExceeded("memory limit")
                try:
                    line = lines.get(timeout=_POLL_SECONDS)
                except queue.Empty:
                    continue
                if line is None:
                    raise ParserCrashed("the parser process ended without a result")
                try:
                    message = json.loads(line)
                except ValueError as exc:
                    raise ParserCrashed("unreadable protocol line") from exc
                if not isinstance(message, dict):
                    raise ParserCrashed("unexpected protocol message")
                if "batch" in message and isinstance(message["batch"], list):
                    yield message["batch"]
                elif message.get("done") is True:
                    finished = True
                    return
                elif message.get("error") == "ValueError":
                    raise ParserRefused("the adapter refused the file")
                elif "error" in message:
                    raise ParserCrashed(f"parser error: {str(message['error'])[:64]}")
                else:
                    raise ParserCrashed("unexpected protocol message")
        finally:
            if finished:
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    _kill_tree(process)
            else:
                _kill_tree(process)
