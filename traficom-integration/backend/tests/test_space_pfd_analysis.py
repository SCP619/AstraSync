"""SPACE_PFD_FREE_SPACE (astrasync-core-lib) through the real analysis runner and case API.

Scenario values are made up for the test. No criterion resolver is registered, so no limit or
margin can appear: the result is a screening number with criterion status unverified.
"""

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_cases import (  # noqa: F401 - fixtures used by name.
    Bearer,
    analyse,
    candidate,
    case_of,
    registered,
)

from astrasync_api.analysis import AnalysisPlugins
from astrasync_api.ingest import PipelineContext
from astrasync_api.worker import WorkerRuntime

space_pfd = pytest.importorskip("astrasync_physics.space_pfd")


@pytest.fixture
def runtime(sessions: sessionmaker[Session], secure_app: FastAPI) -> WorkerRuntime:
    method = space_pfd.SpacePfdFreeSpace()
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test-worker",
        analysis=AnalysisPlugins(methods={method.method_id: method}, build_sha="test-build"),
    )


def runs_by_id(run: Any) -> dict[str, Any]:
    return {item.method_id: item for item in run.method_runs}


def test_free_space_pfd_runs_with_a_trace_and_no_margin(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(
        sessions,
        scenario={
            space_pfd.SCENARIO_KEY: {
                "eirp_toward_receiver_dbw": 50.0,
                "slant_range_m": 35_786_000.0,
                "eirp_reference_bandwidth_hz": 4000.0,
            }
        },
    )
    run = analyse(secure_client, runtime, bearer(), case_id)
    pfd = runs_by_id(run)["SPACE_PFD_FREE_SPACE"]
    assert pfd.execution_status == "SUCCEEDED"
    assert pfd.numeric_value == pytest.approx(-112.0663617921, abs=1e-9)
    assert pfd.unit == "dB(W/m^2)"
    assert pfd.reference_bandwidth_hz == 4000.0
    assert pfd.method_version == space_pfd.METHOD_VERSION
    assert pfd.implementation_sha == space_pfd.IMPLEMENTATION_SHA
    assert pfd.inputs["slant_range_m"] == 35_786_000.0
    assert pfd.assumptions
    # Other catalogue methods are still listed, not hidden, and produce no number.
    for method_id in ("SPACE_PFD_DIRECTIONAL", "SPACE_EPFD_NGSO"):
        assert runs_by_id(run)[method_id].numeric_value is None
    # No resolver, so no criterion check and no margin.
    assert all(check.margin_db is None for check in run.criterion_checks)
    assert case_of(secure_client, bearer(), case_id).finding_status != "POTENTIAL_LIMIT_EXCEEDANCE"


def test_missing_inputs_leave_the_method_unrun(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(
        sessions, scenario={space_pfd.SCENARIO_KEY: {"eirp_toward_receiver_dbw": 50.0}}
    )
    run = analyse(secure_client, runtime, bearer(), case_id)
    pfd = runs_by_id(run)["SPACE_PFD_FREE_SPACE"]
    assert pfd.applicability == "INSUFFICIENT_DATA"
    assert pfd.execution_status == "NOT_RUN"
    assert pfd.numeric_value is None
    assert pfd.missing_fields == [f"{space_pfd.SCENARIO_KEY}.slant_range_m"]
