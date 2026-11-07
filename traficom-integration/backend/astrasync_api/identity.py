"""Maps a validated token to server-held identity, and records audit events."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .contract.permissions import Capability, Role, capabilities_for
from .db import AuditEvent, RoleRow, User, UserRoleGrant
from .oidc import TokenClaims

_LAST_VERIFIED_WRITE_INTERVAL = timedelta(minutes=5)


class IdentityDenied(Exception):
    """No access. ``reason`` is a stable code for logs; clients get a generic message."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class SessionRevoked(Exception):
    """The token predates the user's session revocation, so the user must sign in again."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[Role]
    capabilities: frozenset[Capability]


class IdentityStore:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sessions = session_factory

    @property
    def session_factory(self) -> sessionmaker[Session]:
        return self._sessions

    def resolve(self, claims: TokenClaims, *, now: datetime | None = None) -> Principal:
        """Checked on every request, so deactivation and revocation apply to the next call."""
        now = now or datetime.now(UTC)
        with self._sessions() as session:
            user = session.scalar(
                select(User).where(
                    User.issuer == claims.issuer, User.oidc_subject == claims.subject
                )
            )
            if user is None:
                raise IdentityDenied("USER_NOT_PROVISIONED")
            if not user.active:
                raise IdentityDenied("USER_DEACTIVATED")
            revoked_before = user.sessions_revoked_before_utc
            if revoked_before is not None and claims.issued_at < revoked_before:
                raise SessionRevoked

            # A grant only counts in the user's own tenant and before it expires.
            names = session.scalars(
                select(RoleRow.name)
                .join(UserRoleGrant, UserRoleGrant.role_id == RoleRow.role_id)
                .where(
                    UserRoleGrant.user_id == user.user_id,
                    UserRoleGrant.tenant_id == user.tenant_id,
                    (UserRoleGrant.expires_at_utc.is_(None))
                    | (UserRoleGrant.expires_at_utc > now),
                )
            ).all()
            roles = frozenset(Role(name) for name in names)

            last = user.last_verified_at_utc
            if last is None or now - last >= _LAST_VERIFIED_WRITE_INTERVAL:
                user.last_verified_at_utc = now
                session.commit()

            return Principal(
                user_id=user.user_id,
                tenant_id=user.tenant_id,
                roles=roles,
                capabilities=capabilities_for(roles) | {Capability.AUTHENTICATED},
            )

    def record_audit(
        self,
        *,
        actor: str,
        tenant_id: str | None,
        action: str,
        object_type: str | None,
        object_id: str | None,
        outcome: str,
        correlation_id: str,
    ) -> None:
        with self._sessions() as session:
            session.add(
                AuditEvent(
                    event_id=uuid4().hex,
                    actor=actor,
                    tenant_id=tenant_id,
                    action=action,
                    object_type=object_type,
                    object_id=object_id,
                    outcome=outcome,
                    correlation_id=correlation_id,
                    occurred_at_utc=datetime.now(UTC),
                )
            )
            session.commit()
