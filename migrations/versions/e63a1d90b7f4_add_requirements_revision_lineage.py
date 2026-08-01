"""add requirements revision lineage

Revision ID: e63a1d90b7f4
Revises: c42f8e91a6d3
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e63a1d90b7f4"
down_revision: str | None = "c42f8e91a6d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "requirements_revision_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("requirements_run_id", sa.UUID(), nullable=False),
        sa.Column("source_artifact_id", sa.UUID(), nullable=False),
        sa.Column("source_review_decision_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("feedback_summary", sa.Text(), nullable=False),
        sa.Column("feedback_items", postgresql.JSONB(), nullable=False),
        sa.Column("feedback_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requirements_run_id"], ["crew_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_review_decision_id"], ["approvals.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_review_decision_id"),
        sa.UniqueConstraint("feedback_hash"),
    )
    op.create_index(
        "ix_requirements_revision_requests_run",
        "requirements_revision_requests",
        ["requirements_run_id", "created_at"],
    )
    op.create_table(
        "requirements_revision_cycles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("requirements_run_id", sa.UUID(), nullable=False),
        sa.Column("revision_request_id", sa.UUID(), nullable=False),
        sa.Column("cycle_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("resulting_artifact_id", sa.UUID(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cycle_number > 0", name="ck_requirements_revision_cycle_positive"
        ),
        sa.CheckConstraint(
            "status IN ('pending','executing','completed','failed','cancelled')",
            name="ck_requirements_revision_cycle_status",
        ),
        sa.ForeignKeyConstraint(
            ["requirements_run_id"], ["crew_runs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["revision_request_id"],
            ["requirements_revision_requests.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resulting_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("revision_request_id"),
        sa.UniqueConstraint("resulting_artifact_id"),
        sa.UniqueConstraint(
            "requirements_run_id",
            "cycle_number",
            name="uq_requirements_revision_cycle_number",
        ),
    )
    op.create_index(
        "uq_requirements_revision_cycles_active_run",
        "requirements_revision_cycles",
        ["requirements_run_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending','executing')"),
    )
    op.create_table(
        "requirements_artifact_lineage",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("revision_cycle_id", sa.UUID(), nullable=True),
        sa.Column("previous_artifact_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("revision_feedback_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0", name="ck_requirements_artifact_lineage_version"
        ),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["revision_cycle_id"],
            ["requirements_revision_cycles.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_id"),
    )
    op.add_column(
        "job_execution_attempts",
        sa.Column("revision_cycle_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "job_execution_attempts",
        sa.Column("raw_output_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "job_execution_attempts",
        sa.Column(
            "repair_attempted", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
    )
    op.add_column(
        "job_execution_attempts",
        sa.Column("repair_succeeded", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "job_execution_attempts",
        sa.Column("validation_errors", postgresql.JSONB(), nullable=True),
    )
    op.create_foreign_key(
        "fk_job_attempt_revision_cycle",
        "job_execution_attempts",
        "requirements_revision_cycles",
        ["revision_cycle_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_job_execution_attempts_revision_cycle_id",
        "job_execution_attempts",
        ["revision_cycle_id", "attempt_number"],
    )
    op.execute(
        """
        CREATE FUNCTION prevent_requirements_revision_request_mutation()
        RETURNS trigger AS $$ BEGIN
          RAISE EXCEPTION 'requirements revision requests are immutable';
        END; $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER requirements_revision_requests_immutable
        BEFORE UPDATE OR DELETE ON requirements_revision_requests
        FOR EACH ROW EXECUTE FUNCTION prevent_requirements_revision_request_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS requirements_revision_requests_immutable
        ON requirements_revision_requests
        """
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_requirements_revision_request_mutation()")
    op.drop_index(
        "ix_job_execution_attempts_revision_cycle_id",
        table_name="job_execution_attempts",
    )
    op.drop_constraint(
        "fk_job_attempt_revision_cycle", "job_execution_attempts", type_="foreignkey"
    )
    for column in (
        "validation_errors",
        "repair_succeeded",
        "repair_attempted",
        "raw_output_hash",
        "revision_cycle_id",
    ):
        op.drop_column("job_execution_attempts", column)
    op.drop_table("requirements_artifact_lineage")
    op.drop_index(
        "uq_requirements_revision_cycles_active_run",
        table_name="requirements_revision_cycles",
    )
    op.drop_table("requirements_revision_cycles")
    op.drop_index(
        "ix_requirements_revision_requests_run",
        table_name="requirements_revision_requests",
    )
    op.drop_table("requirements_revision_requests")
