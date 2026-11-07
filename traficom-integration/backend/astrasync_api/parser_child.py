"""Runs one ``SourceAdapter`` over one file in a separate process (see ``parser_sandbox``).

Started by the worker as ``python -I -m astrasync_api.parser_child <module:attr> <path> <rows>``
with a scrubbed environment. It writes one JSON object per line to its original standard output:
``{"batch": [...]}`` for each batch, then ``{"done": true}``; or ``{"error": "<kind>"}``. Only the
exception class name crosses the boundary, never its message, which may hold file content.
Anything the adapter prints goes to standard error instead, so it cannot forge protocol lines.
"""

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def _load(spec: str) -> Any:
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise SystemExit(2)
    return getattr(importlib.import_module(module_name), attribute)()


def main(argv: list[str]) -> int:
    spec, path, rows = argv
    protocol = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", newline="\n")
    sys.stdout = sys.stderr  # Adapter output never reaches the protocol stream.

    def send(message: dict[str, Any]) -> None:
        protocol.write(json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n")
        protocol.flush()

    try:
        adapter = _load(spec)
        for batch in adapter.iter_record_batches(Path(path), batch_rows=int(rows)):
            send({"batch": batch})
    except ValueError:
        send({"error": "ValueError"})  # The adapter contract's "unreadable or unsafe file".
        return 3
    except Exception as exc:  # noqa: BLE001 - reported to the parent by class name only.
        send({"error": type(exc).__name__})
        return 4
    send({"done": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
