"""Identity, entitlement and audit tables (BSD section 6.1) on PostgreSQL.

SQLite is accepted only in the single-user demo environment and in tests.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Dialect,
    Engine,
    ForeignKey,
    String,
    TypeDecorator,
    UniqueConstraint,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class UtcDateTime(TypeDecorator[datetime]):
    """Stores aware UTC only and returns aware UTC on every backend."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    policy_version: Mapped[str] = mapped_column(String(64))
    created_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("issuer", "oidc_subject", name="uq_users_issuer_subject"),)

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    oidc_subject: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"))
    last_verified_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    sessions_revoked_before_utc: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )


class RoleRow(Base):
    __tablename__ = "roles"

    role_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)


class UserRoleGrant(Base):
    __tablename__ = "user_role_grants"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.role_id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), primary_key=True)
    expires_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class ResourceEntitlement(Base):
    __tablename__ = "resource_entitlements"

    grant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    subject: Mapped[str] = mapped_column(ForeignKey("users.user_id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"))
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(128))
    classification: Mapped[str] = mapped_column(String(32))
    rights: Mapped[list[str]] = mapped_column(JSON)
    expires_at_utc: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class AuditEvent(Base):
    """Append-only. On PostgreSQL a trigger rejects updates and deletes."""

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128))
    tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128))
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outcome: Mapped[str] = mapped_column(String(32))
    correlation_id: Mapped[str] = mapped_column(String(64))
    occurred_at_utc: Mapped[datetime] = mapped_column(UtcDateTime)


def build_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _enable_foreign_keys(connection: Any, _record: Any) -> None:
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def _alembic_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    return config


def run_migrations(engine: Engine) -> None:
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def schema_differences(engine: Engine) -> list[Any]:
    """Differences between the migrated database and these models. Empty means they agree."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        return list(compare_metadata(context, Base.metadata))
