"""ific analyses: one row per analysed IFIC issue artifact

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.db import UtcDateTime

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ific_analyses",
        sa.Column("analysis_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("previous_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("issue", sa.Integer(), nullable=False),
        sa.Column("publication_date", sa.String(length=10), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("findings_object_key", sa.String(length=512), nullable=True),
        sa.Column("findings_sha256", sa.String(length=64), nullable=True),
        sa.Column("findings_count", sa.Integer(), nullable=False),
        sa.Column("cases_created", sa.Integer(), nullable=False),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["source_artifacts.artifact_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_connectors.source_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("analysis_id"),
    )
    op.create_index(
        op.f("ix_ific_analyses_artifact_id"), "ific_analyses", ["artifact_id"], unique=True
    )
    op.create_index(op.f("ix_ific_analyses_issue"), "ific_analyses", ["issue"], unique=False)
    op.create_index(
        op.f("ix_ific_analyses_source_id"), "ific_analyses", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_ific_analyses_tenant_id"), "ific_analyses", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ific_analyses_tenant_id"), table_name="ific_analyses")
    op.drop_index(op.f("ix_ific_analyses_source_id"), table_name="ific_analyses")
    op.drop_index(op.f("ix_ific_analyses_issue"), table_name="ific_analyses")
    op.drop_index(op.f("ix_ific_analyses_artifact_id"), table_name="ific_analyses")
    op.drop_table("ific_analyses")
