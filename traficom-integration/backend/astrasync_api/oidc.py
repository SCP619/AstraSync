"""Provider-independent OIDC access-token validation against the provider's published keys."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import jwt

from .config import OidcSettings

_MAX_JWKS_BYTES = 1024 * 1024
_SIGNING_KEY_TYPES = {"RSA", "EC", "OKP"}


class TokenRejected(Exception):
    """The token cannot be trusted. ``reason`` is a stable code, safe to log."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class IdentityProviderUnavailable(Exception):
    """Signing keys cannot be obtained, so no token can be verified."""


@dataclass(frozen=True)
class TokenClaims:
    """The only claims trusted from a token. Roles and tenant always come from the database."""

    issuer: str
    subject: str
    issued_at: datetime


def fetch_jwks_over_http(jwks_uri: str) -> dict[str, Any]:
    """Fetch only the configured URI: no redirects, bounded time and size."""
    response = httpx.get(jwks_uri, timeout=5.0, follow_redirects=False)
    response.raise_for_status()
    if len(response.content) > _MAX_JWKS_BYTES:
        raise ValueError("JWKS document is too large")
    document: dict[str, Any] = response.json()
    return document


class JwksCache:
    """Signing keys by ``kid``, refreshed for rotation.

    An unknown ``kid`` triggers a refresh at most once per ``min_refresh_seconds``, so forged
    tokens cannot make the API hammer the provider. If the provider is down, known keys keep
    working until ``max_stale_seconds``, then every token is denied.
    """

    def __init__(
        self,
        fetch: Callable[[], dict[str, Any]],
        *,
        ttl_seconds: float = 3600,
        min_refresh_seconds: float = 60,
        max_stale_seconds: float = 86400,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._min_refresh = min_refresh_seconds
        self._max_stale = max_stale_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None

    def key_for(self, kid: str) -> Any:
        with self._lock:
            now = self._clock()
            if self._fetched_at is None or now - self._fetched_at > self._ttl:
                self._refresh(now)
            if kid not in self._keys:
                self._refresh(now)
            if self._fetched_at is None or now - self._fetched_at > self._max_stale:
                raise IdentityProviderUnavailable
            key = self._keys.get(kid)
        if key is None:
            raise TokenRejected("UNKNOWN_SIGNING_KEY")
        return key

    def _refresh(self, now: float) -> None:
        if self._attempted_at is not None and now - self._attempted_at < self._min_refresh:
            return
        self._attempted_at = now
        try:
            keys = _parse_signing_keys(self._fetch())
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            return
        if keys:
            self._keys = keys
            self._fetched_at = now


def _parse_signing_keys(document: dict[str, Any]) -> dict[str, Any]:
    keys: dict[str, Any] = {}
    for entry in document["keys"]:
        usable = (
            entry.get("kty") in _SIGNING_KEY_TYPES
            and entry.get("use", "sig") == "sig"
            and entry.get("kid")
            and "d" not in entry  # A private key must never have been published.
        )
        if not usable:
            continue
        try:
            keys[entry["kid"]] = jwt.PyJWK(entry).key
        except jwt.PyJWTError:
            continue
    return keys


class TokenValidator:
    def __init__(self, settings: OidcSettings, keys: JwksCache) -> None:
        self._settings = settings
        self._keys = keys

    def validate(self, token: str) -> TokenClaims:
        settings = self._settings
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenRejected("MALFORMED_TOKEN") from exc
        if header.get("alg") not in settings.algorithms:
            raise TokenRejected("DISALLOWED_ALGORITHM")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise TokenRejected("MISSING_KEY_ID")

        key = self._keys.key_for(kid)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=list(settings.algorithms),
                audience=settings.audience,
                issuer=settings.issuer,
                leeway=settings.leeway_seconds,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenRejected("TOKEN_EXPIRED") from exc
        except jwt.PyJWTError as exc:
            raise TokenRejected("INVALID_TOKEN") from exc

        subject = claims["sub"]
        if not isinstance(subject, str) or not subject:
            raise TokenRejected("INVALID_TOKEN")
        if not settings.required_scopes <= _scopes(claims):
            raise TokenRejected("MISSING_SCOPE")
        if settings.mfa_required and not self._mfa_satisfied(claims):
            raise TokenRejected("MFA_REQUIRED")
        return TokenClaims(
            issuer=claims["iss"],
            subject=subject,
            issued_at=datetime.fromtimestamp(claims["iat"], UTC),
        )

    def _mfa_satisfied(self, claims: dict[str, Any]) -> bool:
        amr = claims.get("amr")
        methods = set(amr) if isinstance(amr, list) else set()
        return bool(methods & self._settings.mfa_amr_values) or (
            claims.get("acr") in self._settings.mfa_acr_values
        )


def _scopes(claims: dict[str, Any]) -> set[str]:
    scope = claims.get("scope")
    if isinstance(scope, str):
        return set(scope.split())
    scp = claims.get("scp")
    return set(scp) if isinstance(scp, list) else set()
