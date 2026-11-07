"""alerts

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.db import UtcDateTime

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "alert_rules",
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("trigger_kind", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("evidence_requirement", sa.String(length=64), nullable=False),
        sa.Column("routing_roles", sa.JSON(), nullable=False),
        sa.Column("dedupe_window_seconds", sa.Integer(), nullable=False),
        sa.Column("ack_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("escalation_policy", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=128), nullable=False),
        sa.Column("updated_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("rule_id", "version"),
    )
    op.create_index(op.f("ix_alert_rules_tenant_id"), "alert_rules", ["tenant_id"], unique=False)
    op.create_table(
        "alert_preferences",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("enabled_channels", sa.JSON(), nullable=False),
        sa.Column("quiet_hours_start_utc", sa.String(length=5), nullable=True),
        sa.Column("quiet_hours_end_utc", sa.String(length=5), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "registered_devices",
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=True),
        sa.Column("push_token_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_seen_at_utc", UtcDateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("token_sha256"),
    )
    op.create_index(
        op.f("ix_registered_devices_tenant_id"), "registered_devices", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_registered_devices_user_id"), "registered_devices", ["user_id"], unique=False
    )
    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=True),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("usage_classification", sa.String(length=32), nullable=True),
        sa.Column("rule_id", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("safe_title", sa.String(length=128), nullable=False),
        sa.Column("safe_preview", sa.String(length=256), nullable=False),
        sa.Column("push_category", sa.String(length=32), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("ack_timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("escalation_policy", sa.JSON(), nullable=False),
        sa.Column("escalated_at_utc", UtcDateTime, nullable=True),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.Column("expires_at_utc", UtcDateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("alert_id"),
        sa.UniqueConstraint("rule_id", "event_id", name="uq_alert_rule_event"),
    )
    op.create_index(
        "ix_alert_dedupe", "alerts", ["tenant_id", "dedupe_key", "created_at_utc"], unique=False
    )
    op.create_index(op.f("ix_alerts_created_at_utc"), "alerts", ["created_at_utc"], unique=False)
    op.create_index(op.f("ix_alerts_tenant_id"), "alerts", ["tenant_id"], unique=False)
    op.create_table(
        "alert_acknowledgments",
        sa.Column("ack_id", sa.String(length=64), nullable=False),
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("comment", sa.String(length=2000), nullable=True),
        sa.Column("acknowledged_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
        ),
        sa.PrimaryKeyConstraint("ack_id"),
        sa.UniqueConstraint("alert_id", "actor_id", name="uq_alert_ack"),
    )
    op.create_index(
        op.f("ix_alert_acknowledgments_alert_id"),
        "alert_acknowledgments",
        ["alert_id"],
        unique=False,
    )
    op.create_table(
        "alert_deliveries",
        sa.Column("delivery_id", sa.String(length=64), nullable=False),
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("recipient_user_id", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("device_key", sa.String(length=64), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("provider_message_id", sa.String(length=256), nullable=True),
        sa.Column("next_attempt_at_utc", UtcDateTime, nullable=True),
        sa.Column("sent_at_utc", UtcDateTime, nullable=True),
        sa.Column("last_attempt_at_utc", UtcDateTime, nullable=True),
        sa.Column("delivered_at_utc", UtcDateTime, nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["users.user_id"],
        ),
        sa.PrimaryKeyConstraint("delivery_id"),
        sa.UniqueConstraint(
            "alert_id", "recipient_user_id", "channel", "device_key", name="uq_alert_delivery"
        ),
    )
    op.create_index(
        op.f("ix_alert_deliveries_alert_id"), "alert_deliveries", ["alert_id"], unique=False
    )
    op.create_index(
        "ix_delivery_inbox",
        "alert_deliveries",
        ["recipient_user_id", "channel", "sent_at_utc"],
        unique=False,
    )
    op.create_index(
        "ix_delivery_pending", "alert_deliveries", ["state", "next_attempt_at_utc"], unique=False
    )


def downgrade() -> None:

    op.drop_index("ix_delivery_pending", table_name="alert_deliveries")
    op.drop_index("ix_delivery_inbox", table_name="alert_deliveries")
    op.drop_index(op.f("ix_alert_deliveries_alert_id"), table_name="alert_deliveries")
    op.drop_table("alert_deliveries")
    op.drop_index(op.f("ix_alert_acknowledgments_alert_id"), table_name="alert_acknowledgments")
    op.drop_table("alert_acknowledgments")
    op.drop_index(op.f("ix_alerts_tenant_id"), table_name="alerts")
    op.drop_index(op.f("ix_alerts_created_at_utc"), table_name="alerts")
    op.drop_index("ix_alert_dedupe", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_registered_devices_user_id"), table_name="registered_devices")
    op.drop_index(op.f("ix_registered_devices_tenant_id"), table_name="registered_devices")
    op.drop_table("registered_devices")
    op.drop_table("alert_preferences")
    op.drop_index(op.f("ix_alert_rules_tenant_id"), table_name="alert_rules")
    op.drop_table("alert_rules")
