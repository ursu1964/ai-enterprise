"""add crash-safe job execution

Revision ID: c42f8e91a6d3
Revises: b94e10d3f721
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c42f8e91a6d3"
down_revision: str | None = "b94e10d3f721"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_token", sa.UUID(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("lease_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "jobs", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("jobs", sa.Column("last_failure_class", sa.String(100), nullable=True))
    op.add_column("jobs", sa.Column("last_leased_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_lease_token", "jobs", ["lease_token"], unique=False)
    op.create_check_constraint("ck_jobs_lease_version_nonnegative", "jobs", "lease_version >= 0")
    op.create_check_constraint("ck_jobs_retry_count_nonnegative", "jobs", "retry_count >= 0")

    op.create_table(
        "job_execution_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("lease_token", sa.UUID(), nullable=False),
        sa.Column("lease_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queue_wait_ms", sa.BigInteger(), nullable=True),
        sa.Column("execution_ms", sa.BigInteger(), nullable=True),
        sa.Column("failure_class", sa.String(100), nullable=True),
        sa.Column("failure_code", sa.String(128), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number"),
    )
    op.create_index("ix_job_execution_attempts_job_id", "job_execution_attempts", ["job_id"])
    op.create_index(
        "ix_job_execution_attempts_running",
        "job_execution_attempts",
        ["status", "deadline_at"],
    )
    op.create_table(
        "worker_instances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("profile", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_id"),
    )
    op.create_index(
        "ix_worker_instances_liveness",
        "worker_instances",
        ["status", "last_heartbeat_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_worker_instances_liveness", table_name="worker_instances")
    op.drop_table("worker_instances")
    op.drop_index("ix_job_execution_attempts_running", table_name="job_execution_attempts")
    op.drop_index("ix_job_execution_attempts_job_id", table_name="job_execution_attempts")
    op.drop_table("job_execution_attempts")
    op.drop_constraint("ck_jobs_retry_count_nonnegative", "jobs", type_="check")
    op.drop_constraint("ck_jobs_lease_version_nonnegative", "jobs", type_="check")
    op.drop_index("ix_jobs_lease_token", table_name="jobs")
    op.drop_column("jobs", "last_leased_at")
    op.drop_column("jobs", "last_failure_class")
    op.drop_column("jobs", "retry_count")
    op.drop_column("jobs", "lease_version")
    op.drop_column("jobs", "lease_token")
