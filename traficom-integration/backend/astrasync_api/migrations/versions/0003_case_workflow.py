"""case workflow

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from astrasync_api.db import UtcDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        "finland_relevance_checks",
        sa.Column("relevance_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("notice_uid", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=True),
        sa.Column("overlap_start_mhz", sa.Float(), nullable=True),
        sa.Column("overlap_end_mhz", sa.Float(), nullable=True),
        sa.Column("frequency_match", sa.Boolean(), nullable=False),
        sa.Column("service_match", sa.Boolean(), nullable=True),
        sa.Column("geometry_match", sa.Boolean(), nullable=True),
        sa.Column("technical_data_ready", sa.Boolean(), nullable=True),
        sa.Column("criterion_available", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("relevance_id"),
    )
    op.create_index(
        op.f("ix_finland_relevance_checks_notice_uid"),
        "finland_relevance_checks",
        ["notice_uid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_finland_relevance_checks_tenant_id"),
        "finland_relevance_checks",
        ["tenant_id"],
        unique=False,
    )
    op.create_table(
        "reference_documents",
        sa.Column("reference_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("authority", sa.String(length=256), nullable=False),
        sa.Column("document_title", sa.String(length=512), nullable=False),
        sa.Column("edition", sa.String(length=128), nullable=True),
        sa.Column("publication_date", sa.String(length=32), nullable=True),
        sa.Column("effective_date", sa.String(length=32), nullable=True),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=True),
        sa.Column("section_id", sa.String(length=128), nullable=True),
        sa.Column("reviewed_by", sa.String(length=128), nullable=True),
        sa.Column("last_verified_at_utc", UtcDateTime, nullable=True),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("reference_id"),
    )
    op.create_index(
        op.f("ix_reference_documents_tenant_id"), "reference_documents", ["tenant_id"], unique=False
    )
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_issue_id", sa.String(length=128), nullable=False),
        sa.Column("notice_uid", sa.String(length=128), nullable=False),
        sa.Column("notice_id", sa.String(length=128), nullable=False),
        sa.Column("administration", sa.String(length=128), nullable=True),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("frequency_start_mhz", sa.Float(), nullable=False),
        sa.Column("frequency_end_mhz", sa.Float(), nullable=False),
        sa.Column("usage_classification", sa.String(length=32), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("relevance_id", sa.String(length=64), nullable=False),
        sa.Column("scenario_id", sa.String(length=128), nullable=False),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("finding_status", sa.String(length=64), nullable=False),
        sa.Column("review_status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=64), nullable=True),
        sa.Column("priority_reason", sa.String(length=512), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=True),
        sa.Column("methods_succeeded", sa.Integer(), nullable=False),
        sa.Column("methods_candidates", sa.Integer(), nullable=False),
        sa.Column("lead_metric_kind", sa.String(length=64), nullable=True),
        sa.Column("lead_numeric_value", sa.Float(), nullable=True),
        sa.Column("lead_unit", sa.String(length=128), nullable=True),
        sa.Column("margin_db", sa.Float(), nullable=True),
        sa.Column("criterion_status", sa.String(length=32), nullable=True),
        sa.Column("latest_analysis_run_id", sa.String(length=64), nullable=True),
        sa.Column("reviewer_decision", sa.String(length=32), nullable=True),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.Column("updated_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["relevance_id"],
            ["finland_relevance_checks.relevance_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["source_connectors.source_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("case_id"),
        sa.UniqueConstraint("tenant_id", "notice_uid", name="uq_case_notice"),
    )
    op.create_index(op.f("ix_cases_finding_status"), "cases", ["finding_status"], unique=False)
    op.create_index(
        op.f("ix_cases_frequency_start_mhz"), "cases", ["frequency_start_mhz"], unique=False
    )
    op.create_index(op.f("ix_cases_notice_id"), "cases", ["notice_id"], unique=False)
    op.create_index(op.f("ix_cases_review_status"), "cases", ["review_status"], unique=False)
    op.create_index(op.f("ix_cases_source_id"), "cases", ["source_id"], unique=False)
    op.create_index(op.f("ix_cases_source_issue_id"), "cases", ["source_issue_id"], unique=False)
    op.create_index(op.f("ix_cases_tenant_id"), "cases", ["tenant_id"], unique=False)
    op.create_table(
        "analysis_runs",
        sa.Column("analysis_run_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("scenario_id", sa.String(length=128), nullable=False),
        sa.Column("scenario_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("software_commit_sha", sa.String(length=64), nullable=False),
        sa.Column("method_registry_version", sa.String(length=64), nullable=False),
        sa.Column("reference_snapshot_sha256", sa.String(length=64), nullable=True),
        sa.Column("analysis_status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=True),
        sa.Column("run_created_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.tenant_id"],
        ),
        sa.PrimaryKeyConstraint("analysis_run_id"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_analysis_request"),
    )
    op.create_index(op.f("ix_analysis_runs_case_id"), "analysis_runs", ["case_id"], unique=False)
    op.create_index(
        op.f("ix_analysis_runs_tenant_id"), "analysis_runs", ["tenant_id"], unique=False
    )
    op.create_table(
        "evidence_links",
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("source_issue_id", sa.String(length=128), nullable=True),
        sa.Column("reference_id", sa.String(length=128), nullable=True),
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("verified_at_utc", UtcDateTime, nullable=True),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
    )
    op.create_index(op.f("ix_evidence_links_case_id"), "evidence_links", ["case_id"], unique=False)
    op.create_table(
        "review_events",
        sa.Column("review_event_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=64), nullable=True),
        sa.Column("draft_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("occurred_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
        ),
        sa.PrimaryKeyConstraint("review_event_id"),
        sa.UniqueConstraint("case_id", "actor_id", "idempotency_key", name="uq_review_request"),
    )
    op.create_index(op.f("ix_review_events_case_id"), "review_events", ["case_id"], unique=False)
    op.create_table(
        "criterion_checks",
        sa.Column("criterion_check_id", sa.String(length=128), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.analysis_run_id"],
        ),
        sa.PrimaryKeyConstraint("criterion_check_id"),
    )
    op.create_index(
        op.f("ix_criterion_checks_analysis_run_id"),
        "criterion_checks",
        ["analysis_run_id"],
        unique=False,
    )
    op.create_table(
        "drafts",
        sa.Column("draft_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=128), nullable=False),
        sa.Column("draft_type", sa.String(length=32), nullable=False),
        sa.Column("source_analysis_run_id", sa.String(length=64), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("ai_model_id", sa.String(length=128), nullable=True),
        sa.Column("generation_provenance", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at_utc", UtcDateTime, nullable=False),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_analysis_run_id"],
            ["analysis_runs.analysis_run_id"],
        ),
        sa.PrimaryKeyConstraint("draft_id"),
    )
    op.create_index(op.f("ix_drafts_case_id"), "drafts", ["case_id"], unique=False)
    op.create_table(
        "method_runs",
        sa.Column("method_run_id", sa.String(length=128), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.analysis_run_id"],
        ),
        sa.PrimaryKeyConstraint("method_run_id"),
    )
    op.create_index(
        op.f("ix_method_runs_analysis_run_id"), "method_runs", ["analysis_run_id"], unique=False
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_immutable_change() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION '% is immutable', TG_TABLE_NAME;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table in _immutable_tables():
            op.execute(
                f"""
                CREATE TRIGGER {table}_immutable
                BEFORE UPDATE OR DELETE ON {table}
                FOR EACH ROW EXECUTE FUNCTION reject_immutable_change()
                """
            )


def _immutable_tables() -> tuple[str, ...]:
    return ("method_runs", "criterion_checks", "review_events")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in _immutable_tables():
            op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute("DROP FUNCTION reject_immutable_change()")

    op.drop_index(op.f("ix_method_runs_analysis_run_id"), table_name="method_runs")
    op.drop_table("method_runs")
    op.drop_index(op.f("ix_drafts_case_id"), table_name="drafts")
    op.drop_table("drafts")
    op.drop_index(op.f("ix_criterion_checks_analysis_run_id"), table_name="criterion_checks")
    op.drop_table("criterion_checks")
    op.drop_index(op.f("ix_review_events_case_id"), table_name="review_events")
    op.drop_table("review_events")
    op.drop_index(op.f("ix_evidence_links_case_id"), table_name="evidence_links")
    op.drop_table("evidence_links")
    op.drop_index(op.f("ix_analysis_runs_tenant_id"), table_name="analysis_runs")
    op.drop_index(op.f("ix_analysis_runs_case_id"), table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index(op.f("ix_cases_tenant_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_source_issue_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_source_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_review_status"), table_name="cases")
    op.drop_index(op.f("ix_cases_notice_id"), table_name="cases")
    op.drop_index(op.f("ix_cases_frequency_start_mhz"), table_name="cases")
    op.drop_index(op.f("ix_cases_finding_status"), table_name="cases")
    op.drop_table("cases")
    op.drop_index(op.f("ix_reference_documents_tenant_id"), table_name="reference_documents")
    op.drop_table("reference_documents")
    op.drop_index(
        op.f("ix_finland_relevance_checks_tenant_id"), table_name="finland_relevance_checks"
    )
    op.drop_index(
        op.f("ix_finland_relevance_checks_notice_uid"), table_name="finland_relevance_checks"
    )
    op.drop_table("finland_relevance_checks")
