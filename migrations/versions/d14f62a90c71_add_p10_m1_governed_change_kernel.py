"""add P10 M1 governed change kernel

Revision ID: d14f62a90c71
Revises: c91a74e8f603
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d14f62a90c71"
down_revision: str | None = "c91a74e8f603"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_proposals",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("proposed_by", sa.String(200), nullable=False),
        sa.Column("sponsor_id", sa.String(200), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("desired_outcome", sa.Text(), nullable=False),
        sa.Column("risk", sa.String(20), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("affected_entities", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint(
            "risk IN ('low', 'medium', 'high', 'critical')",
            name="ck_change_proposal_risk",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'under_analysis', "
            "'validation_required', 'ready_for_decision', 'approved', "
            "'rejected', 'deferred')",
            name="ck_change_proposal_status",
        ),
    )
    op.create_index(
        "ix_change_proposals_organization_id",
        "change_proposals",
        ["organization_id"],
    )
    op.create_index("ix_change_proposals_category", "change_proposals", ["category"])
    op.create_index("ix_change_proposals_status", "change_proposals", ["status"])

    op.create_table(
        "change_evidence",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("owner_type", sa.String(40), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("artifact_content_hash", sa.String(64), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            "artifact_id",
            name="uq_change_evidence_owner_artifact",
        ),
    )
    op.create_index(
        "ix_change_evidence_proposal_id", "change_evidence", ["proposal_id"]
    )

    op.create_table(
        "change_sets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("operations", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_set_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_set_version_positive"),
    )
    op.create_index("ix_change_sets_proposal_id", "change_sets", ["proposal_id"])

    op.create_table(
        "change_impact_assessments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("change_set_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        sa.Column("direct_impacts", postgresql.JSONB(), nullable=False),
        sa.Column("indirect_impacts", postgresql.JSONB(), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("required_approval_roles", postgresql.JSONB(), nullable=False),
        sa.Column("required_tests", postgresql.JSONB(), nullable=False),
        sa.Column("estimated_blast_radius", sa.String(20), nullable=False),
        sa.Column("rollback_complexity", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["change_set_id"], ["change_sets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_impact_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_change_impact_confidence",
        ),
        sa.CheckConstraint("version > 0", name="ck_change_impact_version_positive"),
    )
    op.create_index(
        "ix_change_impact_assessments_proposal_id",
        "change_impact_assessments",
        ["proposal_id"],
    )

    op.create_table(
        "change_validation_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("impact_assessment_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("requirements", postgresql.JSONB(), nullable=False),
        sa.Column("rollback_evidence_required", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["impact_assessment_id"],
            ["change_impact_assessments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_validation_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_validation_version_positive"),
    )
    op.create_index(
        "ix_change_validation_plans_proposal_id",
        "change_validation_plans",
        ["proposal_id"],
    )

    op.create_table(
        "change_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("change_set_id", sa.UUID(), nullable=False),
        sa.Column("impact_assessment_id", sa.UUID(), nullable=False),
        sa.Column("validation_plan_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("actor_roles", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("validation_results", postgresql.JSONB(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["change_set_id"], ["change_sets.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["impact_assessment_id"],
            ["change_impact_assessments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_plan_id"],
            ["change_validation_plans.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", name="uq_change_decision_proposal"),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'deferred')",
            name="ck_change_decision_value",
        ),
    )
    op.create_index(
        "ix_change_decisions_proposal_id", "change_decisions", ["proposal_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_change_decisions_proposal_id", table_name="change_decisions")
    op.drop_table("change_decisions")
    op.drop_index(
        "ix_change_validation_plans_proposal_id",
        table_name="change_validation_plans",
    )
    op.drop_table("change_validation_plans")
    op.drop_index(
        "ix_change_impact_assessments_proposal_id",
        table_name="change_impact_assessments",
    )
    op.drop_table("change_impact_assessments")
    op.drop_index("ix_change_sets_proposal_id", table_name="change_sets")
    op.drop_table("change_sets")
    op.drop_index("ix_change_evidence_proposal_id", table_name="change_evidence")
    op.drop_table("change_evidence")
    op.drop_index("ix_change_proposals_status", table_name="change_proposals")
    op.drop_index("ix_change_proposals_category", table_name="change_proposals")
    op.drop_index("ix_change_proposals_organization_id", table_name="change_proposals")
    op.drop_table("change_proposals")
