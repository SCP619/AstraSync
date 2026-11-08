"""Opt-in live check: authenticated API → GroundedLlmDraftAgent → local n8n webhook → Ollama.

Runs only with ASTRASYNC_LIVE_N8N=1 and the webhook URL and secret in the git-ignored
dev_stack.local.env (ASTRASYNC_DEV_LLM_N8N_URL, ASTRASYNC_DEV_LLM_N8N_SECRET). Synthetic case
only. The secret is passed to the transport and never printed or asserted on.
"""

import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from test_cases import (  # noqa: F401  (fixtures re-used by name)
    Bearer,
    analyse,
    candidate,
    make_draft,
    plugins,
    registered,
    runtime,
)

from astrasync_api.case_tables import EvidenceLinkRow
from astrasync_api.drafting import GroundedLlmDraftAgent, n8n_transport
from astrasync_api.worker import WorkerRuntime

pytestmark = pytest.mark.skipif(
    os.environ.get("ASTRASYNC_LIVE_N8N") != "1", reason="live n8n check is opt-in"
)


def _local_setting(name: str) -> str | None:
    sys.path.insert(0, str(Path(__file__).parent / "support"))
    from dev_ports import setting

    return setting(name)


def test_an_authenticated_draft_is_worded_by_local_ollama_and_grounded(
    secure_app: FastAPI,
    secure_client: TestClient,
    bearer: Bearer,
    sessions: sessionmaker[Session],
    runtime: WorkerRuntime,  # noqa: F811 (fixture imported from test_cases)
) -> None:
    url = _local_setting("ASTRASYNC_DEV_LLM_N8N_URL")
    secret = _local_setting("ASTRASYNC_DEV_LLM_N8N_SECRET")
    if not url or not secret:
        pytest.skip("webhook URL or secret not configured locally")
    calls: list[int] = []
    replies: list[str] = []
    errors: list[str] = []
    send = n8n_transport(url, secret, timeout=300.0)

    def counted(system: str, user: str, model: str) -> str:
        calls.append(1)
        reply = send(system, user, model)
        replies.append(reply)
        return reply

    agent = GroundedLlmDraftAgent(transport=counted, model="qwen3:8b")

    class Recording:
        model_id = agent.model_id

        def create_draft(self, evidence: dict, draft_type: str) -> dict:
            try:
                return agent.create_draft(evidence, draft_type)
            except Exception as exc:
                import re

                known = sorted(e["evidence_id"] for e in evidence.get("evidence", []))
                cited = sorted({c for r in replies for c in re.findall(r"\[E:([^\]]+)\]", r)})
                errors.append(f"{type(exc).__name__}: {exc}; known={known}; cited={cited}")
                raise

        def answer_question(self, evidence: dict, question: str) -> dict:
            try:
                return agent.answer_question(evidence, question)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                raise

    secure_app.state.draft_agent = Recording()
    case_id = candidate(sessions, scenario={"demo_value": -1.0})
    # A synthetic evidence link, as an ingested source record would create (cases.py).
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
    run = analyse(secure_client, runtime, bearer(), case_id)

    # Authorization is unchanged: no token, no draft and no model call.
    unauthenticated = secure_client.post(
        f"/api/v1/cases/{case_id}/drafts",
        json={"analysis_run_id": run.analysis_run_id, "draft_type": "TECHNICAL_INQUIRY"},
    )
    assert unauthenticated.status_code == 401
    assert calls == []

    created = make_draft(secure_client, bearer(), case_id, run.analysis_run_id)
    assert calls, "the model was not called"
    assert created.status_code == 201, (errors, [r[:1500] for r in replies])
    draft = created.json()
    assert draft["requires_human_review"] is True
    assert draft["status"] == "DRAFT"
    assert draft["ai_model_id"] == "qwen3:8b"
    assert f"{case_id}-record" in str(draft["citations"])
    assert "[E:" in draft["content_markdown"]

    asked = secure_client.post(
        f"/api/v1/cases/{case_id}/questions",
        json={"analysis_run_id": run.analysis_run_id, "question": "What is this case about?"},
        headers=bearer(),
    )
    assert asked.status_code == 200, (errors, [r[:1500] for r in replies[-2:]])
    answer = asked.json()
    assert answer["cited_evidence_ids"] == [f"{case_id}-record"]
    assert answer["requires_human_review"] is True
