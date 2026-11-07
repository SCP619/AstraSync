"""User, role and source-entitlement administration (``ADMIN_USERS``, DECISIONS G26).

Rules enforced here, on the server:

- Everything is scoped to the administrator's own tenant. A user in another tenant is
  indistinguishable from a missing one (404).
- An administrator cannot change their own roles, status, sessions or entitlements, so no single
  account can raise its own access; administering does not grant content access.
- Identities are keyed by issuer plus subject, never by email. Roles must be known roles.
- An entitlement's classification is the source's, read by the server, never sent by the client.
- Every change is audited with the actor, tenant, object and request correlation ID.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .contract import CONTRACT_VERSION
from .contract.enums import DomainEventKind, ErrorCode
from .contract.models import (
    AdminEntitlement,
    AdminEntitlementGrantRequest,
    AdminUser,
    AdminUserCreateRequest,
    AdminUserDetail,
    AdminUserList,
)
from .contract.permissions import Role, capabilities_for
from .db import ResourceEntitlement, RoleRow, User, UserRoleGrant
from .errors import ApiError
from .identity import IdentityStore, Principal
from .jobs import emit_event
from .library_tables import SourceConnectorRow


def _envelope() -> dict[str, Any]:
    return {"schema_version": CONTRACT_VERSION, "generated_at_utc": datetime.now(UTC)}


def _not_found() -> ApiError:
    return ApiError(404, ErrorCode.NOT_FOUND, "Not found.")


def _user(session: Session, principal: Principal, user_id: str) -> User:
    user = session.get(User, user_id)
    if user is None or user.tenant_id != principal.tenant_id:
        raise _not_found()
    return user


def _not_self(
    identities: IdentityStore, principal: Principal, user_id: str, request_id: str
) -> None:
    if user_id == principal.user_id:
        identities.record_audit(
            actor=principal.user_id,
            tenant_id=principal.tenant_id,
            action="self_access_change_refused",
            object_type="users",
            object_id=user_id,
            outcome="DENIED",
            correlation_id=request_id,
        )
        raise ApiError(
            403,
            ErrorCode.FORBIDDEN,
            "You cannot change your own access. Ask another administrator.",
        )


def _roles(session: Session, user: User, now: datetime) -> list[Role]:
    names = session.scalars(
        select(RoleRow.name)
        .join(UserRoleGrant, UserRoleGrant.role_id == RoleRow.role_id)
        .where(
            UserRoleGrant.user_id == user.user_id,
            UserRoleGrant.tenant_id == user.tenant_id,
            (UserRoleGrant.expires_at_utc.is_(None)) | (UserRoleGrant.expires_at_utc > now),
        )
    ).all()
    return sorted(Role(name) for name in names)


def _view(session: Session, user: User, now: datetime) -> AdminUser:
    return AdminUser(
        user_id=user.user_id,
        issuer=user.issuer,
        oidc_subject=user.oidc_subject,
        active=user.active,
        roles=_roles(session, user, now),
        sessions_revoked_before_utc=user.sessions_revoked_before_utc,
        last_verified_at_utc=user.last_verified_at_utc,
    )


def _audit(
    identities: IdentityStore, principal: Principal, action: str, object_id: str, request_id: str
) -> None:
    identities.record_audit(
        actor=principal.user_id,
        tenant_id=principal.tenant_id,
        action=action,
        object_type="users",
        object_id=object_id,
        outcome="ALLOWED",
        correlation_id=request_id,
    )


def _security_event(session: Session, principal: Principal, user_id: str, change: str) -> None:
    emit_event(
        session,
        tenant_id=principal.tenant_id,
        event_kind=DomainEventKind.SECURITY_EVENT.value,
        resource_type="user",
        resource_id=user_id,
        dedupe_key=f"security:{user_id}:{change}:{uuid4().hex}",
        correlation_id=user_id,
    )


def list_users(
    session: Session, principal: Principal, limit: int, cursor: str | None
) -> AdminUserList:
    query = select(User).where(User.tenant_id == principal.tenant_id)
    if cursor is not None:
        query = query.where(User.user_id > cursor)
    rows = list(session.scalars(query.order_by(User.user_id).limit(limit + 1)))
    now = datetime.now(UTC)
    kept = rows[:limit]
    return AdminUserList(
        **_envelope(),
        items=[_view(session, user, now) for user in kept],
        limit=limit,
        next_cursor=kept[-1].user_id if len(rows) > limit else None,
        total_if_known=None,
    )


def get_user(session: Session, principal: Principal, user_id: str) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    now = datetime.now(UTC)
    view = _view(session, user, now)
    grants = session.scalars(
        select(ResourceEntitlement)
        .where(
            ResourceEntitlement.subject == user.user_id,
            ResourceEntitlement.tenant_id == user.tenant_id,
        )
        .order_by(ResourceEntitlement.grant_id)
    ).all()
    return AdminUserDetail(
        **_envelope(),
        user=view,
        # What the server would grant on the user's next request: none while deactivated.
        effective_capabilities=sorted(capabilities_for(set(view.roles))) if user.active else [],
        entitlements=[
            AdminEntitlement(
                grant_id=grant.grant_id,
                object_type="source",
                object_id=grant.object_id,
                classification=grant.classification,
                rights=list(grant.rights),
                expires_at_utc=grant.expires_at_utc,
            )
            for grant in grants
            if grant.object_type == "source"
        ],
    )


def create_user(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    body: AdminUserCreateRequest,
    request_id: str,
) -> AdminUserDetail:
    existing = session.scalar(
        select(User).where(User.issuer == body.issuer, User.oidc_subject == body.oidc_subject)
    )
    if existing is not None:
        # The same answer whichever tenant holds it, so other tenants' identities don't leak.
        raise ApiError(409, ErrorCode.CONFLICT, "This identity is already provisioned.")
    user = User(
        user_id=uuid4().hex,
        tenant_id=principal.tenant_id,
        issuer=body.issuer,
        oidc_subject=body.oidc_subject,
        active=True,
    )
    session.add(user)
    session.flush()
    for role in sorted(set(body.roles)):
        session.add(
            UserRoleGrant(user_id=user.user_id, role_id=role.value, tenant_id=principal.tenant_id)
        )
    session.commit()
    _audit(identities, principal, "user_provisioned", user.user_id, request_id)
    return get_user(session, principal, user.user_id)


def set_roles(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    user_id: str,
    roles: list[Role],
    request_id: str,
) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    _not_self(identities, principal, user_id, request_id)
    session.execute(
        delete(UserRoleGrant).where(
            UserRoleGrant.user_id == user.user_id, UserRoleGrant.tenant_id == user.tenant_id
        )
    )
    for role in sorted(set(roles)):
        session.add(
            UserRoleGrant(user_id=user.user_id, role_id=role.value, tenant_id=user.tenant_id)
        )
    _security_event(session, principal, user.user_id, "roles-changed")
    session.commit()
    _audit(identities, principal, "user_roles_changed", user.user_id, request_id)
    return get_user(session, principal, user_id)


def set_status(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    user_id: str,
    active: bool,
    request_id: str,
) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    _not_self(identities, principal, user_id, request_id)
    user.active = active
    _security_event(session, principal, user.user_id, "activated" if active else "deactivated")
    session.commit()
    _audit(
        identities,
        principal,
        "user_activated" if active else "user_deactivated",
        user.user_id,
        request_id,
    )
    return get_user(session, principal, user_id)


def revoke_sessions(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    user_id: str,
    request_id: str,
) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    _not_self(identities, principal, user_id, request_id)
    user.sessions_revoked_before_utc = datetime.now(UTC)
    _security_event(session, principal, user.user_id, "sessions-revoked")
    session.commit()
    _audit(identities, principal, "user_sessions_revoked", user.user_id, request_id)
    return get_user(session, principal, user_id)


def grant_entitlement(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    user_id: str,
    body: AdminEntitlementGrantRequest,
    request_id: str,
) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    _not_self(identities, principal, user_id, request_id)
    source = session.get(SourceConnectorRow, body.source_id)
    if source is None or source.tenant_id != principal.tenant_id:
        raise _not_found()
    if body.expires_at_utc is not None and body.expires_at_utc <= datetime.now(UTC):
        raise ApiError(422, ErrorCode.VALIDATION_ERROR, "An entitlement must expire in the future.")
    grant_id = uuid4().hex
    session.add(
        ResourceEntitlement(
            grant_id=grant_id,
            subject=user.user_id,
            tenant_id=user.tenant_id,
            object_type="source",
            object_id=source.source_id,
            classification=source.usage_classification,
            rights=sorted(set(body.rights)),
            expires_at_utc=body.expires_at_utc,
        )
    )
    _security_event(session, principal, user.user_id, "entitlement-granted")
    session.commit()
    _audit(identities, principal, "entitlement_granted", grant_id, request_id)
    return get_user(session, principal, user_id)


def revoke_entitlement(
    session: Session,
    identities: IdentityStore,
    principal: Principal,
    user_id: str,
    grant_id: str,
    request_id: str,
) -> AdminUserDetail:
    user = _user(session, principal, user_id)
    _not_self(identities, principal, user_id, request_id)
    grant = session.get(ResourceEntitlement, grant_id)
    if grant is None or grant.subject != user.user_id or grant.tenant_id != user.tenant_id:
        raise _not_found()
    session.delete(grant)
    _security_event(session, principal, user.user_id, "entitlement-revoked")
    session.commit()
    _audit(identities, principal, "entitlement_revoked", grant_id, request_id)
    return get_user(session, principal, user_id)
