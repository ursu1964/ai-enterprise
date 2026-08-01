"""add audit query indexes

Revision ID: a10d17f5c9b2
Revises: c80980967426
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a10d17f5c9b2"
down_revision: str | None = "c80980967426"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_project_occurred_id",
        "audit_events",
        ["project_id", "created_at", "id"],
    )
    op.create_index(
        "ix_execution_events_execution_occurred_id",
        "execution_events",
        ["execution_run_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_patch_review_events_review_occurred_id",
        "patch_review_events",
        ["patch_review_run_id", "occurred_at", "id"],
    )
    op.create_index(
        "ix_execution_runs_project_created_id",
        "execution_runs",
        ["project_id", "created_at", "id"],
    )
    op.create_index(
        "ix_patch_review_runs_project_created_id",
        "patch_review_runs",
        ["project_id", "created_at", "id"],
    )
    op.create_index(
        "ix_execution_test_results_run_sequence",
        "execution_test_results",
        ["execution_run_id", "sequence"],
    )
    op.create_index(
        "ix_patch_review_findings_review_severity_blocking",
        "patch_review_findings",
        ["patch_review_run_id", "severity", "blocking"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_patch_review_findings_review_severity_blocking",
        table_name="patch_review_findings",
    )
    op.drop_index(
        "ix_execution_test_results_run_sequence",
        table_name="execution_test_results",
    )
    op.drop_index(
        "ix_patch_review_runs_project_created_id",
        table_name="patch_review_runs",
    )
    op.drop_index(
        "ix_execution_runs_project_created_id",
        table_name="execution_runs",
    )
    op.drop_index(
        "ix_patch_review_events_review_occurred_id",
        table_name="patch_review_events",
    )
    op.drop_index(
        "ix_execution_events_execution_occurred_id",
        table_name="execution_events",
    )
    op.drop_index(
        "ix_audit_events_project_occurred_id",
        table_name="audit_events",
    )
