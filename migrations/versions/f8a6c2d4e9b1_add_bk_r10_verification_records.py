"""add bk r10 verification records

Revision ID: f8a6c2d4e9b1
Revises: e7f9a3b2d1c5
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f8a6c2d4e9b1"
down_revision: str | None = "e7f9a3b2d1c5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _campaigns()
    _obligations()
    _procedures()
    _environments()
    _executions()
    _results()
    _findings()
    _waivers()
    _coverage()
    _verdicts()
    _recommendations()
    _events()
    for table_name in _TABLES:
        _immutable(table_name)


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table_name}_mutation_trigger ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation")
        op.drop_table(table_name)


_TABLES = (
    "bk_r10_verification_campaigns",
    "bk_r10_verification_obligations",
    "bk_r10_verification_procedures",
    "bk_r10_verification_environments",
    "bk_r10_verification_executions",
    "bk_r10_verification_results",
    "bk_r10_verification_findings",
    "bk_r10_verification_waivers",
    "bk_r10_coverage_assessments",
    "bk_r10_campaign_verdicts",
    "bk_r10_satisfaction_recommendations",
    "bk_r10_domain_events",
)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_key", sa.String(length=160), nullable=False),
        sa.Column("project_key", sa.String(length=160), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _campaigns() -> None:
    op.create_table(
        "bk_r10_verification_campaigns",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("implementation_result_id", sa.String(length=220), nullable=False),
        sa.Column("verification_handoff_id", sa.String(length=220), nullable=False),
        sa.Column("repository_revision", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("criticality", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "campaign_id", "content_hash"),
    )
    _indexes("bk_r10_verification_campaigns", "project_key", "campaign_id", "status")


def _obligations() -> None:
    op.create_table(
        "bk_r10_verification_obligations",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("obligation_id", sa.String(length=220), nullable=False),
        sa.Column("requirement_id", sa.String(length=220), nullable=True),
        sa.Column("obligation_type", sa.String(length=120), nullable=False),
        sa.Column("method", sa.String(length=120), nullable=False),
        sa.Column("criticality", sa.String(length=80), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "obligation_id", "campaign_id"),
    )
    _indexes(
        "bk_r10_verification_obligations",
        "project_key",
        "campaign_id",
        "requirement_id",
        "status",
        "mandatory",
    )


def _procedures() -> None:
    op.create_table(
        "bk_r10_verification_procedures",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("procedure_id", sa.String(length=220), nullable=False),
        sa.Column("procedure_type", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "procedure_id", "campaign_id"),
    )
    _indexes("bk_r10_verification_procedures", "project_key", "campaign_id", "procedure_id")


def _environments() -> None:
    op.create_table(
        "bk_r10_verification_environments",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("environment_id", sa.String(length=220), nullable=False),
        sa.Column("environment_type", sa.String(length=80), nullable=False),
        sa.Column("environment_profile", sa.String(length=160), nullable=False),
        sa.Column("repository_revision", sa.String(length=220), nullable=False),
        sa.Column("integrity_status", sa.String(length=80), nullable=False),
        sa.Column("environment_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "environment_id", "campaign_id", "environment_hash"),
    )
    _indexes("bk_r10_verification_environments", "project_key", "campaign_id", "integrity_status")


def _executions() -> None:
    op.create_table(
        "bk_r10_verification_executions",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("execution_id", sa.String(length=220), nullable=False),
        sa.Column("procedure_id", sa.String(length=220), nullable=False),
        sa.Column("environment_id", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("execution_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "execution_id", "execution_hash"),
    )
    _indexes(
        "bk_r10_verification_executions", "project_key", "campaign_id", "procedure_id", "status"
    )


def _results() -> None:
    op.create_table(
        "bk_r10_verification_results",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("result_id", sa.String(length=220), nullable=False),
        sa.Column("execution_id", sa.String(length=220), nullable=False),
        sa.Column("verdict", sa.String(length=80), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "result_id", "content_hash"),
    )
    _indexes("bk_r10_verification_results", "project_key", "execution_id", "verdict")


def _findings() -> None:
    op.create_table(
        "bk_r10_verification_findings",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("finding_id", sa.String(length=220), nullable=False),
        sa.Column("finding_type", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("finding_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "finding_id", "finding_hash"),
    )
    _indexes(
        "bk_r10_verification_findings",
        "project_key",
        "campaign_id",
        "finding_type",
        "severity",
        "status",
    )


def _waivers() -> None:
    op.create_table(
        "bk_r10_verification_waivers",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("waiver_id", sa.String(length=220), nullable=False),
        sa.Column("obligation_id", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("waiver_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "waiver_id", "waiver_hash"),
    )
    _indexes("bk_r10_verification_waivers", "project_key", "campaign_id", "obligation_id", "status")


def _coverage() -> None:
    op.create_table(
        "bk_r10_coverage_assessments",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("coverage_assessment_id", sa.String(length=220), nullable=False),
        sa.Column("coverage_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "coverage_assessment_id", "coverage_hash"),
    )
    _indexes("bk_r10_coverage_assessments", "project_key", "campaign_id")


def _verdicts() -> None:
    op.create_table(
        "bk_r10_campaign_verdicts",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("verdict_id", sa.String(length=220), nullable=False),
        sa.Column("final_verdict", sa.String(length=80), nullable=False),
        sa.Column("verdict_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "verdict_id", "verdict_hash"),
    )
    _indexes("bk_r10_campaign_verdicts", "project_key", "campaign_id", "final_verdict")


def _recommendations() -> None:
    op.create_table(
        "bk_r10_satisfaction_recommendations",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("recommendation_id", sa.String(length=220), nullable=False),
        sa.Column("requirement_id", sa.String(length=220), nullable=False),
        sa.Column("recommendation", sa.String(length=80), nullable=False),
        sa.Column("recommendation_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "recommendation_id", "recommendation_hash"),
    )
    _indexes(
        "bk_r10_satisfaction_recommendations",
        "project_key",
        "campaign_id",
        "requirement_id",
        "recommendation",
    )


def _events() -> None:
    op.create_table(
        "bk_r10_domain_events",
        *_base_columns(),
        sa.Column("campaign_id", sa.String(length=220), nullable=False),
        sa.Column("event_id", sa.String(length=220), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "event_id"),
    )
    _indexes("bk_r10_domain_events", "project_key", "campaign_id", "event_type")


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def _immutable(table_name: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_{table_name}_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{table_name} is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER prevent_{table_name}_mutation_trigger
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION prevent_{table_name}_mutation();
        """
    )
