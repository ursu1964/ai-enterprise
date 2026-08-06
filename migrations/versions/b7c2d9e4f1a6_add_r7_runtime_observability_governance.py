"""add R7 runtime observability governance

Revision ID: b7c2d9e4f1a6
Revises: a6f1b8c3d9e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7c2d9e4f1a6"
down_revision: str | None = "a6f1b8c3d9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r7_runtime_configuration_snapshots",
    "r7_runtime_audit_records",
    "r7_runtime_telemetry_batches",
    "r7_runtime_governance_traces",
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
        "r7_runtime_configuration_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("configuration_id", sa.String(40), nullable=False),
        sa.Column("manifest_version", sa.String(120), nullable=False),
        sa.Column("configuration_document", jsonb, nullable=False),
        sa.Column("feature_flags", jsonb, nullable=False),
        sa.Column("sensitive_keys", jsonb, nullable=False),
        sa.Column("configuration_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "configuration_id"),
        sa.UniqueConstraint("project_id", "configuration_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "configuration_id",
        "manifest_version",
    ):
        op.create_index(
            f"ix_r7_runtime_configuration_snapshots_{column}",
            "r7_runtime_configuration_snapshots",
            [column],
        )

    op.create_table(
        "r7_runtime_audit_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("audit_id", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("affected_object", sa.String(200), nullable=False),
        sa.Column("previous_value_hash", sa.String(64), nullable=True),
        sa.Column("new_value_hash", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(128), nullable=False),
        sa.Column("manifest_rule_ref", sa.String(200), nullable=False),
        sa.Column("audit_document", jsonb, nullable=False),
        sa.Column("audit_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "audit_id"),
        sa.UniqueConstraint("project_id", "audit_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "audit_id",
        "actor",
        "action",
        "affected_object",
        "correlation_id",
        "manifest_rule_ref",
    ):
        op.create_index(
            f"ix_r7_runtime_audit_records_{column}", "r7_runtime_audit_records", [column]
        )

    op.create_table(
        "r7_runtime_telemetry_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("telemetry_id", sa.String(40), nullable=False),
        sa.Column("metrics_document", jsonb, nullable=False),
        sa.Column("trace_ids", jsonb, nullable=False),
        sa.Column("log_signatures", jsonb, nullable=False),
        sa.Column("performance_indicators", jsonb, nullable=False),
        sa.Column("telemetry_document", jsonb, nullable=False),
        sa.Column("telemetry_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "telemetry_id"),
        sa.UniqueConstraint("project_id", "telemetry_hash"),
    )
    for column in ("project_id", "runtime_deployment_id", "telemetry_id"):
        op.create_index(
            f"ix_r7_runtime_telemetry_batches_{column}",
            "r7_runtime_telemetry_batches",
            [column],
        )

    op.create_table(
        "r7_runtime_governance_traces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("governance_trace_id", sa.String(40), nullable=False),
        sa.Column("runtime_action_hash", sa.String(64), nullable=False),
        sa.Column("business_rule_ref", sa.String(200), nullable=False),
        sa.Column("registry_rule_ref", sa.String(200), nullable=False),
        sa.Column("manifest_object_ref", sa.String(200), nullable=False),
        sa.Column("requirement_ref", sa.String(200), nullable=False),
        sa.Column("trace_document", jsonb, nullable=False),
        sa.Column("trace_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "governance_trace_id"),
        sa.UniqueConstraint("project_id", "trace_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "governance_trace_id",
        "runtime_action_hash",
        "business_rule_ref",
        "registry_rule_ref",
        "manifest_object_ref",
        "requirement_ref",
    ):
        op.create_index(
            f"ix_r7_runtime_governance_traces_{column}",
            "r7_runtime_governance_traces",
            [column],
        )

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r7_runtime_governance_traces")
    op.drop_table("r7_runtime_telemetry_batches")
    op.drop_table("r7_runtime_audit_records")
    op.drop_table("r7_runtime_configuration_snapshots")
