"""add R7 runtime operations

Revision ID: 9e4a7c2d5f6b
Revises: 8d2f6a1c9b3e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9e4a7c2d5f6b"
down_revision: str | None = "8d2f6a1c9b3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r7_compatibility_reports",
    "r7_workflow_instances",
    "r7_runtime_errors",
    "r7_recovery_actions",
    "r7_digital_twin_snapshots",
)


def _immutable(table: str) -> None:
    name = f"prevent_{table}_mutation"
    op.execute(
        f"CREATE FUNCTION {name}() RETURNS trigger AS $$ BEGIN "
        f"RAISE EXCEPTION '{table} is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        f"CREATE TRIGGER {name}_trigger BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {name}()"
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "r7_compatibility_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("report_document", jsonb, nullable=False),
        sa.Column("report_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "report_hash"),
    )
    for column in ("project_id", "runtime_deployment_id", "status", "report_hash"):
        op.create_index(
            f"ix_r7_compatibility_reports_{column}", "r7_compatibility_reports", [column]
        )

    op.create_table(
        "r7_workflow_instances",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("workflow_instance_id", sa.String(40), nullable=False),
        sa.Column("workflow_key", sa.String(180), nullable=False),
        sa.Column("previous_state", sa.String(120), nullable=True),
        sa.Column("current_state", sa.String(120), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("context_document", jsonb, nullable=False),
        sa.Column("workflow_document", jsonb, nullable=False),
        sa.Column("instance_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "workflow_instance_id", "instance_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "workflow_instance_id",
        "workflow_key",
        "previous_state",
        "current_state",
        "status",
        "instance_hash",
    ):
        op.create_index(f"ix_r7_workflow_instances_{column}", "r7_workflow_instances", [column])

    op.create_table(
        "r7_runtime_errors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("error_id", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(40), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("source", sa.String(200), nullable=False),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("code", sa.String(120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recovery_guidance", sa.Text(), nullable=False),
        sa.Column("context_document", jsonb, nullable=False),
        sa.Column("error_document", jsonb, nullable=False),
        sa.Column("error_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "error_id"),
        sa.UniqueConstraint("project_id", "error_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "error_id",
        "severity",
        "category",
        "source",
        "correlation_id",
        "code",
    ):
        op.create_index(f"ix_r7_runtime_errors_{column}", "r7_runtime_errors", [column])

    op.create_table(
        "r7_recovery_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_error_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_errors.id"),
            nullable=False,
        ),
        sa.Column("recovery_id", sa.String(40), nullable=False),
        sa.Column("strategy", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("policy_document", jsonb, nullable=False),
        sa.Column("action_document", jsonb, nullable=False),
        sa.Column("action_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_error_id", "recovery_id"),
        sa.UniqueConstraint("project_id", "action_hash"),
    )
    for column in ("project_id", "runtime_error_id", "recovery_id", "strategy", "status"):
        op.create_index(f"ix_r7_recovery_actions_{column}", "r7_recovery_actions", [column])

    op.create_table(
        "r7_digital_twin_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.String(40), nullable=False),
        sa.Column("health_status", sa.String(40), nullable=False),
        sa.Column("topology_document", jsonb, nullable=False),
        sa.Column("metrics_document", jsonb, nullable=False),
        sa.Column("configuration_document", jsonb, nullable=False),
        sa.Column("snapshot_document", jsonb, nullable=False),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "snapshot_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "snapshot_id",
        "health_status",
        "snapshot_hash",
    ):
        op.create_index(
            f"ix_r7_digital_twin_snapshots_{column}", "r7_digital_twin_snapshots", [column]
        )

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r7_digital_twin_snapshots")
    op.drop_table("r7_recovery_actions")
    op.drop_table("r7_runtime_errors")
    op.drop_table("r7_workflow_instances")
    op.drop_table("r7_compatibility_reports")
