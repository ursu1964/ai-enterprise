"""add blueprint organization ownership

Revision ID: f2c6a9e1b407
Revises: f1b5c8d3e7a2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2c6a9e1b407"
down_revision: str | None = "f1b5c8d3e7a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "blueprint_assets", sa.Column("organization_id", sa.UUID(), nullable=True)
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM blueprint_assets)
                   AND (SELECT count(*) FROM organizations) <> 1 THEN
                    RAISE EXCEPTION
                        'Legacy blueprint ownership is ambiguous across multiple organizations';
                END IF;
            END
            $$
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE blueprint_assets
            SET organization_id = (SELECT id FROM organizations)
            WHERE organization_id IS NULL
            """
        )
    )
    op.alter_column("blueprint_assets", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_blueprint_assets_organization_id_organizations",
        "blueprint_assets",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_blueprint_assets_organization_id", "blueprint_assets", ["organization_id"]
    )
    op.drop_constraint(
        "uq_blueprint_asset_key_version", "blueprint_assets", type_="unique"
    )
    op.create_unique_constraint(
        "uq_blueprint_asset_org_key_version",
        "blueprint_assets",
        ["organization_id", "blueprint_key", "version"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_blueprint_asset_org_key_version", "blueprint_assets", type_="unique"
    )
    op.create_unique_constraint(
        "uq_blueprint_asset_key_version",
        "blueprint_assets",
        ["blueprint_key", "version"],
    )
    op.drop_index("ix_blueprint_assets_organization_id", table_name="blueprint_assets")
    op.drop_constraint(
        "fk_blueprint_assets_organization_id_organizations",
        "blueprint_assets",
        type_="foreignkey",
    )
    op.drop_column("blueprint_assets", "organization_id")
