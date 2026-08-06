"""add bk r11 archive publication records

Revision ID: b2e6f9a3c8d1
Revises: a1d5e8f2b9c4
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2e6f9a3c8d1"
down_revision: str | None = "a1d5e8f2b9c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _archive_publications()
    _archive_verifications()
    for table_name in ("bk_r11_archive_publications", "bk_r11_archive_verifications"):
        _immutable(table_name)


def downgrade() -> None:
    for table_name in ("bk_r11_archive_verifications", "bk_r11_archive_publications"):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table_name}_mutation_trigger ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation")
        op.drop_table(table_name)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_key", sa.String(length=160), nullable=False),
        sa.Column("package_id", sa.String(length=220), nullable=False),
        sa.Column("archive_backend", sa.String(length=80), nullable=False),
        sa.Column("archive_uri", sa.String(length=600), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _archive_publications() -> None:
    op.create_table(
        "bk_r11_archive_publications",
        *_base_columns(),
        sa.Column("archive_hash", sa.String(length=64), nullable=False),
        sa.Column("publication_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "publication_hash"),
    )
    _indexes(
        "bk_r11_archive_publications",
        "project_key",
        "package_id",
        "archive_backend",
        "status",
    )


def _archive_verifications() -> None:
    op.create_table(
        "bk_r11_archive_verifications",
        *_base_columns(),
        sa.Column("verification_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "verification_hash"),
    )
    _indexes(
        "bk_r11_archive_verifications",
        "project_key",
        "package_id",
        "archive_backend",
        "status",
    )


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


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
