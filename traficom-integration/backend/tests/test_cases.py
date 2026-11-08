"""IPD stage 5: method matrix, criterion gate, drafts, human review and evidence export."""

import os
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from conftest import TENANT_A, TENANT_B, Users
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from support.demo_plugins import DEMO_UNIT, DemoDraftAgent, DemoEchoMethod, DemoEchoResolver

from astrasync_api import admin, analysis, cases
from astrasync_api.analysis import AnalysisPlugins
from astrasync_api.case_tables import AnalysisRunRow, DraftRow, EvidenceLinkRow, MethodRunRow
from astrasync_api.contract.enums import (
    IssueDomain,
    SourceType,
    UsageClassification,
)
from astrasync_api.contract.models import (
    AnalysisRun,
    CaseCandidate,
    CaseDetail,
    CaseList,
    EvidencePack,
    MethodMatrix,
    ReviewEvent,
)
from astrasync_api.db import AuditEvent, ResourceEntitlement
from astrasync_api.ingest import PipelineContext
from astrasync_api.library_tables import OutboxEventRow
from astrasync_api.worker import WorkerRuntime, load_analysis_plugins, run_until_idle

Bearer = Callable[..., dict[str, str]]
SOURCE = "SRC-CASES"
RESTRICTED = "SRC-CASES-RESTRICTED"
OTHER = "SRC-CASES-OTHER"


def criterion(**overrides: Any) -> dict[str, Any]:
    return {
        "criterion_ref_id": "DEMO-CRITERION-NOT-REAL",
        "regulatory_scope": "DEMO",
        "applicable": "VERIFIED",
        "matching_conditions": {},
        "limit_value": -100.0,
        "limit_unit": DEMO_UNIT,
        "limit_reference_bandwidth_hz": None,
        "comparison_operator": "UPPER_BOUND",
        "review_note": None,
        "citation": {
            "reference_id": "DEMO-REF",
            "section_id": "DEMO-SECTION",
            "source_url": "https://example.invalid/demo",
        },
        **overrides,
    }


@pytest.fixture(autouse=True)
def registered(request: pytest.FixtureRequest) -> None:
    if "users" not in request.fixturenames:
        return
    request.getfixturevalue("users")
    sessions = request.getfixturevalue("sessions")
    common: dict[str, Any] = {
        "publisher": "Demo publisher",
        "domain": IssueDomain.SPACE,
        "source_type": SourceType.SPACE_IFIC,
        "rights_basis": "Synthetic test data",
        "is_synthetic": True,
    }
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=SOURCE,
        classification=UsageClassification.INTERNAL,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_A,
        source_id=RESTRICTED,
        classification=UsageClassification.RESTRICTED,
        **common,
    )
    admin.register_source(
        sessions,
        tenant_id=TENANT_B,
        source_id=OTHER,
        classification=UsageClassification.INTERNAL,
        **common,
    )


def candidate(sessions: sessionmaker[Session], **overrides: Any) -> str:
    tenant = overrides.pop("tenant", TENANT_A)
    values: dict[str, Any] = {
        "notice_uid": uuid4().hex,
        "notice_id": "SYNTHETIC-NOTICE-001",
        "source_id": SOURCE,
        "source_issue_id": "DEMO-IFIC-001",
        "administration": "DEMO",
        "domain": "SPACE",
        "change_type": "NEW",
        "frequency_start_mhz": 10700.0,
        "frequency_end_mhz": 10720.0,
        "relevance": {
            "label": "FREQUENCY_MATCH",
            "reason_codes": ["BAND_OVERLAP"],
            "rule_version": "demo",
            "overlap_start_mhz": 10700.0,
            "overlap_end_mhz": 10720.0,
            "frequency_match": True,
            "service_match": None,
            "geometry_match": None,
            "technical_data_ready": False,
            "criterion_available": False,
        },
        "scenario_id": "DEMO-SCENARIO",
        "scenario": {},
        **overrides,
    }
    return cases.upsert_candidate(sessions, tenant, CaseCandidate(**values))


@pytest.fixture
def plugins() -> AnalysisPlugins:
    return AnalysisPlugins(
        methods={DemoEchoMethod.method_id: DemoEchoMethod()},
        criterion_resolver=DemoEchoResolver(),
        build_sha="test-build",
    )


@pytest.fixture
def runtime(
    sessions: sessionmaker[Session], secure_app: FastAPI, plugins: AnalysisPlugins
) -> WorkerRuntime:
    return WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test-worker",
        analysis=plugins,
    )


def analyse(
    client: TestClient, runtime: WorkerRuntime, headers: dict[str, str], case_id: str
) -> AnalysisRun:
    accepted = client.post(
        f"/api/v1/cases/{case_id}/analyse",
        json={},
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )
    assert accepted.status_code == 202, accepted.text
    run_until_idle(runtime)
    run = client.get(f"/api/v1/analyses/{accepted.json()['analysis_run_id']}", headers=headers)
    assert run.status_code == 200, run.text
    return AnalysisRun.model_validate(run.json())


def case_of(client: TestClient, headers: dict[str, str], case_id: str) -> CaseDetail:
    response = client.get(f"/api/v1/cases/{case_id}", headers=headers)
    assert response.status_code == 200, response.text
    return CaseDetail.model_validate(response.json())


def review(client: TestClient, headers: dict[str, str], case_id: str, **body: Any) -> Any:
    return client.post(
        f"/api/v1/cases/{case_id}/reviews",
        json={"decision_reason": "Evidence checked.", **body},
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )


def make_draft(
    client: TestClient,
    headers: dict[str, str],
    case_id: str,
    run_id: str,
    draft_type: str = "REQUEST_INFORMATION",
) -> Any:
    return client.post(
        f"/api/v1/cases/{case_id}/drafts",
        json={"draft_type": draft_type, "analysis_run_id": run_id},
        headers={**headers, "Idempotency-Key": uuid4().hex},
    )


# --- Method matrix ----------------------------------------------------------------------------


def test_every_candidate_method_gets_a_row_with_no_invented_number(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    states = {item.method_id: item for item in run.method_runs}
    expected = {entry.method_id for entry in analysis.CANDIDATES[analysis.CaseDomain.SPACE]}
    assert expected | {DemoEchoMethod.method_id} == set(states)
    for method_id in expected:
        assert states[method_id].applicability == "NOT_IMPLEMENTED"
        assert states[method_id].numeric_value is None
        assert states[method_id].reason_codes == ["NOT_IMPLEMENTED"]
    echo = states[DemoEchoMethod.method_id]
    assert echo.applicability == "INSUFFICIENT_DATA"
    assert echo.missing_fields == ["demo_value"]
    assert echo.numeric_value is None
    assert run.analysis_status == "BLOCKED_BY_INPUTS"

    case = case_of(secure_client, bearer(), case_id)
    assert case.finding_status == "INSUFFICIENT_DATA"
    assert case.margin_db is None
    assert case.method_summary.model_dump() == {"succeeded": 0, "candidates": 6}


def test_terrestrial_case_never_lists_space_methods(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions, domain="TERRESTRIAL")
    run = analyse(secure_client, runtime, bearer(), case_id)
    ids = {item.method_id for item in run.method_runs}
    assert "TERR_P1546" in ids
    assert not any(method_id.startswith("SPACE_") for method_id in ids)


class _Broken:
    method_version = "broken/1"

    def __init__(self, method_id: str, assess: Any, calculate: Any = None) -> None:
        self.method_id = method_id
        self._assess = assess
        self._calculate = calculate

    def assess_applicability(self, scenario: dict[str, Any]) -> dict[str, Any]:
        return self._assess(scenario)

    def calculate(self, scenario: dict[str, Any]) -> dict[str, Any]:
        return self._calculate(scenario)


def _assessment(method_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "method_id": method_id,
        "method_version": "broken/1",
        "applicability": "APPLICABLE",
        "reason_codes": [],
        "missing_fields": [],
        "metric_kind": "PFD",
        **overrides,
    }


def _raise(_scenario: dict[str, Any]) -> dict[str, Any]:
    raise RuntimeError("SECRET-INTERNAL-DETAIL")


@pytest.mark.parametrize(
    ("assess", "calculate", "reason"),
    [
        pytest.param(_raise, None, "INVALID_ASSESSMENT", id="assess-raises"),
        pytest.param(
            lambda _s: {"nonsense": True}, None, "INVALID_ASSESSMENT", id="bad-assessment"
        ),
        pytest.param(
            lambda _s: _assessment("BROKEN", applicability="INSUFFICIENT_DATA"),
            None,
            "INVALID_ASSESSMENT",
            id="insufficient-without-missing-fields",
        ),
        pytest.param(lambda _s: _assessment("BROKEN"), _raise, "CALCULATION_FAILED", id="raises"),
        pytest.param(
            lambda _s: _assessment("BROKEN"),
            lambda _s: {"method_id": "BROKEN", "numeric_value": float("nan")},
            "CALCULATION_FAILED",
            id="nan-result",
        ),
        pytest.param(
            lambda _s: _assessment("BROKEN"),
            lambda s: {**DemoEchoMethod().calculate({"demo_value": 1.0}), "method_id": "OTHER"},
            "CALCULATION_FAILED",
            id="result-for-another-method",
        ),
        pytest.param(
            lambda _s: _assessment("BROKEN"),
            lambda s: {
                **DemoEchoMethod().calculate({"demo_value": 1.0, "demo_metric": "EPFD"}),
                "method_id": "BROKEN",
            },
            "CALCULATION_FAILED",
            id="epfd-result-for-a-pfd-method",
        ),
    ],
)
def test_broken_method_fails_alone_with_no_value(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    secure_app: FastAPI,
    assess: Any,
    calculate: Any,
    reason: str,
) -> None:
    runtime = WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test",
        analysis=AnalysisPlugins(
            methods={
                "BROKEN": _Broken("BROKEN", assess, calculate),
                DemoEchoMethod.method_id: DemoEchoMethod(),
            }
        ),
    )
    case_id = candidate(sessions, scenario={"demo_value": -101.0})
    run = analyse(secure_client, runtime, bearer(), case_id)
    states = {item.method_id: item for item in run.method_runs}
    assert states["BROKEN"].execution_status == "FAILED"
    assert states["BROKEN"].numeric_value is None
    assert states["BROKEN"].reason_codes == [reason]
    assert states[DemoEchoMethod.method_id].numeric_value == -101.0
    assert run.analysis_status == "READY"
    assert "SECRET-INTERNAL-DETAIL" not in str(run.model_dump())


def test_pfd_and_epfd_are_never_grouped_for_comparison(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    secure_app: FastAPI,
) -> None:
    def make(method_id: str, metric: str, bandwidth: float | None = None) -> _Broken:
        return _Broken(
            method_id,
            lambda _s: _assessment(method_id, metric_kind=metric),
            lambda _s: {
                **DemoEchoMethod().calculate(
                    {"demo_value": -1.0, "demo_metric": metric, "demo_bandwidth_hz": bandwidth}
                ),
                "method_id": method_id,
            },
        )

    methods = {
        "A_PFD": make("A_PFD", "PFD"),
        "B_PFD": make("B_PFD", "PFD"),
        "C_EPFD": make("C_EPFD", "EPFD"),
        "D_PFD_OTHER_BANDWIDTH": make("D_PFD_OTHER_BANDWIDTH", "PFD", 4000.0),
    }
    runtime = WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test",
        analysis=AnalysisPlugins(methods=methods),
    )
    case_id = candidate(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    matrix = MethodMatrix.model_validate(
        secure_client.get(
            f"/api/v1/analyses/{run.analysis_run_id}/methods", headers=bearer()
        ).json()
    )
    groups = [
        sorted(run_id.rsplit("-", 1)[-1] for run_id in group.method_run_ids)
        for group in matrix.comparison_groups
    ]
    assert groups == [["A_PFD", "B_PFD"]]


# --- Criterion gate ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected_margin"),
    [(-102.3, -2.3), (-97.7, 2.3)],
    ids=["below-limit", "above-limit"],
)
def test_margin_is_predicted_minus_limit_with_its_sign(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    value: float,
    expected_margin: float,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": value, "demo_criteria": [criterion()]})
    run = analyse(secure_client, runtime, bearer(), case_id)
    check = run.criterion_checks[0]
    assert check.margin_db == pytest.approx(expected_margin)
    case = case_of(secure_client, bearer(), case_id)
    assert case.margin_db == pytest.approx(expected_margin)
    assert case.criterion_status == "VERIFIED"
    if expected_margin > 0:
        assert case.finding_status == "POTENTIAL_LIMIT_EXCEEDANCE"
    else:
        # A margin below one criterion is still for an expert, never an automatic all-clear.
        assert case.finding_status == "EXPERT_REVIEW_REQUIRED"


def test_a_margin_supplied_by_a_resolver_is_ignored(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    forged = criterion(margin_db=999.0, comparison_status="NOT_COMPARABLE")
    case_id = candidate(sessions, scenario={"demo_value": -102.3, "demo_criteria": [forged]})
    run = analyse(secure_client, runtime, bearer(), case_id)
    assert run.criterion_checks[0].margin_db == pytest.approx(-2.3)


@pytest.mark.parametrize(
    ("overrides", "status"),
    [
        pytest.param({"applicable": "UNVERIFIED"}, "CRITERION_UNVERIFIED", id="unverified"),
        pytest.param({"applicable": "NOT_APPLICABLE"}, "CRITERION_UNVERIFIED", id="not-applicable"),
        pytest.param({"limit_unit": "OTHER-UNIT"}, "NOT_COMPARABLE", id="unit-mismatch"),
        pytest.param(
            {"limit_reference_bandwidth_hz": 4000.0}, "NOT_COMPARABLE", id="bandwidth-mismatch"
        ),
        pytest.param({"citation": None}, "NOT_COMPARABLE", id="no-citation"),
        pytest.param({"limit_value": None}, "NOT_COMPARABLE", id="no-limit"),
        pytest.param({"comparison_operator": "LOWER_BOUND"}, "NOT_COMPARABLE", id="lower-bound"),
        pytest.param(
            {"matching_conditions": {"metric_kind": "EPFD"}},
            "NOT_COMPARABLE",
            id="criterion-for-epfd",
        ),
        pytest.param(
            {"matching_conditions": {"time_percentage": 1.0}},
            "NOT_COMPARABLE",
            id="time-statistics-mismatch",
        ),
    ],
)
def test_no_margin_or_exceedance_without_a_matching_verified_criterion(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    overrides: dict[str, Any],
    status: str,
) -> None:
    case_id = candidate(
        sessions, scenario={"demo_value": -50.0, "demo_criteria": [criterion(**overrides)]}
    )
    run = analyse(secure_client, runtime, bearer(), case_id)
    check = run.criterion_checks[0]
    assert check.margin_db is None
    assert check.comparison_status == status
    case = case_of(secure_client, bearer(), case_id)
    assert case.margin_db is None
    assert case.finding_status == "EXPERT_REVIEW_REQUIRED"


def test_unusable_criterion_is_kept_as_unverified(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(
        sessions, scenario={"demo_value": -50.0, "demo_criteria": [{"limit_value": "not a number"}]}
    )
    run = analyse(secure_client, runtime, bearer(), case_id)
    assert run.criterion_checks[0].applicable == "UNVERIFIED"
    assert run.criterion_checks[0].margin_db is None


def test_no_resolver_means_a_value_with_no_margin(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    secure_app: FastAPI,
) -> None:
    runtime = WorkerRuntime(
        context=PipelineContext(
            sessions=sessions, store=secure_app.state.library.store, adapters={}
        ),
        clients={},
        worker_id="test",
        analysis=AnalysisPlugins(methods={DemoEchoMethod.method_id: DemoEchoMethod()}),
    )
    case_id = candidate(sessions, scenario={"demo_value": -50.0})
    run = analyse(secure_client, runtime, bearer(), case_id)
    assert run.criterion_checks == []
    case = case_of(secure_client, bearer(), case_id)
    assert case.lead_metric.numeric_value == -50.0
    assert case.lead_metric.unit == DEMO_UNIT
    assert case.margin_db is None
    assert case.finding_status == "EXPERT_REVIEW_REQUIRED"


def test_exceedance_outbox_event_is_emitted_once(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": -50.0, "demo_criteria": [criterion()]})
    analyse(secure_client, runtime, bearer(), case_id)
    with sessions() as session:
        kinds = session.scalars(select(OutboxEventRow.event_kind)).all()
    assert kinds.count("CRITERION_CHECKED") == 1


# --- Immutability and reproducibility ---------------------------------------------------------


def test_a_rerun_is_a_new_run_and_the_old_one_is_untouched(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": -101.0})
    first = analyse(secure_client, runtime, bearer(), case_id)
    second = analyse(secure_client, runtime, bearer(), case_id)
    assert first.analysis_run_id != second.analysis_run_id
    assert (
        case_of(secure_client, bearer(), case_id).latest_analysis_run_id == second.analysis_run_id
    )
    again = AnalysisRun.model_validate(
        secure_client.get(f"/api/v1/analyses/{first.analysis_run_id}", headers=bearer()).json()
    )
    assert again.method_runs == first.method_runs
    assert first.input_snapshot_sha256 == second.input_snapshot_sha256
    assert first.software_commit_sha == "test-build"
    assert first.method_registry_version.startswith("sha256:")


def test_repeated_analyse_request_starts_one_run(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    headers = {**bearer(), "Idempotency-Key": "same-key-1"}
    first = secure_client.post(f"/api/v1/cases/{case_id}/analyse", json={}, headers=headers).json()
    second = secure_client.post(f"/api/v1/cases/{case_id}/analyse", json={}, headers=headers).json()
    assert first["analysis_run_id"] == second["analysis_run_id"]
    assert first["job_id"] == second["job_id"]


def test_retry_after_a_crash_does_not_duplicate_results(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    from datetime import timedelta

    from astrasync_api import jobs

    case_id = candidate(sessions, scenario={"demo_value": -1.0})
    secure_client.post(
        f"/api/v1/cases/{case_id}/analyse",
        json={},
        headers={**bearer(), "Idempotency-Key": uuid4().hex},
    )
    assert jobs.claim(sessions, "dead-worker", lease=timedelta(seconds=-1)) is not None
    run_until_idle(runtime)
    with sessions() as session:
        run = session.scalars(select(AnalysisRunRow)).one()
        rows = session.scalars(select(MethodRunRow)).all()
    assert run.analysis_status == "READY"
    assert len(rows) == 6


def test_analyse_rejects_another_scenario(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    response = secure_client.post(
        f"/api/v1/cases/{candidate(sessions)}/analyse",
        json={"scenario_id": "SOMETHING-ELSE"},
        headers={**bearer(), "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 409


@pytest.mark.skipif(
    not os.environ.get("ASTRASYNC_TEST_DATABASE_URL"), reason="PostgreSQL trigger only"
)
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE method_runs SET ordinal = 99",
        "DELETE FROM method_runs",
        "UPDATE review_events SET decision_reason = 'changed'",
        "DELETE FROM review_events",
    ],
)
def test_results_and_decisions_are_immutable_on_postgresql(
    engine: Engine,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    statement: str,
) -> None:
    case_id = candidate(sessions)
    analyse(secure_client, runtime, bearer(), case_id)
    review(secure_client, bearer("reviewer-a"), case_id, action="FOLLOW_UP")
    with pytest.raises(DBAPIError, match="immutable"), engine.begin() as connection:
        connection.execute(text(statement))


# --- Clients cannot write results -------------------------------------------------------------


def test_no_route_accepts_a_method_result_or_criterion(openapi: dict[str, Any]) -> None:
    writes = [
        (method, path)
        for path, item in openapi["paths"].items()
        for method in item
        if method in ("post", "put", "patch", "delete")
    ]
    assert not [write for write in writes if "method" in write[1] or "criterion" in write[1]]
    body = openapi["components"]["schemas"]
    for name in (
        "AnalyseRequest",
        "DraftCreateRequest",
        "DraftUpdateRequest",
        "ReviewCreateRequest",
    ):
        fields = set(body[name]["properties"])
        assert not fields & {"numeric_value", "margin_db", "limit_value", "status", "actor_id"}


@pytest.mark.parametrize("field", ["numeric_value", "margin_db", "tenant_id", "created_by"])
def test_analyse_rejects_client_supplied_results(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session], field: str
) -> None:
    response = secure_client.post(
        f"/api/v1/cases/{candidate(sessions)}/analyse",
        json={field: 1},
        headers={**bearer(), "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 422


# --- Drafts -----------------------------------------------------------------------------------


@pytest.fixture
def agent_app(secure_app: FastAPI) -> FastAPI:
    secure_app.state.draft_agent = DemoDraftAgent()
    return secure_app


def test_draft_is_unapproved_cited_and_editable(
    agent_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": -1.0})
    run = analyse(secure_client, runtime, bearer(), case_id)
    created = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert created.status_code == 201, created.text
    draft = created.json()
    assert draft["status"] == "DRAFT"
    assert draft["requires_human_review"] is True
    assert draft["source_analysis_run_id"] == run.analysis_run_id
    assert any("test template" in warning for warning in draft["warnings"])

    edited = secure_client.put(
        f"/api/v1/cases/{case_id}/drafts/{draft['draft_id']}",
        json={"content_markdown": "Edited by the analyst."},
        headers=bearer(),
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "EDITED"
    forged = secure_client.put(
        f"/api/v1/cases/{case_id}/drafts/{draft['draft_id']}",
        json={"content_markdown": "x", "status": "APPROVED"},
        headers=bearer(),
    )
    assert forged.status_code == 422
    stored = secure_client.get(f"/api/v1/cases/{case_id}/drafts", headers=bearer()).json()
    assert stored["items"][0]["status"] == "EDITED"


def _with_agent(app: FastAPI, response: Any) -> None:
    class Agent:
        def create_draft(self, _evidence: Any, _draft_type: str) -> Any:
            if isinstance(response, Exception):
                raise response
            return response

    app.state.draft_agent = Agent()


def _agent_payload(run_id: str, **overrides: Any) -> dict[str, Any]:
    return {
        "draft_type": "REQUEST_INFORMATION",
        "analysis_run_id": run_id,
        "explanation_markdown": "x",
        "uncertainties": [],
        "cited_evidence_ids": [],
        "draft_markdown": "Please provide details.",
        "requires_human_review": True,
        **overrides,
    }


@pytest.mark.parametrize(
    "change",
    [
        pytest.param({"cited_evidence_ids": ["FABRICATED-EVIDENCE"]}, id="invented-citation"),
        pytest.param({"requires_human_review": False}, id="no-human-review"),
        pytest.param({"draft_type": "DRAFT_OBJECTION"}, id="different-draft-type"),
        pytest.param({"analysis_run_id": "OTHER-RUN"}, id="different-run"),
        pytest.param({"status": "APPROVED"}, id="self-approval"),
    ],
)
def test_unusable_agent_output_is_rejected_and_nothing_is_stored(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    change: dict[str, Any],
) -> None:
    case_id = candidate(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    _with_agent(secure_app, _agent_payload(run.analysis_run_id, **change))
    response = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_UNAVAILABLE"
    with sessions() as session:
        assert session.scalars(select(DraftRow)).all() == []


def test_unsupported_claim_is_flagged_for_the_reviewer(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    _with_agent(
        secure_app,
        _agent_payload(run.analysis_run_id, draft_markdown="This is a Violation of the rules."),
    )
    response = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    warnings = response.json()["warnings"]
    assert any('"violation"' in warning for warning in warnings)
    assert "This draft cites no evidence." in warnings


def test_agent_failure_leaves_analysis_and_review_working(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    missing = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert missing.status_code == 503
    _with_agent(secure_app, RuntimeError("provider down"))
    failing = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert failing.status_code == 503
    assert "provider down" not in failing.text
    assert case_of(secure_client, bearer(), case_id).latest_analysis_run_id == run.analysis_run_id
    accepted = review(secure_client, bearer("reviewer-a"), case_id, action="NEEDS_MORE_DATA")
    assert accepted.status_code == 201


def test_restricted_data_is_not_sent_to_the_agent_by_default(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
    runtime: WorkerRuntime,
) -> None:
    calls: list[Any] = []

    class Agent:
        def create_draft(self, evidence: Any, _draft_type: str) -> Any:
            calls.append(evidence)
            raise AssertionError("must not be called")

    secure_app.state.draft_agent = Agent()
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id="g",
                subject=users.ids["analyst-a"],
                tenant_id=TENANT_A,
                object_type="source",
                object_id=RESTRICTED,
                classification="RESTRICTED",
                rights=["READ"],
            )
        )
        session.commit()
    case_id = candidate(sessions, source_id=RESTRICTED)
    run = analyse(secure_client, runtime, bearer(), case_id)
    response = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SOURCE_RESTRICTED"
    assert calls == []


def test_evidence_given_to_the_agent_excludes_the_scenario_and_scope(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    captured: list[dict[str, Any]] = []

    class Agent:
        def create_draft(self, evidence: dict[str, Any], draft_type: str) -> Any:
            captured.append(evidence)
            return _agent_payload(evidence["analysis_run_id"], draft_type=draft_type)

    secure_app.state.draft_agent = Agent()
    case_id = candidate(
        sessions, scenario={"demo_value": -1.0, "private_note": "not for the agent"}
    )
    run = analyse(secure_client, runtime, bearer(), case_id)
    assert make_draft(secure_client, bearer(), case_id, run.analysis_run_id).status_code == 201
    assert "scenario" not in captured[0]
    assert "tenant_id" not in captured[0]


# --- Human review -----------------------------------------------------------------------------


def test_approval_requires_a_reviewer_and_records_who_and_why(
    agent_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    users: Users,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": -1.0})
    run = analyse(secure_client, runtime, bearer(), case_id)
    draft_id = make_draft(secure_client, bearer(), case_id, run.analysis_run_id).json()["draft_id"]
    body = {"action": "APPROVE_DRAFT", "draft_id": draft_id}
    for subject in ("analyst-a", "admin-a", "demo-a"):
        assert review(secure_client, bearer(subject), case_id, **body).status_code == 403

    response = review(secure_client, bearer("reviewer-a"), case_id, **body)
    assert response.status_code == 201
    event = ReviewEvent.model_validate(response.json())
    assert event.actor_id == users.ids["reviewer-a"]
    assert event.decision_reason == "Evidence checked."
    drafts = secure_client.get(f"/api/v1/cases/{case_id}/drafts", headers=bearer()).json()["items"]
    assert drafts[0]["status"] == "APPROVED"

    locked = secure_client.put(
        f"/api/v1/cases/{case_id}/drafts/{draft_id}",
        json={"content_markdown": "Changed afterwards"},
        headers=bearer(),
    )
    assert locked.status_code == 409
    again = review(secure_client, bearer("reviewer-a"), case_id, **body)
    assert again.status_code == 409


def test_objection_cannot_be_approved_without_a_verified_criterion(
    agent_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    unverified = candidate(sessions, scenario={"demo_value": -1.0})
    run = analyse(secure_client, runtime, bearer(), unverified)
    draft_id = make_draft(
        secure_client, bearer(), unverified, run.analysis_run_id, "DRAFT_OBJECTION"
    ).json()["draft_id"]
    blocked = review(
        secure_client,
        bearer("reviewer-a"),
        unverified,
        action="APPROVE_DRAFT",
        draft_id=draft_id,
    )
    assert blocked.status_code == 409

    verified = candidate(sessions, scenario={"demo_value": -1.0, "demo_criteria": [criterion()]})
    run = analyse(secure_client, runtime, bearer(), verified)
    draft_id = make_draft(
        secure_client, bearer(), verified, run.analysis_run_id, "DRAFT_OBJECTION"
    ).json()["draft_id"]
    allowed = review(
        secure_client, bearer("reviewer-a"), verified, action="APPROVE_DRAFT", draft_id=draft_id
    )
    assert allowed.status_code == 201


def test_review_rules_and_status(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    reviewer = bearer("reviewer-a")
    case_id = candidate(sessions)
    no_run = review(secure_client, reviewer, case_id, action="ACCEPT_FINDING")
    assert no_run.status_code == 409
    run = analyse(secure_client, runtime, bearer(), case_id)
    other_case = candidate(sessions)
    wrong = review(
        secure_client,
        reviewer,
        other_case,
        action="ACCEPT_FINDING",
        analysis_run_id=run.analysis_run_id,
    )
    assert wrong.status_code == 404
    ok = review(
        secure_client,
        reviewer,
        case_id,
        action="ACCEPT_FINDING",
        analysis_run_id=run.analysis_run_id,
    )
    assert ok.status_code == 201
    case = case_of(secure_client, reviewer, case_id)
    assert case.review_status == "ACCEPTED"
    assert case.reviewer_decision == "ACCEPT_FINDING"
    # A decision never rewrites the deterministic finding.
    assert case.finding_status == "INSUFFICIENT_DATA"
    history = secure_client.get(f"/api/v1/cases/{case_id}/reviews", headers=reviewer).json()
    assert [event["action"] for event in history["items"]] == ["ACCEPT_FINDING"]
    missing_reason = review(
        secure_client, reviewer, case_id, action="FOLLOW_UP", decision_reason=""
    )
    assert missing_reason.status_code == 422


def test_repeated_review_request_records_one_event(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    headers = {**bearer("reviewer-a"), "Idempotency-Key": "same-review"}
    body = {"action": "FOLLOW_UP", "decision_reason": "Check again."}
    first = secure_client.post(f"/api/v1/cases/{case_id}/reviews", json=body, headers=headers)
    second = secure_client.post(f"/api/v1/cases/{case_id}/reviews", json=body, headers=headers)
    assert first.json()["review_event_id"] == second.json()["review_event_id"]


# --- Export and access ------------------------------------------------------------------------


def test_export_contains_the_chain_and_marks_unapproved_drafts(
    agent_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = candidate(sessions, scenario={"demo_value": -1.0, "demo_criteria": [criterion()]})
    run = analyse(secure_client, runtime, bearer(), case_id)
    make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    review(secure_client, bearer("reviewer-a"), case_id, action="FOLLOW_UP")
    assert secure_client.get(f"/api/v1/cases/{case_id}/export", headers=bearer()).status_code == 403

    pack = EvidencePack.model_validate(
        secure_client.get(f"/api/v1/cases/{case_id}/export", headers=bearer("reviewer-a")).json()
    )
    assert pack.is_synthetic is True
    assert pack.analysis_runs[0].criterion_checks[0].citation is not None
    assert pack.drafts[0].status == "DRAFT"
    assert pack.review_events[0].action == "FOLLOW_UP"
    with sessions() as session:
        events = session.scalars(select(AuditEvent).where(AuditEvent.action == "export_case")).all()
    assert {event.outcome for event in events} >= {"DENIED", "ALLOWED"}


def test_candidate_is_idempotent_and_needs_a_registered_source(
    sessions: sessionmaker[Session], users: Users
) -> None:
    uid = uuid4().hex
    assert candidate(sessions, notice_uid=uid) == candidate(sessions, notice_uid=uid)
    with pytest.raises(ValueError, match="not registered"):
        candidate(sessions, source_id=OTHER)
    with pytest.raises(ValueError):
        candidate(sessions, frequency_start_mhz=2.0, frequency_end_mhz=1.0)


def test_frequency_overlap_alone_is_never_a_concern(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case = case_of(secure_client, bearer(), candidate(sessions))
    assert case.relevance_label == "FREQUENCY_MATCH"
    assert case.relevance.frequency_match is True
    assert case.finding_status == "INSUFFICIENT_DATA"
    assert case.margin_db is None


@pytest.mark.parametrize(
    ("subject", "kind"),
    [("analyst-b", "other-tenant"), ("reviewer-a", "unentitled")],
)
def test_case_data_is_hidden_exactly_like_a_missing_case(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    users: Users,
    subject: str,
    kind: str,
) -> None:
    with sessions() as session:
        session.add(
            ResourceEntitlement(
                grant_id="g",
                subject=users.ids["analyst-a"],
                tenant_id=TENANT_A,
                object_type="source",
                object_id=RESTRICTED,
                classification="RESTRICTED",
                rights=["READ"],
            )
        )
        session.commit()
    case_id = candidate(sessions, source_id=RESTRICTED, notice_id="SECRET-NOTICE")
    run = analyse(secure_client, runtime, bearer(), case_id)

    headers = bearer(subject)
    paths = [
        f"/api/v1/cases/{case_id}",
        f"/api/v1/analyses/{run.analysis_run_id}",
        f"/api/v1/analyses/{run.analysis_run_id}/methods",
        f"/api/v1/cases/{case_id}/drafts",
        f"/api/v1/cases/{case_id}/reviews",
    ]
    absent = secure_client.get("/api/v1/cases/does-not-exist", headers=headers).json()["error"]
    for path in paths:
        response = secure_client.get(path, headers=headers)
        assert response.status_code == 404, path
        error = response.json()["error"]
        assert (error["code"], error["message"]) == (absent["code"], absent["message"])
    listing = secure_client.get("/api/v1/cases", params={"query": "SECRET"}, headers=headers)
    assert listing.json()["items"] == []
    assert "SECRET-NOTICE" not in listing.text


def test_restricted_export_needs_the_export_right(
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    users: Users,
) -> None:
    def grant(rights: list[str]) -> None:
        with sessions() as session:
            session.add(
                ResourceEntitlement(
                    grant_id=uuid4().hex,
                    subject=users.ids["reviewer-a"],
                    tenant_id=TENANT_A,
                    object_type="source",
                    object_id=RESTRICTED,
                    classification="RESTRICTED",
                    rights=rights,
                )
            )
            session.commit()

    case_id = candidate(sessions, source_id=RESTRICTED)
    headers = bearer("reviewer-a")
    grant(["READ"])
    assert secure_client.get(f"/api/v1/cases/{case_id}", headers=headers).status_code == 200
    assert secure_client.get(f"/api/v1/cases/{case_id}/export", headers=headers).status_code == 404
    grant(["EXPORT"])
    assert secure_client.get(f"/api/v1/cases/{case_id}/export", headers=headers).status_code == 200


def test_list_filters_sorting_and_pagination(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    for start, change, issue in (
        (300.0, "NEW", "ISSUE-1"),
        (100.0, "MODIFIED", "ISSUE-1"),
        (200.0, "NEW", "ISSUE-2"),
    ):
        candidate(
            sessions,
            frequency_start_mhz=start,
            frequency_end_mhz=start,
            change_type=change,
            source_issue_id=issue,
        )
    headers = bearer()

    def fetch(**params: Any) -> CaseList:
        response = secure_client.get("/api/v1/cases", params=params, headers=headers)
        assert response.status_code == 200, response.text
        return CaseList.model_validate(response.json())

    assert len(fetch(change_type="NEW").items) == 2
    assert len(fetch(source_issue_id="ISSUE-2").items) == 1
    assert fetch(query="%").items == []

    ordered: list[float] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"sort": "frequency_start_mhz", "limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = fetch(**params)
        ordered += [item.frequency_start_mhz for item in page.items]
        cursor = page.next_cursor
        if cursor is None:
            break
    assert ordered == [100.0, 200.0, 300.0]
    bad = secure_client.get("/api/v1/cases", params={"cursor": "e30="}, headers=headers)
    assert bad.status_code == 422


def test_demo_viewer_cannot_act_on_a_case(
    secure_client: TestClient, bearer: Bearer, sessions: sessionmaker[Session]
) -> None:
    case_id = candidate(sessions)
    viewer = bearer("demo-a")
    assert secure_client.get(f"/api/v1/cases/{case_id}", headers=viewer).status_code == 200
    denied = secure_client.post(
        f"/api/v1/cases/{case_id}/analyse",
        json={},
        headers={**viewer, "Idempotency-Key": uuid4().hex},
    )
    assert denied.status_code == 403


def test_worker_loads_only_valid_plugins() -> None:
    from astrasync_api.config import Settings, SettingsError

    good = load_analysis_plugins(
        Settings(
            rf_methods=("support.demo_plugins:DemoEchoMethod",),
            criterion_resolver="support.demo_plugins:DemoEchoResolver",
            build_sha="abc",
        )
    )
    assert DemoEchoMethod.method_id in good.methods
    assert good.build_sha == "abc"
    with pytest.raises(SettingsError, match="RFMethod"):
        load_analysis_plugins(Settings(rf_methods=("support.demo_plugins:DemoDraftAgent",)))


# --- Case questions (grounded assistant) ------------------------------------------------------


def _with_answerer(app: FastAPI, response: Any) -> list[str]:
    asked: list[str] = []

    class Agent:
        model_id = "test-model"

        def answer_question(self, evidence: Any, question: str) -> Any:
            asked.append(question)
            if isinstance(response, Exception):
                raise response
            return response(evidence) if callable(response) else response

    app.state.draft_agent = Agent()
    return asked


def _ask(client: TestClient, headers: dict[str, str], case_id: str, run_id: str) -> Any:
    return client.post(
        f"/api/v1/cases/{case_id}/questions",
        json={"analysis_run_id": run_id, "question": "What was calculated?"},
        headers=headers,
    )


def _evidence_case(sessions: sessionmaker[Session]) -> str:
    case_id = candidate(sessions)
    with sessions.begin() as session:
        session.add(
            EvidenceLinkRow(
                evidence_id=f"{case_id}-record",
                case_id=case_id,
                label="Original source record (synthetic)",
                entity_type="source_record",
                entity_id="SYNTHETIC-RECORD-001",
                source_issue_id="DEMO-IFIC-001",
                source_locator="SYNTHETIC!1",
                sha256="0" * 64,
            )
        )
    return case_id


def test_a_question_is_answered_with_checked_citations(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = _evidence_case(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    asked = _with_answerer(
        secure_app,
        lambda evidence: {
            "answer_markdown": "The notice is under review "
            f"[E:{evidence['evidence'][0]['evidence_id']}].",
            "uncertainties": ["Screening only."],
            "cited_evidence_ids": [evidence["evidence"][0]["evidence_id"]],
        },
    )
    response = _ask(secure_client, bearer(), case_id, run.analysis_run_id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cited_evidence_ids"] == [f"{case_id}-record"]
    assert body["requires_human_review"] is True
    assert body["ai_model_id"] == "test-model"
    assert asked == ["What was calculated?"]


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(
            {"answer_markdown": "x [E:FAKE]", "cited_evidence_ids": ["FAKE"]}, id="invented"
        ),
        pytest.param({"answer_markdown": "x", "cited_evidence_ids": []}, id="uncited"),
        pytest.param(ValueError("refused"), id="agent-refused"),
    ],
)
def test_unusable_answers_are_refused(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
    answer: Any,
) -> None:
    case_id = _evidence_case(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    _with_answerer(secure_app, answer)
    response = _ask(secure_client, bearer(), case_id, run.analysis_run_id)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_UNAVAILABLE"


def test_questions_keep_authorization_and_tenant_isolation(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = _evidence_case(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    asked = _with_answerer(secure_app, {"answer_markdown": "x", "cited_evidence_ids": []})
    assert _ask(secure_client, {}, case_id, run.analysis_run_id).status_code == 401
    assert (
        _ask(secure_client, bearer("no-roles-a"), case_id, run.analysis_run_id).status_code == 403
    )
    assert _ask(secure_client, bearer("analyst-b"), case_id, run.analysis_run_id).status_code == 404
    assert asked == []


def test_without_an_answering_agent_questions_are_unavailable(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,
) -> None:
    case_id = _evidence_case(sessions)
    run = analyse(secure_client, runtime, bearer(), case_id)
    secure_app.state.draft_agent = DemoDraftAgent()
    response = _ask(secure_client, bearer(), case_id, run.analysis_run_id)
    assert response.status_code == 503
