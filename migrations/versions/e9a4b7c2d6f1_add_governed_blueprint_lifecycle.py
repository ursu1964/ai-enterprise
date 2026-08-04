"""add governed blueprint lifecycle

Revision ID: e9a4b7c2d6f1
Revises: d8e9f0a1b2c3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e9a4b7c2d6f1"
down_revision: str | None = "d8e9f0a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "blueprint_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("blueprint_key", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("lifecycle", sa.String(40), nullable=False),
        sa.Column("source_project_id", sa.UUID(), nullable=False),
        sa.Column("source_phase", sa.String(80), nullable=False),
        sa.Column("source_artifact_id", sa.UUID(), nullable=True),
        sa.Column("supersedes_id", sa.UUID(), nullable=True),
        sa.Column("pattern", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("economic_proof", postgresql.JSONB(), nullable=False),
        sa.Column("recommended_use", sa.Text(), nullable=False),
        sa.Column("reuse_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "lifecycle IN ('proposed', 'reviewed', 'reusable', 'deprecated', 'improved')",
            name="ck_blueprint_asset_lifecycle",
        ),
        sa.CheckConstraint("version > 0", name="ck_blueprint_asset_version_positive"),
        sa.CheckConstraint(
            "reuse_count >= 0", name="ck_blueprint_asset_reuse_count_nonnegative"
        ),
        sa.ForeignKeyConstraint(
            ["source_project_id"], ["projects.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["blueprint_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "blueprint_key", "version", name="uq_blueprint_asset_key_version"
        ),
    )
    op.create_index(
        "ix_blueprint_assets_blueprint_key", "blueprint_assets", ["blueprint_key"]
    )
    op.create_index("ix_blueprint_assets_lifecycle", "blueprint_assets", ["lifecycle"])
    op.create_index(
        "ix_blueprint_assets_source_project_id",
        "blueprint_assets",
        ["source_project_id"],
    )
    op.create_table(
        "blueprint_decisions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("blueprint_id", sa.UUID(), nullable=False),
        sa.Column("previous_lifecycle", sa.String(40), nullable=False),
        sa.Column("lifecycle", sa.String(40), nullable=False),
        sa.Column("reviewer", sa.String(200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["blueprint_id"], ["blueprint_assets.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_blueprint_decisions_blueprint_id", "blueprint_decisions", ["blueprint_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_blueprint_decisions_blueprint_id", table_name="blueprint_decisions"
    )
    op.drop_table("blueprint_decisions")
    op.drop_index(
        "ix_blueprint_assets_source_project_id", table_name="blueprint_assets"
    )
    op.drop_index("ix_blueprint_assets_lifecycle", table_name="blueprint_assets")
    op.drop_index("ix_blueprint_assets_blueprint_key", table_name="blueprint_assets")
    op.drop_table("blueprint_assets")
