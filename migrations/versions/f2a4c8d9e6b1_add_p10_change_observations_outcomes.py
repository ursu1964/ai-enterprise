"""add P10 change observations and outcomes

Revision ID: f2a4c8d9e6b1
Revises: e73b1aa9d6f0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f2a4c8d9e6b1"
down_revision: str | None = "e73b1aa9d6f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "change_observations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("observed_by", sa.String(200), nullable=False),
        sa.Column("observation_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observation_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decision_id"], ["change_decisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "proposal_id", "version", name="uq_change_observation_proposal_version"
        ),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint("version > 0", name="ck_change_observation_version_positive"),
        sa.CheckConstraint(
            "observation_window_end > observation_window_start",
            name="ck_change_observation_window",
        ),
    )
    op.create_index(
        "ix_change_observations_proposal_id", "change_observations", ["proposal_id"]
    )

    op.create_table(
        "change_outcomes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("proposal_id", sa.UUID(), nullable=False),
        sa.Column("observation_id", sa.UUID(), nullable=False),
        sa.Column("disposition", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(["proposal_id"], ["change_proposals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["observation_id"], ["change_observations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposal_id", "observation_id", name="uq_change_outcome_observation"),
        sa.UniqueConstraint("content_hash"),
        sa.CheckConstraint(
            "disposition IN ('retain', 'revise', 'rollback', 'inconclusive')",
            name="ck_change_outcome_disposition",
        ),
    )
    op.create_index("ix_change_outcomes_proposal_id", "change_outcomes", ["proposal_id"])


def downgrade() -> None:
    op.drop_index("ix_change_outcomes_proposal_id", table_name="change_outcomes")
    op.drop_table("change_outcomes")
    op.drop_index("ix_change_observations_proposal_id", table_name="change_observations")
    op.drop_table("change_observations")
