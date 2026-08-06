"""add R7 UERM records

Revision ID: 8d2f6a1c9b3e
Revises: 7c4e2a9b8d1f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8d2f6a1c9b3e"
down_revision: str | None = "7c4e2a9b8d1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r7_runtime_deployments",
    "r7_health_reports",
    "r7_runtime_events",
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
        "r7_runtime_deployments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "r6_generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("deployment_id", sa.String(40), nullable=False),
        sa.Column("service_identity", sa.String(180), nullable=False),
        sa.Column("environment", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("manifest_version", sa.String(120), nullable=False),
        sa.Column("application_version", sa.String(120), nullable=False),
        sa.Column("generator_pack_id", sa.String(120), nullable=False),
        sa.Column("generator_pack_version", sa.String(40), nullable=False),
        sa.Column("endpoint_urls", jsonb, nullable=False),
        sa.Column("dependency_service_ids", jsonb, nullable=False),
        sa.Column("deployment_document", jsonb, nullable=False),
        sa.Column("deployment_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("r6_generation_build_id", "environment", "service_identity"),
        sa.UniqueConstraint("project_id", "deployment_hash"),
    )
    for column in (
        "project_id",
        "r6_generation_build_id",
        "deployment_id",
        "service_identity",
        "environment",
        "status",
        "manifest_version",
        "application_version",
        "generator_pack_id",
        "generator_pack_version",
    ):
        op.create_index(f"ix_r7_runtime_deployments_{column}", "r7_runtime_deployments", [column])

    op.create_table(
        "r7_health_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("checks_document", jsonb, nullable=False),
        sa.Column("metrics_document", jsonb, nullable=False),
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
        op.create_index(f"ix_r7_health_reports_{column}", "r7_health_reports", [column])

    op.create_table(
        "r7_runtime_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(40), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("context_document", jsonb, nullable=False),
        sa.Column("payload_document", jsonb, nullable=False),
        sa.Column("manifest_rule_ref", sa.String(200), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "event_id"),
        sa.UniqueConstraint("project_id", "event_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "event_id",
        "event_type",
        "manifest_rule_ref",
    ):
        op.create_index(f"ix_r7_runtime_events_{column}", "r7_runtime_events", [column])

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r7_runtime_events")
    op.drop_table("r7_health_reports")
    op.drop_table("r7_runtime_deployments")
