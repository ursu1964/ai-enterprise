"""scope R2 hash uniqueness to project

Revision ID: 7f4a1d2c9e35
Revises: 0d4c2f9a7b81
"""

from collections.abc import Sequence

from alembic import op

revision: str = "7f4a1d2c9e35"
down_revision: str | None = "0d4c2f9a7b81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "aeir_project_snapshots_snapshot_sha256_key",
        "aeir_project_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_aeir_project_snapshots_project_snapshot_sha",
        "aeir_project_snapshots",
        ["project_id", "snapshot_sha256"],
    )
    op.drop_constraint(
        "aeir_ai_operations_operation_sha256_key",
        "aeir_ai_operations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_aeir_ai_operations_project_operation_sha",
        "aeir_ai_operations",
        ["project_id", "operation_sha256"],
    )
    op.drop_constraint(
        "aeir_artifact_versions_artifact_hash_key",
        "aeir_artifact_versions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_aeir_artifact_versions_project_artifact_hash",
        "aeir_artifact_versions",
        ["project_id", "artifact_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_aeir_artifact_versions_project_artifact_hash",
        "aeir_artifact_versions",
        type_="unique",
    )
    op.create_unique_constraint(
        "aeir_artifact_versions_artifact_hash_key",
        "aeir_artifact_versions",
        ["artifact_hash"],
    )
    op.drop_constraint(
        "uq_aeir_ai_operations_project_operation_sha",
        "aeir_ai_operations",
        type_="unique",
    )
    op.create_unique_constraint(
        "aeir_ai_operations_operation_sha256_key",
        "aeir_ai_operations",
        ["operation_sha256"],
    )
    op.drop_constraint(
        "uq_aeir_project_snapshots_project_snapshot_sha",
        "aeir_project_snapshots",
        type_="unique",
    )
    op.create_unique_constraint(
        "aeir_project_snapshots_snapshot_sha256_key",
        "aeir_project_snapshots",
        ["snapshot_sha256"],
    )
