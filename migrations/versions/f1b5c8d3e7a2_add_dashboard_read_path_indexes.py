"""add dashboard read path indexes

Revision ID: f1b5c8d3e7a2
Revises: e9a4b7c2d6f1
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1b5c8d3e7a2"
down_revision: str | None = "e9a4b7c2d6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_jobs_project_created_at",
        "jobs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_crew_runs_project_created_at",
        "crew_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_work_packages_project_created_at",
        "work_packages",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_packages_project_created_at", table_name="work_packages")
    op.drop_index("ix_crew_runs_project_created_at", table_name="crew_runs")
    op.drop_index("ix_jobs_project_created_at", table_name="jobs")
