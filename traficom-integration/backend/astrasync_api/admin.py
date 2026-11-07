"""Operator commands. AstraSync has no self-registration: accounts exist only through these.

Run as ``python -m astrasync_api.admin <command>`` with ``ASTRASYNC_DATABASE_URL`` set.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from .contract.permissions import Role
from .db import Tenant, User, UserRoleGrant, build_engine, build_session_factory, run_migrations
from .identity import IdentityStore

_ACTOR = "cli:operator"


def create_tenant(sessions: sessionmaker[Session], tenant_id: str, policy_version: str) -> None:
    with sessions() as session:
        session.add(
            Tenant(
                tenant_id=tenant_id, policy_version=policy_version, created_at_utc=datetime.now(UTC)
            )
        )
        session.commit()
    _audit(sessions, tenant_id, "create_tenant", "tenants", tenant_id)


def provision_user(
    sessions: sessionmaker[Session],
    *,
    tenant_id: str,
    issuer: str,
    subject: str,
    roles: list[Role],
    user_id: str | None = None,
) -> str:
    user_id = user_id or uuid4().hex
    with sessions() as session:
        session.add(
            User(
                user_id=user_id,
                tenant_id=tenant_id,
                issuer=issuer,
                oidc_subject=subject,
                active=True,
            )
        )
        session.flush()
        for role in roles:
            session.add(UserRoleGrant(user_id=user_id, role_id=role.value, tenant_id=tenant_id))
        session.commit()
    _audit(sessions, tenant_id, "provision_user", "users", user_id)
    return user_id


def deactivate_user(sessions: sessionmaker[Session], user_id: str) -> None:
    """Takes effect on the user's next request, even with an unexpired token."""
    user = _update_user(sessions, user_id, active=False)
    _audit(sessions, user.tenant_id, "deactivate_user", "users", user_id)


def revoke_sessions(sessions: sessionmaker[Session], user_id: str) -> None:
    """Rejects every token issued before now. The user can sign in again."""
    user = _update_user(sessions, user_id, sessions_revoked_before_utc=datetime.now(UTC))
    _audit(sessions, user.tenant_id, "revoke_sessions", "users", user_id)


def revoke_role(sessions: sessionmaker[Session], user_id: str, role: Role) -> None:
    with sessions() as session:
        user = session.get(User, user_id)
        if user is None:
            raise SystemExit(f"Unknown user: {user_id}")
        session.execute(
            delete(UserRoleGrant).where(
                UserRoleGrant.user_id == user_id, UserRoleGrant.role_id == role.value
            )
        )
        session.commit()
    _audit(sessions, user.tenant_id, "revoke_role", "users", user_id)


def _update_user(
    sessions: sessionmaker[Session], user_id: str, **values: bool | datetime
) -> User:
    with sessions() as session:
        user = session.scalar(select(User).where(User.user_id == user_id))
        if user is None:
            raise SystemExit(f"Unknown user: {user_id}")
        for name, value in values.items():
            setattr(user, name, value)
        session.commit()
        return user


def _audit(
    sessions: sessionmaker[Session], tenant_id: str, action: str, object_type: str, object_id: str
) -> None:
    IdentityStore(sessions).record_audit(
        actor=_ACTOR,
        tenant_id=tenant_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        outcome="ALLOWED",
        correlation_id=uuid4().hex,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply database migrations")

    tenant = commands.add_parser("create-tenant")
    tenant.add_argument("--tenant", required=True)
    tenant.add_argument("--policy-version", default="1")

    provision = commands.add_parser("provision-user")
    provision.add_argument("--tenant", required=True)
    provision.add_argument("--issuer", required=True)
    provision.add_argument("--subject", required=True)
    provision.add_argument("--role", action="append", default=[], choices=[r.value for r in Role])

    for name in ("deactivate-user", "revoke-sessions"):
        commands.add_parser(name).add_argument("--user-id", required=True)

    role = commands.add_parser("revoke-role")
    role.add_argument("--user-id", required=True)
    role.add_argument("--role", required=True, choices=[r.value for r in Role])

    args = parser.parse_args(argv)
    database_url = os.environ.get("ASTRASYNC_DATABASE_URL")
    if not database_url:
        parser.error("ASTRASYNC_DATABASE_URL is required")
    engine = build_engine(database_url)
    sessions = build_session_factory(engine)

    if args.command == "migrate":
        run_migrations(engine)
    elif args.command == "create-tenant":
        create_tenant(sessions, args.tenant, args.policy_version)
    elif args.command == "provision-user":
        roles = [Role(name) for name in args.role]
        print(
            provision_user(
                sessions,
                tenant_id=args.tenant,
                issuer=args.issuer,
                subject=args.subject,
                roles=roles,
            )
        )
    elif args.command == "deactivate-user":
        deactivate_user(sessions, args.user_id)
    elif args.command == "revoke-sessions":
        revoke_sessions(sessions, args.user_id)
    elif args.command == "revoke-role":
        revoke_role(sessions, args.user_id, Role(args.role))
    return 0


if __name__ == "__main__":
    sys.exit(main())
