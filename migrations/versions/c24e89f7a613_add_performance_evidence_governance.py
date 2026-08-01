"""add governed performance evidence and certification

Revision ID: c24e89f7a613
Revises: b37e9a81cd44
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c24e89f7a613"
down_revision: str | None = "b37e9a81cd44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable(table: str) -> None:
    function = f"prevent_{table}_mutation"
    op.execute(
        f"""CREATE FUNCTION {function}() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION '{table} is append-only'; END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        f"CREATE TRIGGER {function}_trigger BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "performance_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("workflow_type", sa.String(60), nullable=False),
        sa.Column("workflow_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(60), nullable=False),
        sa.Column("agent_profile_id", sa.Uuid(), sa.ForeignKey("agent_profiles.id")),
        sa.Column("crew_id", sa.Uuid(), sa.ForeignKey("crew_manifests.id")),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("agent_assignments.id")),
        sa.Column("task_id", sa.Uuid()),
        sa.Column("prompt_version", sa.String(80)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_document", jsonb, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "source_audit_event_id", sa.Uuid(), sa.ForeignKey("audit_events.id"), nullable=False
        ),
        sa.Column(
            "collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workflow_type", "workflow_id", "evidence_type", "evidence_hash"),
    )
    op.create_index(
        "ix_performance_evidence_workflow", "performance_evidence", ["workflow_type", "workflow_id"]
    )
    op.create_index(
        "ix_performance_evidence_agent", "performance_evidence", ["agent_profile_id", "observed_at"]
    )
    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("numerator", sa.Integer(), nullable=False),
        sa.Column("denominator", sa.Integer(), nullable=False),
        sa.Column("metric_value", sa.Numeric(12, 6), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_type", "scope_id", "metric_key", "evidence_set_hash"),
    )
    op.create_table(
        "assignment_quality_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "assignment_id", sa.Uuid(), sa.ForeignKey("agent_assignments.id"), nullable=False
        ),
        sa.Column("quality_band", sa.String(30), nullable=False),
        sa.Column("report_document", jsonb, nullable=False),
        sa.Column("report_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "performance_trends",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.Uuid(), nullable=False),
        sa.Column("metric_key", sa.String(80), nullable=False),
        sa.Column("window_days", sa.Integer(), nullable=False),
        sa.Column("trend_direction", sa.String(20), nullable=False),
        sa.Column("trend_document", jsonb, nullable=False),
        sa.Column("trend_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("metric_ids", jsonb, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "capability_recommendations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "agent_profile_id", sa.Uuid(), sa.ForeignKey("agent_profiles.id"), nullable=False
        ),
        sa.Column("capability_key", sa.String(120), nullable=False),
        sa.Column("recommended_level", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("recommendation_document", jsonb, nullable=False),
        sa.Column("recommendation_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "capability_certification_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("capability_recommendations.id"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("board_role", sa.String(80), nullable=False),
        sa.Column("recommendation_hash", sa.String(64), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "capability_certifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "agent_profile_id", sa.Uuid(), sa.ForeignKey("agent_profiles.id"), nullable=False
        ),
        sa.Column("capability_key", sa.String(120), nullable=False),
        sa.Column("level", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "recommendation_id",
            sa.Uuid(),
            sa.ForeignKey("capability_recommendations.id"),
            nullable=False,
        ),
        sa.Column(
            "decision_id",
            sa.Uuid(),
            sa.ForeignKey("capability_certification_decisions.id"),
            nullable=False,
        ),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("granted_by", sa.String(200), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_id", sa.Uuid(), sa.ForeignKey("capability_certifications.id")),
        sa.UniqueConstraint("agent_profile_id", "capability_key", "version"),
    )
    op.create_table(
        "performance_learning_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id")),
        sa.Column("proposal_type", sa.String(60), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("target_reference", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("proposal_document", jsonb, nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("proposed_by", sa.String(200), nullable=False),
        sa.Column("reviewed_by", sa.String(200)),
        sa.Column("review_rationale", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    )
    for table in (
        "performance_evidence",
        "performance_metrics",
        "assignment_quality_reports",
        "performance_trends",
        "capability_certification_decisions",
        "capability_certifications",
    ):
        _immutable(table)


def downgrade() -> None:
    immutable = (
        "performance_evidence",
        "performance_metrics",
        "assignment_quality_reports",
        "performance_trends",
        "capability_certification_decisions",
        "capability_certifications",
    )
    for table in reversed(immutable):
        function = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER {function}_trigger ON {table}")
        op.execute(f"DROP FUNCTION {function}()")
    for table in (
        "performance_learning_proposals",
        "capability_certifications",
        "capability_certification_decisions",
        "capability_recommendations",
        "performance_trends",
        "assignment_quality_reports",
        "performance_metrics",
        "performance_evidence",
    ):
        op.drop_table(table)
