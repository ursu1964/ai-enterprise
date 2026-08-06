"""add R7 runtime registry location fields

Revision ID: d1f4a7c9e2b6
Revises: c8d3e7f1a9b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1f4a7c9e2b6"
down_revision: str | None = "c8d3e7f1a9b2"
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
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r7_runtime_deployments_mutation_trigger "
        "ON r7_runtime_deployments"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r7_runtime_deployments_mutation")
    op.add_column(
        "r7_runtime_deployments",
        sa.Column("template_version", sa.String(80), nullable=False, server_default="1.0"),
    )
    op.add_column(
        "r7_runtime_deployments",
        sa.Column(
            "deployment_location",
            sa.String(300),
            nullable=False,
            server_default="unassigned",
        ),
    )
    op.execute(
        """
        UPDATE r7_runtime_deployments
        SET deployment_document =
            deployment_document
            || jsonb_build_object(
                'template_version',
                template_version,
                'deployment_location',
                deployment_location
            )
        """
    )
    op.alter_column("r7_runtime_deployments", "template_version", server_default=None)
    op.alter_column("r7_runtime_deployments", "deployment_location", server_default=None)
    op.create_index(
        "ix_r7_runtime_deployments_template_version",
        "r7_runtime_deployments",
        ["template_version"],
    )
    op.create_index(
        "ix_r7_runtime_deployments_deployment_location",
        "r7_runtime_deployments",
        ["deployment_location"],
    )
    _immutable("r7_runtime_deployments")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS prevent_r7_runtime_deployments_mutation_trigger "
        "ON r7_runtime_deployments"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_r7_runtime_deployments_mutation")
    op.drop_index(
        "ix_r7_runtime_deployments_deployment_location",
        table_name="r7_runtime_deployments",
    )
    op.drop_index(
        "ix_r7_runtime_deployments_template_version",
        table_name="r7_runtime_deployments",
    )
    op.drop_column("r7_runtime_deployments", "deployment_location")
    op.drop_column("r7_runtime_deployments", "template_version")
    _immutable("r7_runtime_deployments")
