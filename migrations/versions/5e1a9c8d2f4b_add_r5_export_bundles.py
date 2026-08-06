"""add R5 export bundles

Revision ID: 5e1a9c8d2f4b
Revises: 4d9e2f7a6b1c
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5e1a9c8d2f4b"
down_revision: str | None = "4d9e2f7a6b1c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "r5_export_bundles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "transformation_run_id",
            sa.Uuid(),
            sa.ForeignKey("r5_transformation_runs.id"),
            nullable=False,
        ),
        sa.Column("artifact_count", sa.Integer(), nullable=False),
        sa.Column("source_model_sha256", sa.String(64), nullable=False),
        sa.Column("source_snapshot_id", sa.String(40), nullable=False),
        sa.Column("source_snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("registry_version", sa.String(40), nullable=False),
        sa.Column("template_pack_version", sa.String(40), nullable=False),
        sa.Column("bundle_document", jsonb, nullable=False),
        sa.Column("bundle_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("transformation_run_id"),
        sa.UniqueConstraint("project_id", "bundle_hash"),
    )
    for column in (
        "project_id",
        "transformation_run_id",
        "source_model_sha256",
        "source_snapshot_id",
        "registry_version",
        "template_pack_version",
    ):
        op.create_index(f"ix_r5_export_bundles_{column}", "r5_export_bundles", [column])

    op.execute(
        "CREATE FUNCTION prevent_r5_export_bundles_mutation() RETURNS trigger AS $$ BEGIN "
        "RAISE EXCEPTION 'r5_export_bundles is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER prevent_r5_export_bundles_mutation_trigger "
        "BEFORE UPDATE OR DELETE ON r5_export_bundles "
        "FOR EACH ROW EXECUTE FUNCTION prevent_r5_export_bundles_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r5_export_bundles_mutation_trigger ON r5_export_bundles"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r5_export_bundles_mutation")
    op.drop_table("r5_export_bundles")
