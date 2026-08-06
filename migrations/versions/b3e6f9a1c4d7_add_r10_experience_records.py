"""add r10 experience records

Revision ID: b3e6f9a1c4d7
Revises: a9c1e4f6b8d2
Create Date: 2026-08-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e6f9a1c4d7"
down_revision: str | None = "a9c1e4f6b8d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "r10_experience_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("record_id", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("object_ref", sa.String(length=240), nullable=True),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("record_document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "record_hash"),
        sa.UniqueConstraint("project_id", "record_type", "record_id", "record_hash"),
    )
    for column in ("project_id", "record_type", "record_id", "role", "object_ref", "status"):
        op.create_index(
            f"ix_r10_experience_records_{column}",
            "r10_experience_records",
            [column],
        )
    _immutable("r10_experience_records")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r10_experience_records_mutation_trigger "
        "ON r10_experience_records"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r10_experience_records_mutation")
    op.drop_table("r10_experience_records")


def _immutable(table_name: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_{table_name}_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{table_name} is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER prevent_{table_name}_mutation_trigger
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION prevent_{table_name}_mutation();
        """
    )
