"""add R5 generated artifacts

Revision ID: 4d9e2f7a6b1c
Revises: 3c8d1e4f6a7b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "4d9e2f7a6b1c"
down_revision: str | None = "3c8d1e4f6a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "r5_generated_artifacts",
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
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("source_artifact_spec_hash", sa.String(64), nullable=False),
        sa.Column("content_document", jsonb, nullable=False),
        sa.Column("generated_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("transformation_run_id", "artifact_key"),
        sa.UniqueConstraint("project_id", "generated_hash"),
    )
    for column in (
        "project_id",
        "transformation_run_id",
        "artifact_key",
        "artifact_kind",
        "target",
        "media_type",
        "source_artifact_spec_hash",
    ):
        op.create_index(f"ix_r5_generated_artifacts_{column}", "r5_generated_artifacts", [column])

    op.execute(
        "CREATE FUNCTION prevent_r5_generated_artifacts_mutation() RETURNS trigger AS $$ BEGIN "
        "RAISE EXCEPTION 'r5_generated_artifacts is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER prevent_r5_generated_artifacts_mutation_trigger "
        "BEFORE UPDATE OR DELETE ON r5_generated_artifacts "
        "FOR EACH ROW EXECUTE FUNCTION prevent_r5_generated_artifacts_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r5_generated_artifacts_mutation_trigger "
        "ON r5_generated_artifacts"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r5_generated_artifacts_mutation")
    op.drop_table("r5_generated_artifacts")
