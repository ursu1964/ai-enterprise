"""add r11 integration records

Revision ID: c4f7a9e2b6d1
Revises: b3e6f9a1c4d7
Create Date: 2026-08-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4f7a9e2b6d1"
down_revision: str | None = "b3e6f9a1c4d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "r11_integration_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("record_id", sa.String(length=80), nullable=False),
        sa.Column("integration_ref", sa.String(length=240), nullable=True),
        sa.Column("lifecycle_state", sa.String(length=60), nullable=True),
        sa.Column("health_status", sa.String(length=60), nullable=True),
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
    for column in (
        "project_id",
        "record_type",
        "record_id",
        "integration_ref",
        "lifecycle_state",
        "health_status",
    ):
        op.create_index(f"ix_r11_integration_records_{column}", "r11_integration_records", [column])
    _immutable("r11_integration_records")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r11_integration_records_mutation_trigger "
        "ON r11_integration_records"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r11_integration_records_mutation")
    op.drop_table("r11_integration_records")


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
