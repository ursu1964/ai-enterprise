"""add R6 UAGF records

Revision ID: 6a2b8c9d1e5f
Revises: 5e1a9c8d2f4b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6a2b8c9d1e5f"
down_revision: str | None = "5e1a9c8d2f4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r6_generation_builds",
    "r6_generated_files",
    "r6_validation_reports",
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
        "r6_generation_builds",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "r5_export_bundle_id",
            sa.Uuid(),
            sa.ForeignKey("r5_export_bundles.id"),
            nullable=False,
        ),
        sa.Column("r5_export_bundle_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("generator_pack_id", sa.String(120), nullable=False),
        sa.Column("generator_pack_version", sa.String(40), nullable=False),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("manifest_document", jsonb, nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("build_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("r5_export_bundle_id"),
        sa.UniqueConstraint("project_id", "build_hash"),
    )
    for column in (
        "project_id",
        "r5_export_bundle_id",
        "r5_export_bundle_hash",
        "status",
        "generator_pack_id",
        "generator_pack_version",
    ):
        op.create_index(f"ix_r6_generation_builds_{column}", "r6_generation_builds", [column])

    op.create_table(
        "r6_generated_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("file_id", sa.String(40), nullable=False),
        sa.Column("artifact_key", sa.String(180), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("generator_id", sa.String(120), nullable=False),
        sa.Column("template_ref", sa.String(160), nullable=False),
        sa.Column("lifecycle_status", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_document", jsonb, nullable=False),
        sa.UniqueConstraint("generation_build_id", "relative_path"),
        sa.UniqueConstraint("project_id", "file_hash"),
    )
    for column in (
        "project_id",
        "generation_build_id",
        "file_id",
        "artifact_key",
        "media_type",
        "generator_id",
        "template_ref",
        "lifecycle_status",
        "content_hash",
    ):
        op.create_index(f"ix_r6_generated_files_{column}", "r6_generated_files", [column])

    op.create_table(
        "r6_validation_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("blocking_finding_count", sa.Integer(), nullable=False),
        sa.Column("report_document", jsonb, nullable=False),
        sa.Column("report_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("generation_build_id"),
    )
    for column in ("project_id", "generation_build_id", "status"):
        op.create_index(f"ix_r6_validation_reports_{column}", "r6_validation_reports", [column])

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r6_validation_reports")
    op.drop_table("r6_generated_files")
    op.drop_table("r6_generation_builds")
