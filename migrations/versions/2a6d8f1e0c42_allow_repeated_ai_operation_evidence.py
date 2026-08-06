"""allow repeated AI operation evidence

Revision ID: 2a6d8f1e0c42
Revises: 9b2e7c4f6a10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2a6d8f1e0c42"
down_revision: str | None = "9b2e7c4f6a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_aeir_ai_operations_project_operation_sha",
        "aeir_ai_operations",
        type_="unique",
    )
    op.create_index(
        "ix_aeir_ai_operations_operation_sha256",
        "aeir_ai_operations",
        ["operation_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_aeir_ai_operations_operation_sha256",
        table_name="aeir_ai_operations",
    )
    op.create_unique_constraint(
        "uq_aeir_ai_operations_project_operation_sha",
        "aeir_ai_operations",
        ["project_id", "operation_sha256"],
    )
