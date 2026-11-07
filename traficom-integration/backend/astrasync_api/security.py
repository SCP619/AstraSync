"""Request authentication and route authorization.

``AuthorizedRoute`` runs before FastAPI reads the request body or solves dependencies, and it
enforces the capability each operation declares in the contract. A v1 route cannot be registered
without one, so a route cannot be open by omission.
"""

import logging
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from .contract.enums import Environment, ErrorCode
from .contract.permissions import Capability
from .errors import ApiError, request_id_for
from .identity import IdentityDenied, IdentityStore, Principal, SessionRevoked
from .oidc import IdentityProviderUnavailable, TokenRejected, TokenValidator

logger = logging.getLogger("astrasync.security")

REQUIRED_CAPABILITY_KEY = "x-required-capability"
_MAX_TOKEN_LENGTH = 8192
_AUDITED_READS = frozenset({Capability.CASE_EXPORT, Capability.SOURCE_DOWNLOAD})
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def _unauthenticated(details: dict[str, Any] | None = None) -> ApiError:
    return ApiError(
        401,
        ErrorCode.UNAUTHENTICATED,
        "Authentication is required.",
        details,
        headers=_BEARER_CHALLENGE,
    )


def _forbidden() -> ApiError:
    return ApiError(403, ErrorCode.FORBIDDEN, "You do not have permission for this action.")


def _identity_unavailable() -> ApiError:
    return ApiError(
        503, ErrorCode.SERVICE_UNAVAILABLE, "Sign-in cannot be verified right now. Try again."
    )


class SecurityRuntime:
    """Authenticates requests. With no validator (unconfigured deployment) it denies everything."""

    def __init__(
        self,
        *,
        environment: Environment | None = None,
        validator: TokenValidator | None = None,
        identities: IdentityStore | None = None,
    ) -> None:
        self.environment = environment
        self._validator = validator
        self.identities = identities

    def authenticate(self, authorization: str | None, request_id: str) -> Principal:
        token = _bearer_token(authorization)
        if token is None:
            raise _unauthenticated()
        if self._validator is None or self.identities is None:
            raise _identity_unavailable()
        try:
            claims = self._validator.validate(token)
            return self.identities.resolve(claims)
        except TokenRejected as exc:
            logger.info("token_rejected reason=%s request_id=%s", exc.reason, request_id)
            if exc.reason == "MFA_REQUIRED":
                raise ApiError(
                    401,
                    ErrorCode.MFA_REQUIRED,
                    "Multi-factor sign-in is required.",
                    headers=_BEARER_CHALLENGE,
                ) from exc
            if exc.reason == "TOKEN_EXPIRED":
                raise _unauthenticated({"reason": "TOKEN_EXPIRED"}) from exc
            raise _unauthenticated() from exc
        except SessionRevoked as exc:
            logger.info("session_revoked request_id=%s", request_id)
            raise _unauthenticated() from exc
        except IdentityDenied as exc:
            logger.warning("identity_denied reason=%s request_id=%s", exc.reason, request_id)
            raise _forbidden() from exc
        except (IdentityProviderUnavailable, SQLAlchemyError) as exc:
            logger.error("identity_unavailable request_id=%s", request_id, exc_info=True)
            raise _identity_unavailable() from exc

    def authorize(
        self, request: Request, capability: Capability, action: str, object_type: str | None
    ) -> Principal:
        request_id = request_id_for(request)
        principal = self.authenticate(request.headers.get("Authorization"), request_id)
        object_id = next(iter(request.path_params.values()), None)

        def audit(outcome: str) -> None:
            assert self.identities is not None  # noqa: S101 - authenticate() guarantees this.
            self.identities.record_audit(
                actor=principal.user_id,
                tenant_id=principal.tenant_id,
                action=action,
                object_type=object_type,
                object_id=str(object_id) if object_id is not None else None,
                outcome=outcome,
                correlation_id=request_id,
            )

        if capability not in principal.capabilities:
            try:
                audit("DENIED")
            except SQLAlchemyError:
                # The request is denied either way; losing this record must still be visible.
                logger.error("audit_write_failed request_id=%s", request_id, exc_info=True)
            raise _forbidden()

        if request.method not in _READ_METHODS or capability in _AUDITED_READS:
            # A sensitive action that cannot be audited does not proceed.
            try:
                audit("ALLOWED")
            except SQLAlchemyError as exc:
                logger.error("audit_write_failed request_id=%s", request_id, exc_info=True)
                raise _identity_unavailable() from exc
        return principal


def _bearer_token(authorization: str | None) -> str | None:
    """Header only. A token in a query parameter would leak through URLs and logs."""
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > _MAX_TOKEN_LENGTH:
        return None
    return token


class AuthorizedRoute(APIRoute):
    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        declared = (self.openapi_extra or {}).get(REQUIRED_CAPABILITY_KEY)
        if declared is None:
            raise RuntimeError(f"{path} declares no required capability")
        self.required_capability = Capability(declared)

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def authorized_handler(request: Request) -> Response:
            security: SecurityRuntime = request.app.state.security
            request.state.principal = await run_in_threadpool(
                security.authorize,
                request,
                self.required_capability,
                self.name,
                _object_type(self.path_format),
            )
            return await handler(request)

        return authorized_handler


def _object_type(path: str) -> str | None:
    """``/api/v1/cases/{case_id}/reviews`` -> ``cases``."""
    parts = [part for part in path.split("/") if part and not part.startswith("{")]
    return parts[2] if len(parts) > 2 else None


def current_principal(request: Request) -> Principal:
    principal: Principal | None = getattr(request.state, "principal", None)
    if principal is None:
        raise _unauthenticated()
    return principal


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
