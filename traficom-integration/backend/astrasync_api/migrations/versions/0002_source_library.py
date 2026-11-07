"""source library

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.db import UtcDateTime

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "job_runs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("lane", sa.String(length=32), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("progress_stage", sa.String(length=64), nullable=True),
        sa.Column("processed_bytes", sa.BigInteger(), nullable=True),
        sa.Column("processed_records", sa.BigInteger(), nullable=True),
        sa.Column("total_records_if_known", sa.BigInteger(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at_utc", UtcDateTime, nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at_utc", UtcDateTime, nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.Column("started_at_utc", UtcDateTime, nullable=True),
        sa.Column("finished_at_utc", UtcDateTime, nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_detail", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("tenant_id", "job_type", "idempotency_key", name="uq_job_idempotency"),
    )
    op.create_index(
        "ix_job_claim", "job_runs", ["lane", "status", "next_attempt_at_utc"], unique=False
    )
    op.create_index(op.f("ix_job_runs_tenant_id"), "job_runs", ["tenant_id"], unique=False)
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=256), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("occurred_at_utc", UtcDateTime, nullable=False),
        sa.Column("consumed_at_utc", UtcDateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_outbox_dedupe"),
    )
    op.create_index(
        op.f("ix_outbox_events_tenant_id"), "outbox_events", ["tenant_id"], unique=False
    )
    op.create_table(
        "source_connectors",
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("discovery_mode", sa.String(length=32), nullable=False),
        sa.Column("endpoint_ref", sa.String(length=256), nullable=True),
        sa.Column("auth_secret_ref", sa.String(length=256), nullable=True),
        sa.Column("rights_basis", sa.String(length=512), nullable=False),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("expected_cadence_seconds", sa.Integer(), nullable=True),
        sa.Column("last_checked_at_utc", UtcDateTime, nullable=True),
        sa.Column("last_success_at_utc", UtcDateTime, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_summary", sa.String(length=512), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index(
        op.f("ix_source_connectors_tenant_id"), "source_connectors", ["tenant_id"], unique=False
    )
    op.create_table(
        "source_observations",
        sa.Column("observation_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("provider_issue_key", sa.String(length=256), nullable=False),
        sa.Column("provider_version", sa.String(length=256), nullable=True),
        sa.Column("version_key", sa.String(length=256), nullable=False),
        sa.Column("published_at_utc", UtcDateTime, nullable=True),
        sa.Column("first_seen_at_utc", UtcDateTime, nullable=False),
        sa.Column("last_seen_at_utc", UtcDateTime, nullable=False),
        sa.Column("remote_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("observation_status", sa.String(length=32), nullable=False),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("remote", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_connectors.source_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("observation_id"),
        sa.UniqueConstraint(
            "source_id", "provider_issue_key", "version_key", name="uq_source_observation"
        ),
    )
    op.create_index(
        op.f("ix_source_observations_source_id"), "source_observations", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_observations_tenant_id"), "source_observations", ["tenant_id"], unique=False
    )
    op.create_table(
        "upload_sessions",
        sa.Column("upload_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.Column("filename_original", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expected_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("received_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("part_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("max_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("client_sha256", sa.String(length=64), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_id", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.Column("expires_at_utc", UtcDateTime, nullable=False),
        sa.Column("completed_at_utc", UtcDateTime, nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_connectors.source_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("upload_id"),
        sa.UniqueConstraint(
            "tenant_id", "created_by", "idempotency_key", name="uq_upload_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_upload_sessions_tenant_id"), "upload_sessions", ["tenant_id"], unique=False
    )
    op.create_table(
        "source_artifacts",
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("publication_id", sa.String(length=64), nullable=True),
        sa.Column("filename_original", sa.String(length=512), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=False),
        sa.Column("expected_digest", sa.String(length=64), nullable=True),
        sa.Column("expected_digest_origin", sa.String(length=256), nullable=True),
        sa.Column("publisher_auth_status", sa.String(length=64), nullable=False),
        sa.Column("byte_length", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("analysis_eligible", sa.Boolean(), nullable=False),
        sa.Column("published_at_utc", UtcDateTime, nullable=True),
        sa.Column("first_seen_at_utc", UtcDateTime, nullable=False),
        sa.Column("download_completed_at_utc", UtcDateTime, nullable=True),
        sa.Column("indexed_at_utc", UtcDateTime, nullable=True),
        sa.Column("parser_version", sa.String(length=64), nullable=True),
        sa.Column("row_reconciliation", sa.JSON(), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["source_observations.observation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_connectors.source_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("artifact_id"),
        sa.UniqueConstraint("source_id", "raw_sha256", name="uq_source_artifact_bytes"),
    )
    op.create_index(
        op.f("ix_source_artifacts_filename_original"),
        "source_artifacts",
        ["filename_original"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_artifacts_raw_sha256"), "source_artifacts", ["raw_sha256"], unique=False
    )
    op.create_index(
        op.f("ix_source_artifacts_source_id"), "source_artifacts", ["source_id"], unique=False
    )
    op.create_index(
        op.f("ix_source_artifacts_status"), "source_artifacts", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_source_artifacts_tenant_id"), "source_artifacts", ["tenant_id"], unique=False
    )
    op.create_table(
        "upload_parts",
        sa.Column("upload_id", sa.String(length=64), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("etag", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["upload_id"],
            ["upload_sessions.upload_id"],
        ),
        sa.PrimaryKeyConstraint("upload_id", "part_number"),
    )
    op.create_table(
        "artifact_integrity_checks",
        sa.Column("check_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("check_type", sa.String(length=64), nullable=False),
        sa.Column("value_expected", sa.String(length=512), nullable=True),
        sa.Column("value_observed", sa.String(length=512), nullable=True),
        sa.Column("trust_level", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column("tool_version", sa.String(length=64), nullable=False),
        sa.Column("checked_at_utc", UtcDateTime, nullable=False),
        sa.Column("diagnostic", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["source_artifacts.artifact_id"],
        ),
        sa.PrimaryKeyConstraint("check_id"),
    )
    op.create_index(
        op.f("ix_artifact_integrity_checks_artifact_id"),
        "artifact_integrity_checks",
        ["artifact_id"],
        unique=False,
    )
    op.create_table(
        "source_record_locations",
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.BigInteger(), nullable=False),
        sa.Column("source_table_or_sheet", sa.String(length=256), nullable=True),
        sa.Column("source_row_or_key", sa.String(length=256), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("notice_id", sa.String(length=256), nullable=True),
        sa.Column("raw_record_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_fields", sa.JSON(), nullable=False),
        sa.Column("field_aliases", sa.JSON(), nullable=False),
        sa.Column("analysis_eligibility", sa.JSON(), nullable=False),
        sa.Column("parser_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["source_artifacts.artifact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("source_record_id"),
        sa.UniqueConstraint("artifact_id", "ordinal", name="uq_source_record_ordinal"),
    )
    op.create_index(
        op.f("ix_source_record_locations_tenant_id"),
        "source_record_locations",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "record_quality_findings",
        sa.Column("finding_id", sa.String(length=128), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("field_key", sa.String(length=256), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_override_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_record_locations.source_record_id"],
        ),
        sa.PrimaryKeyConstraint("finding_id"),
    )
    op.create_index(
        op.f("ix_record_quality_findings_source_record_id"),
        "record_quality_findings",
        ["source_record_id"],
        unique=False,
    )
    op.create_table(
        "reference_station_records",
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_record_locations.source_record_id"],
        ),
        sa.PrimaryKeyConstraint("source_record_id"),
    )
    op.create_table(
        "source_library_search_index",
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("issue_key", sa.String(length=256), nullable=True),
        sa.Column("publisher", sa.String(length=256), nullable=False),
        sa.Column("filename_original", sa.String(length=512), nullable=False),
        sa.Column("station_number", sa.String(length=128), nullable=True),
        sa.Column("network_id", sa.String(length=128), nullable=True),
        sa.Column("administration", sa.String(length=128), nullable=True),
        sa.Column("frequency_start_mhz", sa.Float(), nullable=True),
        sa.Column("frequency_end_mhz", sa.Float(), nullable=True),
        sa.Column("text_terms", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("record_status", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["source_artifacts.artifact_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_connectors.source_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_record_locations.source_record_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("source_record_id"),
    )
    op.create_index(
        "ix_search_frequency",
        "source_library_search_index",
        ["frequency_start_mhz", "frequency_end_mhz"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_library_search_index_artifact_id"),
        "source_library_search_index",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_library_search_index_source_id"),
        "source_library_search_index",
        ["source_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_library_search_index_station_number"),
        "source_library_search_index",
        ["station_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_source_library_search_index_tenant_id"),
        "source_library_search_index",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:

    op.drop_index(
        op.f("ix_source_library_search_index_tenant_id"), table_name="source_library_search_index"
    )
    op.drop_index(
        op.f("ix_source_library_search_index_station_number"),
        table_name="source_library_search_index",
    )
    op.drop_index(
        op.f("ix_source_library_search_index_source_id"), table_name="source_library_search_index"
    )
    op.drop_index(
        op.f("ix_source_library_search_index_artifact_id"), table_name="source_library_search_index"
    )
    op.drop_index("ix_search_frequency", table_name="source_library_search_index")
    op.drop_table("source_library_search_index")
    op.drop_table("reference_station_records")
    op.drop_index(
        op.f("ix_record_quality_findings_source_record_id"), table_name="record_quality_findings"
    )
    op.drop_table("record_quality_findings")
    op.drop_index(
        op.f("ix_source_record_locations_tenant_id"), table_name="source_record_locations"
    )
    op.drop_table("source_record_locations")
    op.drop_index(
        op.f("ix_artifact_integrity_checks_artifact_id"), table_name="artifact_integrity_checks"
    )
    op.drop_table("artifact_integrity_checks")
    op.drop_table("upload_parts")
    op.drop_index(op.f("ix_source_artifacts_tenant_id"), table_name="source_artifacts")
    op.drop_index(op.f("ix_source_artifacts_status"), table_name="source_artifacts")
    op.drop_index(op.f("ix_source_artifacts_source_id"), table_name="source_artifacts")
    op.drop_index(op.f("ix_source_artifacts_raw_sha256"), table_name="source_artifacts")
    op.drop_index(op.f("ix_source_artifacts_filename_original"), table_name="source_artifacts")
    op.drop_table("source_artifacts")
    op.drop_index(op.f("ix_upload_sessions_tenant_id"), table_name="upload_sessions")
    op.drop_table("upload_sessions")
    op.drop_index(op.f("ix_source_observations_tenant_id"), table_name="source_observations")
    op.drop_index(op.f("ix_source_observations_source_id"), table_name="source_observations")
    op.drop_table("source_observations")
    op.drop_index(op.f("ix_source_connectors_tenant_id"), table_name="source_connectors")
    op.drop_table("source_connectors")
    op.drop_index(op.f("ix_outbox_events_tenant_id"), table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_index(op.f("ix_job_runs_tenant_id"), table_name="job_runs")
    op.drop_index("ix_job_claim", table_name="job_runs")
    op.drop_table("job_runs")
