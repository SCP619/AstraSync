"""Deployment settings, read from the environment and validated so unsafe setups refuse to start.

No value here is a secret: the API only verifies tokens with the provider's public keys.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .contract.enums import Environment

# Asymmetric only. Shared-secret algorithms and "none" can never be enabled by configuration.
ALLOWED_TOKEN_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "EdDSA"}
)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class SettingsError(ValueError):
    """The deployment configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    audience: str
    jwks_uri: str
    algorithms: tuple[str, ...]
    required_scopes: frozenset[str]
    mfa_required: bool
    mfa_amr_values: frozenset[str]
    mfa_acr_values: frozenset[str]
    leeway_seconds: int = 30


@dataclass(frozen=True)
class Settings:
    """Without ``environment`` the API starts unconfigured and denies every request."""

    environment: Environment | None = None
    database_url: str | None = None
    oidc: OidcSettings | None = None
    cors_origins: tuple[str, ...] = ()
    object_store_path: Path | None = None
    max_upload_bytes: int = 10 * 1024**3
    source_adapters: tuple[str, ...] = ()
    source_clients: tuple[str, ...] = ()
    rf_methods: tuple[str, ...] = ()
    criterion_resolver: str | None = None
    draft_agent: str | None = None
    ai_classifications: tuple[str, ...] = ("PUBLIC", "INTERNAL")
    build_sha: str = "unknown"
    push_token_key: str | None = None
    push_gateway: str | None = None

    def __post_init__(self) -> None:
        _validate(self)

    @property
    def configured(self) -> bool:
        return (
            self.environment is not None
            and self.database_url is not None
            and self.oidc is not None
        )

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        names = ("ASTRASYNC_ENVIRONMENT", "ASTRASYNC_DATABASE_URL", "ASTRASYNC_OIDC_ISSUER")
        present = [name for name in names if env.get(name)]
        if not present:
            return cls(cors_origins=_csv(env.get("ASTRASYNC_CORS_ORIGINS", "")))
        missing = [
            name
            for name in (*names, "ASTRASYNC_OIDC_AUDIENCE", "ASTRASYNC_OIDC_JWKS_URI")
            if not env.get(name)
        ]
        if missing:
            raise SettingsError(f"Missing required settings: {', '.join(missing)}")
        try:
            environment = Environment(env["ASTRASYNC_ENVIRONMENT"])
        except ValueError as exc:
            raise SettingsError("ASTRASYNC_ENVIRONMENT is not a known environment") from exc
        return cls(
            environment=environment,
            database_url=env["ASTRASYNC_DATABASE_URL"],
            cors_origins=_csv(env.get("ASTRASYNC_CORS_ORIGINS", "")),
            object_store_path=(
                Path(env["ASTRASYNC_OBJECT_STORE_PATH"])
                if env.get("ASTRASYNC_OBJECT_STORE_PATH")
                else None
            ),
            max_upload_bytes=int(env.get("ASTRASYNC_MAX_UPLOAD_BYTES", 10 * 1024**3)),
            source_adapters=_csv(env.get("ASTRASYNC_SOURCE_ADAPTERS", "")),
            source_clients=_csv(env.get("ASTRASYNC_SOURCE_CLIENTS", "")),
            rf_methods=_csv(env.get("ASTRASYNC_RF_METHODS", "")),
            criterion_resolver=env.get("ASTRASYNC_CRITERION_RESOLVER") or None,
            draft_agent=env.get("ASTRASYNC_DRAFT_AGENT") or None,
            ai_classifications=_csv(env.get("ASTRASYNC_AI_CLASSIFICATIONS", "PUBLIC,INTERNAL")),
            build_sha=env.get("ASTRASYNC_BUILD_SHA", "unknown"),
            push_token_key=env.get("ASTRASYNC_PUSH_TOKEN_KEY") or None,
            push_gateway=env.get("ASTRASYNC_PUSH_GATEWAY") or None,
            oidc=OidcSettings(
                issuer=env["ASTRASYNC_OIDC_ISSUER"],
                audience=env["ASTRASYNC_OIDC_AUDIENCE"],
                jwks_uri=env["ASTRASYNC_OIDC_JWKS_URI"],
                algorithms=_csv(env.get("ASTRASYNC_OIDC_ALGORITHMS", "RS256,ES256")),
                required_scopes=frozenset(_csv(env.get("ASTRASYNC_OIDC_REQUIRED_SCOPES", ""))),
                mfa_required=env.get("ASTRASYNC_OIDC_MFA_REQUIRED", "true").lower() != "false",
                mfa_amr_values=frozenset(_csv(env.get("ASTRASYNC_OIDC_MFA_AMR", "mfa"))),
                mfa_acr_values=frozenset(_csv(env.get("ASTRASYNC_OIDC_MFA_ACR", ""))),
            ),
        )


def load_named(spec: str) -> Any:
    """Loads a server-configured ``module:attribute``. Never takes a client-supplied value."""
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise SettingsError(f"Expected module:attribute, got {spec!r}")
    return getattr(import_module(module_name), attribute)


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _validate(settings: Settings) -> None:
    for origin in settings.cors_origins:
        parts = urlsplit(origin)
        if "*" in origin or not parts.scheme or not parts.netloc or parts.path:
            raise SettingsError("CORS origins must be exact origins, without wildcards")

    oidc = settings.oidc
    if oidc is None:
        return
    unsupported = set(oidc.algorithms) - ALLOWED_TOKEN_ALGORITHMS
    if unsupported or not oidc.algorithms:
        raise SettingsError("Only asymmetric token signing algorithms are allowed")
    if oidc.mfa_required and not (oidc.mfa_amr_values or oidc.mfa_acr_values):
        raise SettingsError("MFA is required but no accepted amr or acr values are configured")

    if settings.environment is Environment.DEMO:
        # A demo may run on one machine over plain HTTP, but only over the loopback interface.
        for url in (oidc.issuer, oidc.jwks_uri):
            parts = urlsplit(url)
            if parts.scheme != "https" and parts.hostname not in _LOOPBACK_HOSTS:
                raise SettingsError("Identity endpoints must use HTTPS unless on loopback")
        return

    # STAGING and PRODUCTION: nothing in this block may be relaxed by configuration.
    if settings.object_store_path is not None:
        raise SettingsError("Local object storage has no encryption and is for the demo only")
    for url in (oidc.issuer, oidc.jwks_uri):
        if urlsplit(url).scheme != "https":
            raise SettingsError("Identity endpoints must use HTTPS")
    if not oidc.mfa_required:
        raise SettingsError("MFA must be required outside the demo environment")
    if not oidc.required_scopes:
        raise SettingsError("Required token scopes must be set outside the demo environment")
    if not (settings.database_url or "").startswith("postgresql"):
        raise SettingsError("PostgreSQL is required outside the demo environment")
