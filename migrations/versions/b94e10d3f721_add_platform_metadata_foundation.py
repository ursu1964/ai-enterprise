"""add platform metadata foundation

Revision ID: b94e10d3f721
Revises: a67c9e12b4d8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b94e10d3f721"
down_revision: str | None = "a67c9e12b4d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_metadata",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("platform_name", sa.String(100), nullable=False),
        sa.Column("platform_version", sa.String(50), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_platform_metadata"),
    )


def downgrade() -> None:
    op.drop_table("platform_metadata")
