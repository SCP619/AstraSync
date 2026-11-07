"""Identity, role grants, resource entitlements and append-only audit events.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.contract.permissions import Role
from astrasync_api.db import UtcDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("oidc_subject", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("tenant_id", sa.String(128), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("last_verified_at_utc", UtcDateTime, nullable=True),
        sa.Column("sessions_revoked_before_utc", UtcDateTime, nullable=True),
        sa.UniqueConstraint("issuer", "oidc_subject", name="uq_users_issuer_subject"),
    )
    roles = op.create_table(
        "roles",
        sa.Column("role_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )
    op.bulk_insert(roles, [{"role_id": role.value, "name": role.value} for role in Role])
    op.create_table(
        "user_role_grants",
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.user_id"), primary_key=True),
        sa.Column("role_id", sa.String(64), sa.ForeignKey("roles.role_id"), primary_key=True),
        sa.Column(
            "tenant_id", sa.String(128), sa.ForeignKey("tenants.tenant_id"), primary_key=True
        ),
        sa.Column("expires_at_utc", UtcDateTime, nullable=True),
    )
    op.create_table(
        "resource_entitlements",
        sa.Column("grant_id", sa.String(128), primary_key=True),
        sa.Column("subject", sa.String(128), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("tenant_id", sa.String(128), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False),
        sa.Column("classification", sa.String(32), nullable=False),
        sa.Column("rights", sa.JSON, nullable=False),
        sa.Column("expires_at_utc", UtcDateTime, nullable=True),
    )
    op.create_index("ix_resource_entitlements_subject", "resource_entitlements", ["subject"])
    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=True),
        sa.Column("object_id", sa.String(128), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("occurred_at_utc", UtcDateTime, nullable=False),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_audit_change() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_append_only
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_change()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION reject_audit_change()")
    op.drop_table("audit_events")
    op.drop_table("resource_entitlements")
    op.drop_table("user_role_grants")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("tenants")
