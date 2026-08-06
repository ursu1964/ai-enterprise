"""add R9 UAK kernel records

Revision ID: a9c1e4f6b8d2
Revises: f4b8d2a6c9e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a9c1e4f6b8d2"
down_revision: str | None = "f4b8d2a6c9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "r9_kernel_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope_type", sa.String(40), nullable=False),
        sa.Column("scope_id", sa.String(120), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("record_type", sa.String(80), nullable=False),
        sa.Column("record_id", sa.String(60), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("object_identity", sa.String(240), nullable=True),
        sa.Column("parent_record_hash", sa.String(64), nullable=True),
        sa.Column("record_document", jsonb, nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("scope_type", "scope_id", "record_type", "record_id", "record_hash"),
        sa.UniqueConstraint("record_hash"),
    )
    for column in (
        "scope_type",
        "scope_id",
        "organization_id",
        "project_id",
        "record_type",
        "record_id",
        "status",
        "object_identity",
        "parent_record_hash",
    ):
        op.create_index(f"ix_r9_kernel_records_{column}", "r9_kernel_records", [column])
    _immutable("r9_kernel_records")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r9_kernel_records_mutation_trigger ON r9_kernel_records"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r9_kernel_records_mutation")
    op.drop_table("r9_kernel_records")
