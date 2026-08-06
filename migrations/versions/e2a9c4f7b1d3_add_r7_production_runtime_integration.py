"""add R7 production runtime integration records

Revision ID: e2a9c4f7b1d3
Revises: d1f4a7c9e2b6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e2a9c4f7b1d3"
down_revision: str | None = "d1f4a7c9e2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r7_runtime_synchronization_reports",
    "r7_runtime_upgrade_plans",
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
        "r7_runtime_synchronization_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column("synchronization_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("findings", jsonb, nullable=False),
        sa.Column("observed_runtime_document", jsonb, nullable=False),
        sa.Column("report_document", jsonb, nullable=False),
        sa.Column("report_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "synchronization_id"),
        sa.UniqueConstraint("project_id", "report_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "synchronization_id",
        "status",
    ):
        op.create_index(
            f"ix_r7_runtime_synchronization_reports_{column}",
            "r7_runtime_synchronization_reports",
            [column],
        )

    op.create_table(
        "r7_runtime_upgrade_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column(
            "synchronization_report_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_synchronization_reports.id"),
            nullable=False,
        ),
        sa.Column("upgrade_plan_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("blocked_by", jsonb, nullable=False),
        sa.Column("steps_document", jsonb, nullable=False),
        sa.Column("plan_document", jsonb, nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "upgrade_plan_id"),
        sa.UniqueConstraint("project_id", "plan_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "synchronization_report_id",
        "upgrade_plan_id",
        "status",
    ):
        op.create_index(
            f"ix_r7_runtime_upgrade_plans_{column}",
            "r7_runtime_upgrade_plans",
            [column],
        )

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r7_runtime_upgrade_plans")
    op.drop_table("r7_runtime_synchronization_reports")
