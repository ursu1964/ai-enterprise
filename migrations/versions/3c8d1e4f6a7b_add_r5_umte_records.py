"""add R5 UMTE records

Revision ID: 3c8d1e4f6a7b
Revises: 2b7e9f0a1c3d
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3c8d1e4f6a7b"
down_revision: str | None = "2b7e9f0a1c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r5_transformation_runs",
    "r5_artifact_specs",
    "r5_verification_reports",
)


def _timestamps() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
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
        "r5_transformation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_project_snapshots.id"),
            nullable=True,
        ),
        sa.Column("source_model_sha256", sa.String(64), nullable=False),
        sa.Column("source_snapshot_id", sa.String(40), nullable=False),
        sa.Column("source_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("registry_version", sa.String(40), nullable=False),
        sa.Column("template_pack_version", sa.String(40), nullable=False),
        sa.Column("target_stack", jsonb, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("blocking_finding_count", sa.Integer(), nullable=False),
        sa.Column("plan_document", jsonb, nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("result_document", jsonb, nullable=False),
        sa.Column("run_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("project_id", "run_hash"),
        sa.UniqueConstraint("project_id", "plan_hash"),
    )
    for column in (
        "project_id",
        "model_version_id",
        "snapshot_row_id",
        "source_model_sha256",
        "source_snapshot_id",
        "registry_version",
        "template_pack_version",
        "status",
    ):
        op.create_index(f"ix_r5_transformation_runs_{column}", "r5_transformation_runs", [column])

    op.create_table(
        "r5_artifact_specs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "transformation_run_id",
            sa.Uuid(),
            sa.ForeignKey("r5_transformation_runs.id"),
            nullable=False,
        ),
        sa.Column("artifact_key", sa.String(180), nullable=False),
        sa.Column("artifact_kind", sa.String(80), nullable=False),
        sa.Column("target", sa.String(80), nullable=False),
        sa.Column("source_object_id", sa.String(80), nullable=False),
        sa.Column("source_object_type", sa.String(40), nullable=False),
        sa.Column("depends_on_object_ids", jsonb, nullable=False),
        sa.Column("artifact_document", jsonb, nullable=False),
        sa.Column("provenance_document", jsonb, nullable=False),
        sa.Column("artifact_spec_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("transformation_run_id", "artifact_key"),
        sa.UniqueConstraint("project_id", "artifact_spec_hash"),
    )
    for column in (
        "project_id",
        "transformation_run_id",
        "artifact_key",
        "artifact_kind",
        "target",
        "source_object_id",
        "source_object_type",
    ):
        op.create_index(f"ix_r5_artifact_specs_{column}", "r5_artifact_specs", [column])

    op.create_table(
        "r5_verification_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "transformation_run_id",
            sa.Uuid(),
            sa.ForeignKey("r5_transformation_runs.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("blocking_finding_count", sa.Integer(), nullable=False),
        sa.Column("report_document", jsonb, nullable=False),
        sa.Column("report_hash", sa.String(64), nullable=False, unique=True),
        _timestamps(),
        sa.UniqueConstraint("transformation_run_id"),
    )
    for column in ("project_id", "transformation_run_id", "status"):
        op.create_index(f"ix_r5_verification_reports_{column}", "r5_verification_reports", [column])

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r5_verification_reports")
    op.drop_table("r5_artifact_specs")
    op.drop_table("r5_transformation_runs")
