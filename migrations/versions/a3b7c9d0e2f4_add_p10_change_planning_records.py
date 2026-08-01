"""add P10 change planning records

Revision ID: a3b7c9d0e2f4
Revises: f2a4c8d9e6b1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3b7c9d0e2f4"
down_revision: str | None = "f2a4c8d9e6b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_transformation_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("change_set_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column("steps", postgresql.JSONB(), nullable=False),
        sa.Column("prerequisites", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["change_set_id"], ["change_sets.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_transformation_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_transformation_version_positive"),
    )
    op.create_index(
        "ix_change_transformation_plans_proposal_id",
        "change_transformation_plans",
        ["proposal_id"],
    )

    op.create_table(
        "change_rollout_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("transformation_plan_id", sa.UUID(), nullable=False),
        sa.Column("validation_plan_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("stages", postgresql.JSONB(), nullable=False),
        sa.Column("eligible_scope", postgresql.JSONB(), nullable=False),
        sa.Column("excluded_scope", postgresql.JSONB(), nullable=False),
        sa.Column("success_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("rollback_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transformation_plan_id"],
            ["change_transformation_plans.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_plan_id"], ["change_validation_plans.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_rollout_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_rollout_version_positive"),
    )
    op.create_index(
        "ix_change_rollout_plans_proposal_id", "change_rollout_plans", ["proposal_id"]
    )

    op.create_table(
        "change_rollback_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("transformation_plan_id", sa.UUID(), nullable=False),
        sa.Column("validation_plan_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rollback_steps", postgresql.JSONB(), nullable=False),
        sa.Column("trigger_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("recovery_time_objective_seconds", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["transformation_plan_id"],
            ["change_transformation_plans.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_plan_id"], ["change_validation_plans.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_rollback_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_rollback_version_positive"),
        sa.CheckConstraint(
            "recovery_time_objective_seconds > 0",
            name="ck_change_rollback_rto_positive",
        ),
    )
    op.create_index(
        "ix_change_rollback_plans_proposal_id", "change_rollback_plans", ["proposal_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_change_rollback_plans_proposal_id", table_name="change_rollback_plans")
    op.drop_table("change_rollback_plans")
    op.drop_index("ix_change_rollout_plans_proposal_id", table_name="change_rollout_plans")
    op.drop_table("change_rollout_plans")
    op.drop_index(
        "ix_change_transformation_plans_proposal_id",
        table_name="change_transformation_plans",
    )
    op.drop_table("change_transformation_plans")
