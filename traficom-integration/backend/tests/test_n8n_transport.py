"""Local n8n/Ollama transport: destination, authentication header, contract and failure modes."""

from __future__ import annotations

import json

import httpx
import pytest

from astrasync_api.drafting import (
    N8N_MAX_RESPONSE_BYTES,
    N8N_SECRET_HEADER,
    GroundedLlmDraftAgent,
    LlmTransportError,
    n8n_transport,
    transport_from_environment,
    validate_n8n_url,
)

URL = "http://127.0.0.1:5678/webhook/astrasync-llm"
SECRET = "synthetic-test-secret"


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, follow_redirects=False)


def test_the_request_carries_the_secret_header_and_the_trusted_contract() -> None:
    seen: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["header"] = request.headers.get(N8N_SECRET_HEADER)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"text": "Generated response"})

    send = n8n_transport(URL, SECRET, client=_client(httpx.MockTransport(handle)))
    assert send("Trusted instructions", "Evidence prompt", "qwen3:8b") == "Generated response"
    assert seen["header"] == SECRET
    assert seen["body"] == {
        "system": "Trusted instructions",
        "user": "Evidence prompt",
        "model": "qwen3:8b",
    }


def test_a_single_item_array_reply_is_accepted() -> None:
    send = n8n_transport(
        URL,
        SECRET,
        client=_client(httpx.MockTransport(lambda r: httpx.Response(200, json=[{"text": "ok"}]))),
    )
    assert send("s", "u", "m") == "ok"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/webhook/astrasync-llm",
        "http://10.0.0.5:5678/webhook/astrasync-llm",
        "ftp://127.0.0.1/x",
        "http://user:pw@127.0.0.1:5678/webhook/x",
        "http://127.0.0.1.example.com/webhook",
    ],
)
def test_non_local_destinations_are_refused(url: str) -> None:
    with pytest.raises(ValueError):
        validate_n8n_url(url)


def test_a_named_local_service_must_be_allowed_explicitly() -> None:
    with pytest.raises(ValueError):
        validate_n8n_url("http://n8n:5678/webhook/astrasync-llm")
    assert validate_n8n_url("http://n8n:5678/webhook/astrasync-llm", frozenset({"n8n"}))


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(403, text="Authorization data is wrong!"), "HTTP 403"),
        (httpx.Response(404, json={"message": "not registered"}), "HTTP 404"),
        (httpx.Response(302, headers={"location": "https://evil.example"}), "redirect"),
        (httpx.Response(200, text="not json"), "not JSON"),
        (httpx.Response(200, json={"answer": "x"}), '"text"'),
        (httpx.Response(200, json={"text": "  "}), '"text"'),
        (httpx.Response(200, content=b"x" * (N8N_MAX_RESPONSE_BYTES + 10)), "size"),
    ],
)
def test_contract_violations_fail_safely_without_the_secret(
    response: httpx.Response, message: str
) -> None:
    send = n8n_transport(URL, SECRET, client=_client(httpx.MockTransport(lambda r: response)))
    with pytest.raises(LlmTransportError) as error:
        send("system", "user", "qwen3:8b")
    assert message in str(error.value)
    assert SECRET not in str(error.value)


def test_an_outage_or_timeout_is_reported_without_details() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    send = n8n_transport(URL, SECRET, client=_client(httpx.MockTransport(handle)))
    with pytest.raises(LlmTransportError) as error:
        send("system", "secret evidence", "qwen3:8b")
    assert "ReadTimeout" in str(error.value)
    assert "secret evidence" not in str(error.value)


def test_an_oversized_prompt_is_not_sent() -> None:
    calls = []
    send = n8n_transport(
        URL,
        SECRET,
        client=_client(httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(200))),
    )
    with pytest.raises(LlmTransportError):
        send("s", "x" * (600 * 1024), "m")
    assert calls == []


def test_the_environment_selects_n8n_only_with_url_and_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ASTRASYNC_LLM_PROVIDER", "n8n")
    monkeypatch.delenv("ASTRASYNC_LLM_API_KEY", raising=False)
    monkeypatch.setenv("ASTRASYNC_LLM_N8N_URL", URL)
    with pytest.raises(RuntimeError):
        transport_from_environment()
    monkeypatch.setenv("ASTRASYNC_LLM_API_KEY", SECRET)
    assert callable(transport_from_environment())
    monkeypatch.delenv("ASTRASYNC_LLM_MODEL", raising=False)
    assert GroundedLlmDraftAgent().model_id == "qwen3:8b"
    monkeypatch.setenv("ASTRASYNC_LLM_N8N_URL", "http://example.com/webhook/x")
    with pytest.raises(ValueError):
        transport_from_environment()


def test_the_dev_stack_enables_local_ai_only_with_url_and_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    from pathlib import Path

    support = str(Path(__file__).parent / "support")
    monkeypatch.syspath_prepend(support)
    if "dev_stack" in sys.modules:
        dev_stack = sys.modules["dev_stack"]
    else:
        import dev_stack

    monkeypatch.setattr(dev_stack, "setting", lambda name, local=None: None)
    assert "ASTRASYNC_LLM_PROVIDER" not in dev_stack._dev_environment()
    values = {
        "ASTRASYNC_DEV_LLM_N8N_URL": URL,
        "ASTRASYNC_DEV_LLM_N8N_SECRET": SECRET,
    }
    monkeypatch.setattr(dev_stack, "setting", lambda name, local=None: values.get(name))
    environment = dev_stack._dev_environment()
    assert environment["ASTRASYNC_LLM_PROVIDER"] == "n8n"
    assert environment["ASTRASYNC_LLM_API_KEY"] == SECRET
    assert environment["ASTRASYNC_LLM_MODEL"] == "qwen3:8b"
    assert environment["ASTRASYNC_DRAFT_AGENT"].endswith(":GroundedLlmDraftAgent")
