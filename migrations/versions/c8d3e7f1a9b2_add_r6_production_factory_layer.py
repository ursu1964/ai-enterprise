"""add R6 production factory layer

Revision ID: c8d3e7f1a9b2
Revises: b7c2d9e4f1a6
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8d3e7f1a9b2"
down_revision: str | None = "b7c2d9e4f1a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r6_installed_generator_packs",
    "r6_parallel_generation_plans",
    "r6_validation_gate_runs",
    "r6_artifact_repository_publications",
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
    op.drop_constraint(
        "r6_generation_builds_r5_export_bundle_id_key",
        "r6_generation_builds",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_r6_generation_builds_bundle_pack_version",
        "r6_generation_builds",
        ["r5_export_bundle_id", "generator_pack_id", "generator_pack_version"],
    )

    op.create_table(
        "r6_installed_generator_packs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("installation_id", sa.String(40), nullable=False),
        sa.Column("pack_id", sa.String(120), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("technology_stack", jsonb, nullable=False),
        sa.Column("supported_targets", jsonb, nullable=False),
        sa.Column("validation_gates", jsonb, nullable=False),
        sa.Column("repository_kinds", jsonb, nullable=False),
        sa.Column("pack_document", jsonb, nullable=False),
        sa.Column("installation_document", jsonb, nullable=False),
        sa.Column("installation_hash", sa.String(64), nullable=False),
        sa.Column("installed_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "pack_id", "version"),
        sa.UniqueConstraint("project_id", "installation_hash"),
    )
    for column in ("project_id", "installation_id", "pack_id", "version", "status"):
        op.create_index(
            f"ix_r6_installed_generator_packs_{column}",
            "r6_installed_generator_packs",
            [column],
        )

    op.create_table(
        "r6_parallel_generation_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("plan_id", sa.String(40), nullable=False),
        sa.Column("generator_pack_id", sa.String(120), nullable=False),
        sa.Column("max_parallelism", sa.Integer(), nullable=False),
        sa.Column("lanes_document", jsonb, nullable=False),
        sa.Column("plan_document", jsonb, nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("generation_build_id", "plan_id"),
        sa.UniqueConstraint("project_id", "plan_hash"),
    )
    for column in ("project_id", "generation_build_id", "plan_id", "generator_pack_id"):
        op.create_index(
            f"ix_r6_parallel_generation_plans_{column}",
            "r6_parallel_generation_plans",
            [column],
        )

    op.create_table(
        "r6_validation_gate_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("gate_run_id", sa.String(40), nullable=False),
        sa.Column("gate_id", sa.String(160), nullable=False),
        sa.Column("command", jsonb, nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("gate_document", jsonb, nullable=False),
        sa.Column("gate_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("generation_build_id", "gate_run_id"),
        sa.UniqueConstraint("project_id", "gate_hash"),
    )
    for column in ("project_id", "generation_build_id", "gate_run_id", "gate_id", "status"):
        op.create_index(f"ix_r6_validation_gate_runs_{column}", "r6_validation_gate_runs", [column])

    op.create_table(
        "r6_artifact_repository_publications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("publication_id", sa.String(40), nullable=False),
        sa.Column("repository_kind", sa.String(80), nullable=False),
        sa.Column("repository_ref", sa.String(300), nullable=False),
        sa.Column("version_ref", sa.String(160), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("content_address", sa.String(64), nullable=False),
        sa.Column("publication_document", jsonb, nullable=False),
        sa.Column("publication_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("generation_build_id", "publication_id"),
        sa.UniqueConstraint("project_id", "publication_hash"),
    )
    for column in (
        "project_id",
        "generation_build_id",
        "publication_id",
        "repository_kind",
        "version_ref",
        "content_address",
    ):
        op.create_index(
            f"ix_r6_artifact_repository_publications_{column}",
            "r6_artifact_repository_publications",
            [column],
        )

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r6_artifact_repository_publications")
    op.drop_table("r6_validation_gate_runs")
    op.drop_table("r6_parallel_generation_plans")
    op.drop_table("r6_installed_generator_packs")
    op.drop_constraint(
        "uq_r6_generation_builds_bundle_pack_version",
        "r6_generation_builds",
        type_="unique",
    )
    op.create_unique_constraint(
        "r6_generation_builds_r5_export_bundle_id_key",
        "r6_generation_builds",
        ["r5_export_bundle_id"],
    )
