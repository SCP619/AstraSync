"""The criteria-registry resolver: only complete, cited, approved entries load, and a margin
appears only when every declared condition is matched.

Every limit, citation and approval below is **made up for the test**. None is a real ITU or
national limit; the URLs are `.invalid`.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker
from test_cases import (  # noqa: F401 - fixtures used by name.
    Bearer,
    analyse,
    candidate,
    case_of,
    registered,
)

from astrasync_api.analysis import AnalysisPlugins
from astrasync_api.criteria import CriteriaRegistry, RegistryCriterionResolver, load_registry
from astrasync_api.ingest import PipelineContext
from astrasync_api.worker import WorkerRuntime

space_pfd = pytest.importorskip("astrasync_physics.space_pfd")


def made_up_criterion(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "criterion_ref_id": "TEST-ONLY-PFD-LIMIT",
        "regulatory_scope": "TEST-ONLY scope, not a regulation",
        "source": {
            "document": "Made-up test document",
            "edition": "T1",
            "edition_date": "2000-01-01",
        },
        "citation": {
            "reference_id": "TEST-DOC",
            "section_id": "TEST-SECTION",
            "source_url": "https://example.invalid/test-only",
        },
        "metric_kind": "PFD",
        "comparison_operator": "UPPER_BOUND",
        "limit_value": -120.0,
        "limit_unit": "dB(W/m^2)",
        "limit_reference_bandwidth_hz": 4000.0,
        "frequency_min_hz": 10.7e9,
        "frequency_max_hz": 11.7e9,
        "frequency_key": "space_pfd_free_space.frequency_hz",
        "conditions": {"space_pfd_free_space.direction": "space-to-Earth"},
        "approval": {
            "approved_by": "test reviewer",
            "approved_at": "2000-01-02",
            "review_reference": "TEST-REVIEW-1",
        },
    }
    entry.update(overrides)
    return entry


def registry(*entries: dict[str, Any]) -> CriteriaRegistry:
    return CriteriaRegistry.model_validate({"criteria": list(entries)})


def scenario(**extra: Any) -> dict[str, Any]:
    return {
        space_pfd.SCENARIO_KEY: {
            "eirp_toward_receiver_dbw": 50.0,
            "slant_range_m": 35_786_000.0,
            "eirp_reference_bandwidth_hz": 4000.0,
            **extra,
        }
    }


def runtime_with(
    sessions: sessionmaker[Session], app: FastAPI, resolver: RegistryCriterionResolver
) -> WorkerRuntime:
    method = space_pfd.SpacePfdFreeSpace()
    return WorkerRuntime(
        context=PipelineContext(sessions=sessions, store=app.state.library.store, adapters={}),
        clients={},
        worker_id="test-worker",
        analysis=AnalysisPlugins(
            methods={method.method_id: method}, criterion_resolver=resolver, build_sha="test"
        ),
    )


@pytest.mark.parametrize(
    "broken",
    [
        {"approval": None},
        {"citation": None},
        {"source": {"document": "x", "edition": "", "edition_date": "2000-01-01"}},
        {"citation": {"reference_id": "x", "section_id": "y", "source_url": "not a url"}},
        {"frequency_min_hz": 2e9, "frequency_max_hz": 1e9},
        {"surprise_field": 1},
    ],
)
def test_incomplete_entries_refuse_the_whole_file(tmp_path: Path, broken: dict[str, Any]) -> None:
    path = tmp_path / "criteria.json"
    path.write_text(
        json.dumps({"criteria": [made_up_criterion(), made_up_criterion(**broken)]}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_registry(path)


def test_duplicate_ids_are_refused() -> None:
    with pytest.raises(ValidationError):
        registry(made_up_criterion(), made_up_criterion())


def test_the_resolver_needs_a_registry_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ASTRASYNC_CRITERIA_REGISTRY", raising=False)
    with pytest.raises(ValueError, match="no criteria registry"):
        RegistryCriterionResolver()


def method_run(**overrides: Any) -> dict[str, Any]:
    return {"metric_kind": "PFD", "unit": "dB(W/m^2)", "inputs": {}, **overrides}


def test_selection_by_metric_frequency_and_conditions() -> None:
    resolver = RegistryCriterionResolver(registry(made_up_criterion()))
    good = {"scenario": scenario(frequency_hz=11.2e9, direction="space-to-Earth")}
    [check] = resolver.resolve(method_run(), good)
    assert check["applicable"] == "VERIFIED"
    assert check["limit_value"] == -120.0
    assert "TEST-REVIEW-1" in check["review_note"]
    assert resolver.resolve(method_run(metric_kind="EPFD"), good) == []
    wrong_band = {"scenario": scenario(frequency_hz=12.5e9, direction="space-to-Earth")}
    assert resolver.resolve(method_run(), wrong_band) == []
    wrong_direction = {"scenario": scenario(frequency_hz=11.2e9, direction="Earth-to-space")}
    assert resolver.resolve(method_run(), wrong_direction) == []


def test_unknown_values_leave_the_criterion_unverified() -> None:
    resolver = RegistryCriterionResolver(registry(made_up_criterion()))
    [check] = resolver.resolve(method_run(), {"scenario": scenario()})
    assert check["applicable"] == "UNVERIFIED"
    assert "space_pfd_free_space.frequency_hz" in check["review_note"]
    assert "space_pfd_free_space.direction" in check["review_note"]


def test_a_margin_appears_only_for_a_fully_matched_criterion(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    secure_app: FastAPI,
) -> None:
    resolver = RegistryCriterionResolver(registry(made_up_criterion()))
    runtime = runtime_with(sessions, secure_app, resolver)

    matched = candidate(
        sessions, scenario=scenario(frequency_hz=11.2e9, direction="space-to-Earth")
    )
    run = analyse(secure_client, runtime, bearer(), matched)
    [check] = run.criterion_checks
    pfd = next(m for m in run.method_runs if m.method_id == "SPACE_PFD_FREE_SPACE")
    assert check.comparison_status == "COMPARED"
    # The runner computes the margin; the made-up limit is -120 dB(W/m^2).
    assert check.margin_db == pytest.approx(pfd.numeric_value - (-120.0), abs=1e-9)
    assert check.citation is not None and check.citation.reference_id == "TEST-DOC"

    unknown = candidate(sessions, scenario=scenario())
    run = analyse(secure_client, runtime, bearer(), unknown)
    [check] = run.criterion_checks
    assert check.applicable == "UNVERIFIED"
    assert check.margin_db is None
    assert case_of(secure_client, bearer(), unknown).finding_status != (
        "POTENTIAL_LIMIT_EXCEEDANCE"
    )

    other_bandwidth = RegistryCriterionResolver(
        registry(made_up_criterion(limit_reference_bandwidth_hz=1e6))
    )
    runtime = runtime_with(sessions, secure_app, other_bandwidth)
    mismatch = candidate(
        sessions, scenario=scenario(frequency_hz=11.2e9, direction="space-to-Earth")
    )
    [check] = analyse(secure_client, runtime, bearer(), mismatch).criterion_checks
    assert check.comparison_status == "NOT_COMPARABLE"
    assert check.margin_db is None
