"""add R6 lifecycle events

Revision ID: 7c4e2a9b8d1f
Revises: 6a2b8c9d1e5f
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7c4e2a9b8d1f"
down_revision: str | None = "6a2b8c9d1e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "r6_lifecycle_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "generation_build_id",
            sa.Uuid(),
            sa.ForeignKey("r6_generation_builds.id"),
            nullable=False,
        ),
        sa.Column("event_id", sa.String(40), nullable=False),
        sa.Column("build_hash", sa.String(64), nullable=False),
        sa.Column("file_id", sa.String(40), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(40), nullable=False),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_document", jsonb, nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("generation_build_id", "event_id"),
        sa.UniqueConstraint("project_id", "event_hash"),
    )
    for column in (
        "project_id",
        "generation_build_id",
        "event_id",
        "build_hash",
        "file_id",
        "event_type",
        "from_status",
        "to_status",
    ):
        op.create_index(f"ix_r6_lifecycle_events_{column}", "r6_lifecycle_events", [column])
    op.execute(
        "CREATE FUNCTION prevent_r6_lifecycle_events_mutation() RETURNS trigger AS $$ BEGIN "
        "RAISE EXCEPTION 'r6_lifecycle_events is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER prevent_r6_lifecycle_events_mutation_trigger "
        "BEFORE UPDATE OR DELETE ON r6_lifecycle_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_r6_lifecycle_events_mutation()"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r6_lifecycle_events_mutation_trigger ON r6_lifecycle_events"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r6_lifecycle_events_mutation")
    op.drop_table("r6_lifecycle_events")
