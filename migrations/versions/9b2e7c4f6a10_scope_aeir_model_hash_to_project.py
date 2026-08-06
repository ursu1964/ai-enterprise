"""scope AEIR model hash uniqueness to project

Revision ID: 9b2e7c4f6a10
Revises: 7f4a1d2c9e35
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9b2e7c4f6a10"
down_revision: str | None = "7f4a1d2c9e35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "aeir_model_versions_model_sha256_key",
        "aeir_model_versions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_aeir_model_versions_project_model_sha",
        "aeir_model_versions",
        ["project_id", "model_sha256"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_aeir_model_versions_project_model_sha",
        "aeir_model_versions",
        type_="unique",
    )
    op.create_unique_constraint(
        "aeir_model_versions_model_sha256_key",
        "aeir_model_versions",
        ["model_sha256"],
    )
