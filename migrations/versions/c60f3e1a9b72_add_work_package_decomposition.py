"""add work package decomposition

Revision ID: c60f3e1a9b72
Revises: b18e70ac42d1
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.decomposition.models import (
    CandidateOutputModel,
    DecompositionApprovalModel,
    DecompositionArtifactModel,
    DecompositionReviewModel,
    DecompositionRunModel,
    RepositoryIndexModel,
    RepositorySnapshotModel,
    ValidationFindingModel,
    WorkPackageDependencyModel,
    WorkPackageModel,
)

revision: str = "c60f3e1a9b72"
down_revision: str | None = "b18e70ac42d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    RepositorySnapshotModel,
    RepositoryIndexModel,
    DecompositionRunModel,
    CandidateOutputModel,
    DecompositionArtifactModel,
    WorkPackageModel,
    WorkPackageDependencyModel,
    ValidationFindingModel,
    DecompositionReviewModel,
    DecompositionApprovalModel,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=False)
    op.create_foreign_key(
        "fk_decomposition_run_parent_artifact",
        "work_package_decomposition_runs",
        "work_package_decomposition_artifacts",
        ["parent_artifact_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_decomposition_run_parent_artifact",
        "work_package_decomposition_runs",
        type_="foreignkey",
    )
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=False)
