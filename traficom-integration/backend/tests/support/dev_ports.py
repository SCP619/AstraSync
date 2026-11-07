"""Port and origin settings for the local development stack (``dev_stack.py``).

Defaults are the documented ones (API 8800, identity provider 8801, UI 5173). A machine where
those ports are unavailable (for example Windows reserving them: socket error 10048) overrides
them without editing tracked files, in either:

- environment variables ``ASTRASYNC_DEV_API_PORT``, ``ASTRASYNC_DEV_IDP_PORT``,
  ``ASTRASYNC_DEV_UI_PORT``; or
- ``traficom-integration/backend/dev_stack.local.env`` (git-ignored), one ``NAME=value`` per line.

Environment variables win over the file. Everything binds to loopback only. The issuer,
discovery document, JWKS, token ``iss``, CORS allowlist and redirect URIs are all derived from
these values, so they cannot drift apart; the UI reads the matching values from
``traficom-integration/ui/.env.development.local`` (also git-ignored).
"""

import os
import socket
from dataclasses import dataclass
from pathlib import Path

HOST = "127.0.0.1"
LOCAL_FILE = Path(__file__).resolve().parents[2] / "dev_stack.local.env"
DEFAULTS = {
    "ASTRASYNC_DEV_API_PORT": 8800,
    "ASTRASYNC_DEV_IDP_PORT": 8801,
    "ASTRASYNC_DEV_UI_PORT": 5173,
}


class DevConfigError(SystemExit):
    """An unusable local configuration. The message says what to change."""


def read_local_file(path: Path = LOCAL_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep or not name.strip().startswith("ASTRASYNC_DEV_"):
            raise DevConfigError(
                f"{path.name} line {number}: expected ASTRASYNC_DEV_<NAME>=value, got {line!r}"
            )
        values[name.strip()] = value.strip()
    return values


def setting(name: str, local: dict[str, str] | None = None) -> str | None:
    """An environment variable, else the local file's value, else None."""
    value = os.environ.get(name)
    if value:
        return value
    return (local if local is not None else read_local_file()).get(name) or None


@dataclass(frozen=True)
class DevPorts:
    api: int
    idp: int
    ui: int

    @property
    def issuer(self) -> str:
        return f"http://{HOST}:{self.idp}"

    @property
    def api_url(self) -> str:
        return f"http://{HOST}:{self.api}"

    @property
    def ui_origin(self) -> str:
        return f"http://{HOST}:{self.ui}"


def _port(name: str, local: dict[str, str]) -> int:
    raw = setting(name, local)
    if raw is None:
        return DEFAULTS[name]
    if not raw.isdigit():
        raise DevConfigError(f"{name}={raw!r} is not a port number")
    value = int(raw)
    if not 1024 <= value <= 65535:
        raise DevConfigError(f"{name}={value} must be between 1024 and 65535")
    return value


def load_ports(local: dict[str, str] | None = None) -> DevPorts:
    local = read_local_file() if local is None else local
    ports = DevPorts(
        api=_port("ASTRASYNC_DEV_API_PORT", local),
        idp=_port("ASTRASYNC_DEV_IDP_PORT", local),
        ui=_port("ASTRASYNC_DEV_UI_PORT", local),
    )
    if len({ports.api, ports.idp, ports.ui}) != 3:
        raise DevConfigError(
            f"The API ({ports.api}), identity provider ({ports.idp}) and UI ({ports.ui}) "
            "need three different ports"
        )
    return ports


def require_bindable(port: int, role: str, variable: str) -> None:
    """Fails early with the fix, instead of a bare socket error from the server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError as exc:
            raise DevConfigError(
                f"The {role} cannot bind {HOST}:{port} ({exc.strerror or exc}). The port is in use "
                "or reserved (on Windows check `netsh interface ipv4 show excludedportrange "
                f"protocol=tcp`). Choose another port with {variable}, in the environment or in "
                f"{LOCAL_FILE.name}, and set the matching value in "
                "traficom-integration/ui/.env.development.local."
            ) from exc
