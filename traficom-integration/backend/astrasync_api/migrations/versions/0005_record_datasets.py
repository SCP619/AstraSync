"""record datasets: the manifest of Parquet record-store datasets

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.db import UtcDateTime

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "record_datasets",
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column("filename_original", sa.String(length=512), nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("format_version", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.BigInteger(), nullable=False),
        sa.Column("finding_count", sa.BigInteger(), nullable=False),
        sa.Column("records_sha256", sa.String(length=64), nullable=False),
        sa.Column("records_bytes", sa.BigInteger(), nullable=False),
        sa.Column("findings_sha256", sa.String(length=64), nullable=False),
        sa.Column("findings_bytes", sa.BigInteger(), nullable=False),
        sa.Column("published_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["source_artifacts.artifact_id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_connectors.source_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("artifact_id"),
    )
    op.create_index(
        op.f("ix_record_datasets_source_id"), "record_datasets", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_record_datasets_tenant_id"), "record_datasets", ["tenant_id"], unique=False
    )


def downgrade() -> None:

    op.drop_index(op.f("ix_record_datasets_tenant_id"), table_name="record_datasets")
    op.drop_index(op.f("ix_record_datasets_source_id"), table_name="record_datasets")
    op.drop_table("record_datasets")
