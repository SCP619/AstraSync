"""Parser isolation (Stage 8, DECISIONS A16): adapters parse in a limited child process."""

import json
from pathlib import Path
from typing import Any

import pytest

from astrasync_api import parser_child
from astrasync_api.config import Settings, SettingsError
from astrasync_api.contract.enums import Environment
from astrasync_api.parser_sandbox import (
    IsolatedAdapter,
    ParserCrashed,
    ParserLimitExceeded,
    ParserLimits,
    ParserRefused,
    _child_environment,
)

challenge = pytest.importorskip("astrasync_data.challenge_reference")
synthetic = pytest.importorskip("astrasync_data.synthetic_scale")
SPEC = "astrasync_data.challenge_reference:ChallengeReferenceAdapter"


def isolated(**limits: Any) -> IsolatedAdapter:
    adapter = challenge.ChallengeReferenceAdapter()
    return IsolatedAdapter(
        SPEC, adapter.source_type, adapter.parser_version, ParserLimits(**limits)
    )


def synthetic_file(tmp_path: Path, rows: int = 300) -> Path:
    path = tmp_path / "scale.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        synthetic.generate(handle, rows=rows, seed=4)
    return path


def test_isolated_records_equal_in_process_records(tmp_path: Path) -> None:
    path = synthetic_file(tmp_path)
    expected = [
        r
        for b in challenge.ChallengeReferenceAdapter().iter_record_batches(path, batch_rows=70)
        for r in b
    ]
    got = [r for b in isolated().iter_record_batches(path, batch_rows=70) for r in b]
    assert len(got) == 300
    assert json.loads(json.dumps(expected)) == got


def test_an_adapter_refusal_is_a_value_error(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    path.write_text("Station number,TX frequency\n1,87.9 MHz\n", encoding="utf-8")
    with pytest.raises(ParserRefused) as caught:
        list(isolated().iter_record_batches(path, batch_rows=10))
    assert isinstance(caught.value, ValueError)  # So ingest quarantines the file.


@pytest.mark.parametrize(
    "limits", [{"memory_mb": 1}, {"timeout_seconds": 0.01}], ids=["memory", "time"]
)
def test_limits_stop_the_parser_and_count_as_unsafe(tmp_path: Path, limits: dict[str, Any]) -> None:
    path = synthetic_file(tmp_path, rows=20_000)
    with pytest.raises(ParserLimitExceeded) as caught:
        list(isolated(**limits).iter_record_batches(path, batch_rows=100))
    assert isinstance(caught.value, ValueError)


def test_other_failures_are_retryable_not_a_verdict(tmp_path: Path) -> None:
    adapter = IsolatedAdapter(
        "astrasync_data.challenge_reference:Missing", "X", "x/1", ParserLimits()
    )
    with pytest.raises(ParserCrashed) as caught:
        list(adapter.iter_record_batches(synthetic_file(tmp_path), batch_rows=10))
    assert not isinstance(caught.value, ValueError)


def test_the_child_gets_no_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTRASYNC_DATABASE_URL", "postgresql://user:secret@db/astrasync")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    environment = _child_environment()
    assert environment["PATH"] == "/usr/bin"
    assert not any("ASTRASYNC" in name or "SECRET" in name for name in environment)


class _Printer:
    """Prints to standard output while parsing, as a careless or hostile adapter might."""

    def iter_record_batches(self, path: Path, *, batch_rows: int) -> Any:
        print('{"done": true}')
        yield [{"forged": False}]


def test_adapter_output_cannot_forge_protocol_lines(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(parser_child, "_load", lambda spec: _Printer())
    assert parser_child.main(["x:y", str(tmp_path / "f"), "5"]) == 0
    out, err = capfd.readouterr()
    lines = [json.loads(line) for line in out.splitlines()]
    assert lines == [{"batch": [{"forged": False}]}, {"done": True}]
    assert '{"done": true}' in err


def test_in_process_parsing_is_refused_outside_demo() -> None:
    with pytest.raises(SettingsError, match="isolated"):
        Settings(environment=Environment.PRODUCTION, parser_isolation="none")
    Settings(environment=Environment.DEMO, parser_isolation="none")
    with pytest.raises(SettingsError):
        Settings(parser_isolation="thread")


def test_memory_check_tolerates_a_parser_that_has_already_exited() -> None:
    """A finished child can leave its last lines in the pipe; the check must not raise."""
    import subprocess
    import sys

    import psutil

    from astrasync_api.parser_sandbox import _tree_rss

    child = subprocess.Popen([sys.executable, "-c", "pass"])  # noqa: S603
    watched = psutil.Process(child.pid)
    child.wait()
    assert _tree_rss(watched) == 0
