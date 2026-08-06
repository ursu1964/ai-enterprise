"""add R8 UGEIF records

Revision ID: f4b8d2a6c9e1
Revises: e2a9c4f7b1d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f4b8d2a6c9e1"
down_revision: str | None = "e2a9c4f7b1d3"
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
        "r8_governance_evolution_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("record_type", sa.String(80), nullable=False),
        sa.Column("record_id", sa.String(60), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("lifecycle_state", sa.String(60), nullable=True),
        sa.Column("approval_status", sa.String(60), nullable=True),
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
        sa.UniqueConstraint("project_id", "record_type", "record_id", "record_hash"),
        sa.UniqueConstraint("project_id", "record_hash"),
    )
    for column in (
        "project_id",
        "record_type",
        "record_id",
        "status",
        "lifecycle_state",
        "approval_status",
        "parent_record_hash",
    ):
        op.create_index(
            f"ix_r8_governance_evolution_records_{column}",
            "r8_governance_evolution_records",
            [column],
        )
    _immutable("r8_governance_evolution_records")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r8_governance_evolution_records_mutation_trigger "
        "ON r8_governance_evolution_records"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r8_governance_evolution_records_mutation")
    op.drop_table("r8_governance_evolution_records")
