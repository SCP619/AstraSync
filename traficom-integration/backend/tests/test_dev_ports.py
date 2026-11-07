"""Local development port configuration (tests/support/dev_ports.py) and the identity rule
behind the 2026-11-07 access-denied problem: a user is (issuer, subject), so a dev identity
provider moved to another port issues tokens no seeded persona matches."""

import socket
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support import dev_ports

from astrasync_api import admin
from astrasync_api.contract.permissions import Role


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in dev_ports.DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def test_defaults_and_derived_urls_agree() -> None:
    ports = dev_ports.load_ports({})
    assert (ports.api, ports.idp, ports.ui) == (8800, 8801, 5173)
    assert ports.issuer == "http://127.0.0.1:8801"
    assert ports.ui_origin == "http://127.0.0.1:5173"


def test_local_file_overrides_and_environment_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "dev_stack.local.env"
    path.write_text(
        "﻿# machine only\nASTRASYNC_DEV_API_PORT=18800\nASTRASYNC_DEV_IDP_PORT=18801\n",
        encoding="utf-8",
    )
    local = dev_ports.read_local_file(path)
    ports = dev_ports.load_ports(local)
    assert (ports.api, ports.idp) == (18800, 18801)
    assert ports.issuer == "http://127.0.0.1:18801"
    monkeypatch.setenv("ASTRASYNC_DEV_IDP_PORT", "18901")
    assert dev_ports.load_ports(local).idp == 18901


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"ASTRASYNC_DEV_API_PORT": "eighty"}, "not a port number"),
        ({"ASTRASYNC_DEV_API_PORT": "80"}, "between 1024 and 65535"),
        ({"ASTRASYNC_DEV_IDP_PORT": "70000"}, "between 1024 and 65535"),
        ({"ASTRASYNC_DEV_API_PORT": "18800", "ASTRASYNC_DEV_IDP_PORT": "18800"}, "different"),
        ({"ASTRASYNC_DEV_UI_PORT": "8800"}, "different"),
    ],
)
def test_invalid_ports_are_refused_with_a_reason(values: dict[str, str], message: str) -> None:
    with pytest.raises(dev_ports.DevConfigError, match=message):
        dev_ports.load_ports(values)


def test_only_dev_settings_are_read_from_the_local_file(tmp_path: Path) -> None:
    path = tmp_path / "dev_stack.local.env"
    path.write_text("ASTRASYNC_OIDC_ISSUER=https://evil.example\n", encoding="utf-8")
    with pytest.raises(dev_ports.DevConfigError, match="line 1"):
        dev_ports.read_local_file(path)


def test_an_occupied_port_fails_with_the_fix() -> None:
    with socket.socket() as held:
        held.bind((dev_ports.HOST, 0))
        held.listen()
        port = held.getsockname()[1]
        with pytest.raises(dev_ports.DevConfigError, match="ASTRASYNC_DEV_API_PORT"):
            dev_ports.require_bindable(port, "API", "ASTRASYNC_DEV_API_PORT")


def test_a_persona_under_the_old_issuer_is_refused(
    secure_client: TestClient, bearer: Any, sessions: Any
) -> None:
    """The root cause: same subject, different issuer, so no provisioned user matches."""
    admin.provision_user(
        sessions,
        tenant_id="DEMO-TENANT-A",
        issuer="http://127.0.0.1:8801",
        subject="moved-persona",
        roles=[Role.ANALYST],
    )
    # Tokens in this suite come from the test issuer, as a moved dev IdP's tokens would.
    assert secure_client.get("/api/v1/me", headers=bearer("moved-persona")).status_code == 403
