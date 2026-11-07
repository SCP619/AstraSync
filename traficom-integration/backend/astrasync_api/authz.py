"""Per-object authorization, required by every route that returns or changes a stored object.

The capability on a route is necessary but not sufficient. This module adds the remaining layers:
tenant, data environment, classification and source entitlement. No role bypasses any of them.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.orm import Session, sessionmaker

from .contract.enums import ErrorCode, UsageClassification
from .contract.permissions import Role
from .db import ResourceEntitlement
from .errors import ApiError
from .identity import Principal

# Everything else, including UNVERIFIED, needs an explicit entitlement.
_OPEN_WITHIN_TENANT = frozenset({UsageClassification.PUBLIC, UsageClassification.INTERNAL})
_SYNTHETIC_ONLY_ROLES = frozenset({Role.DEMO_VIEWER})


@dataclass(frozen=True)
class ObjectRef:
    """Loaded from server-side storage. Never built from values supplied by a client."""

    object_type: str
    object_id: str
    tenant_id: str
    classification: UsageClassification
    is_synthetic: bool


class ObjectAccessPolicy:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    def can_access(self, principal: Principal, target: ObjectRef, right: str) -> bool:
        if target.tenant_id != principal.tenant_id:
            return False
        if principal.roles & _SYNTHETIC_ONLY_ROLES and not target.is_synthetic:
            return False
        if target.classification in _OPEN_WITHIN_TENANT:
            return True
        return self._has_entitlement(principal, target, right)

    def require_access(self, principal: Principal, target: ObjectRef, right: str) -> None:
        """Denial is the same 404 as an absent object, so existence does not leak."""
        if not self.can_access(principal, target, right):
            raise not_found()

    def readable_clause(
        self,
        principal: Principal,
        right: str,
        *,
        tenant_column: Any,
        source_column: Any,
        classification_column: Any,
        synthetic_column: Any,
    ) -> ColumnElement[bool]:
        """The same rules as ``can_access``, as a filter inside a list or search query."""
        now = datetime.now(UTC)
        with self._sessions() as session:
            grants = session.scalars(
                select(ResourceEntitlement).where(
                    ResourceEntitlement.subject == principal.user_id,
                    ResourceEntitlement.tenant_id == principal.tenant_id,
                    ResourceEntitlement.object_type == "source",
                    (ResourceEntitlement.expires_at_utc.is_(None))
                    | (ResourceEntitlement.expires_at_utc > now),
                )
            ).all()
        entitled = [
            and_(source_column == grant.object_id, classification_column == grant.classification)
            for grant in grants
            if right in grant.rights
        ]
        permitted = or_(
            classification_column.in_([level.value for level in _OPEN_WITHIN_TENANT]), *entitled
        )
        clause = and_(tenant_column == principal.tenant_id, permitted)
        if principal.roles & _SYNTHETIC_ONLY_ROLES:
            clause = and_(clause, synthetic_column.is_(True))
        return clause

    def _has_entitlement(self, principal: Principal, target: ObjectRef, right: str) -> bool:
        now = datetime.now(UTC)
        with self._sessions() as session:
            grants = session.scalars(
                select(ResourceEntitlement).where(
                    ResourceEntitlement.subject == principal.user_id,
                    ResourceEntitlement.tenant_id == principal.tenant_id,
                    ResourceEntitlement.object_type == target.object_type,
                    ResourceEntitlement.object_id == target.object_id,
                    ResourceEntitlement.classification == target.classification.value,
                    (ResourceEntitlement.expires_at_utc.is_(None))
                    | (ResourceEntitlement.expires_at_utc > now),
                )
            ).all()
        return any(right in grant.rights for grant in grants)


def not_found() -> ApiError:
    return ApiError(404, ErrorCode.NOT_FOUND, "The requested resource was not found.")
