"""add vertical slice workflow kernel

Revision ID: b73e91c4d205
Revises: f62c8a1047de
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b73e91c4d205"
down_revision: str | None = "f62c8a1047de"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("definition_name", sa.String(100), nullable=False),
        sa.Column("workflow_version", sa.String(40), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("current_step", sa.String(80), nullable=True),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("optimistic_version", sa.Integer(), nullable=False),
        sa.Column("cancellation_requested_at", sa.DateTime(timezone=True)),
        sa.Column("failure_code", sa.String(100)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("recommended_operator_action", sa.Text()),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
        sa.UniqueConstraint("correlation_id"),
    )
    op.create_index("ix_workflow_instances_project_id", "workflow_instances", ["project_id"])
    op.create_index("ix_workflow_instances_state", "workflow_instances", ["state"])
    op.create_index(
        "ix_workflow_instances_correlation_id", "workflow_instances", ["correlation_id"]
    )
    op.create_table(
        "workflow_contexts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_context_version"),
    )
    op.create_index("ix_workflow_contexts_workflow_id", "workflow_contexts", ["workflow_id"])
    op.create_table(
        "workflow_transitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("previous_state", sa.String(80), nullable=False),
        sa.Column("current_state", sa.String(80), nullable=False),
        sa.Column("step", sa.String(80)),
        sa.Column("actor_type", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("workflow_version", sa.String(40), nullable=False),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "sequence", name="uq_workflow_transition_sequence"),
    )
    op.create_index("ix_workflow_transitions_workflow_id", "workflow_transitions", ["workflow_id"])
    op.create_index(
        "ix_workflow_transitions_correlation_id", "workflow_transitions", ["correlation_id"]
    )
    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("step", sa.String(80), nullable=False),
        sa.Column("step_version", sa.String(40), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("container_id", sa.String(200)),
        sa.Column("artifact_ids", postgresql.JSONB(), nullable=False),
        sa.Column("open_resources", postgresql.JSONB(), nullable=False),
        sa.Column("running_commands", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "checkpoint_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workflow_id", "step", "context_version", name="uq_workflow_checkpoint"
        ),
    )
    op.create_index("ix_workflow_checkpoints_workflow_id", "workflow_checkpoints", ["workflow_id"])
    op.create_table(
        "workflow_step_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("step", sa.String(80), nullable=False),
        sa.Column("step_version", sa.String(40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("failure_class", sa.String(80)),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("policy", postgresql.JSONB(), nullable=False),
        sa.Column(
            "queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflow_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id", "step", "attempt", name="uq_workflow_step_attempt"),
    )
    op.create_index(
        "ix_workflow_step_attempts_workflow_id", "workflow_step_attempts", ["workflow_id"]
    )


def downgrade() -> None:
    op.drop_table("workflow_step_attempts")
    op.drop_table("workflow_checkpoints")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_contexts")
    op.drop_table("workflow_instances")
