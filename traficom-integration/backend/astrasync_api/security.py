"""Authentication boundary. Fails closed until OIDC validation arrives in IPD stage 1."""

from .contract.enums import ErrorCode
from .errors import ApiError


async def require_authenticated_principal() -> None:
    """Applied to the whole v1 router, so a route added later cannot be open by omission."""
    raise ApiError(401, ErrorCode.UNAUTHENTICATED, "Authentication is required.")
