"""add controlled integration control plane

Revision ID: e31b6d42a901
Revises: a10d17f5c9b2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e31b6d42a901"
down_revision: str | None = "a10d17f5c9b2"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("execution_runs", sa.Column("base_tree_sha", sa.String(64)))
    op.add_column(
        "execution_runs",
        sa.Column("patch_status", sa.String(40), server_default="generated", nullable=False),
    )
    op.add_column("execution_runs", sa.Column("parent_execution_run_id", sa.UUID()))
    op.add_column("execution_runs", sa.Column("revision_source_review_run_id", sa.UUID()))
    op.add_column("execution_runs", sa.Column("root_execution_run_id", sa.UUID()))
    op.add_column(
        "execution_runs",
        sa.Column("lineage_depth", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint("ck_execution_lineage_depth", "execution_runs", "lineage_depth >= 0")
    op.create_foreign_key(
        "fk_execution_parent",
        "execution_runs",
        "execution_runs",
        ["parent_execution_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_execution_root",
        "execution_runs",
        "execution_runs",
        ["root_execution_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_execution_revision_review",
        "execution_runs",
        "patch_review_runs",
        ["revision_source_review_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("patch_review_findings", sa.Column("required_change", sa.Text()))
    op.create_check_constraint(
        "ck_review_finding_line_start",
        "patch_review_findings",
        "line_start IS NULL OR line_start > 0",
    )
    op.create_check_constraint(
        "ck_review_finding_line_end",
        "patch_review_findings",
        "line_end IS NULL OR line_end >= line_start",
    )
    op.create_table(
        "execution_run_revision_findings",
        sa.Column("execution_run_id", sa.UUID(), nullable=False),
        sa.Column("review_finding_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["review_finding_id"], ["patch_review_findings.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("execution_run_id", "review_finding_id"),
    )
    op.create_table(
        "integration_eligibilities",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("execution_run_id", sa.UUID(), nullable=False, unique=True),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("patch_sha256", sa.String(64), nullable=False),
        sa.Column("base_commit_sha", sa.String(64), nullable=False),
        sa.Column("base_tree_sha", sa.String(64), nullable=False),
        sa.Column("accepted_review_id", sa.UUID()),
        sa.Column("failure_reasons", postgresql.JSONB(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["accepted_review_id"], ["patch_review_runs.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_integration_eligibilities_execution_run_id",
        "integration_eligibilities",
        ["execution_run_id"],
    )
    op.create_table(
        "integration_approvals",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("execution_run_id", sa.UUID(), nullable=False),
        sa.Column("eligibility_id", sa.UUID(), nullable=False),
        sa.Column("approver_subject", sa.String(200), nullable=False),
        sa.Column("approver_role", sa.String(80), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("repository_url", sa.Text(), nullable=False),
        sa.Column("target_branch", sa.String(200), nullable=False),
        sa.Column("approved_patch_sha256", sa.String(64), nullable=False),
        sa.Column("approved_base_commit_sha", sa.String(64), nullable=False),
        sa.Column("approved_base_tree_sha", sa.String(64), nullable=False),
        sa.Column("approved_test_commands", postgresql.JSONB(), nullable=False),
        sa.Column("approved_test_commands_sha256", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["eligibility_id"], ["integration_eligibilities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_integration_approvals_execution_run_id",
        "integration_approvals",
        ["execution_run_id"],
    )
    op.create_table(
        "integration_attempts",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("execution_run_id", sa.UUID(), nullable=False),
        sa.Column("integration_approval_id", sa.UUID(), nullable=False, unique=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("target_branch", sa.String(200), nullable=False),
        sa.Column("expected_patch_sha256", sa.String(64), nullable=False),
        sa.Column("expected_base_commit_sha", sa.String(64), nullable=False),
        sa.Column("expected_base_tree_sha", sa.String(64), nullable=False),
        sa.Column("actual_base_commit_sha", sa.String(64)),
        sa.Column("actual_base_tree_sha", sa.String(64)),
        sa.Column("resulting_tree_sha", sa.String(64)),
        sa.Column("failure_code", sa.String(128)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("correlation_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["execution_run_id"], ["execution_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["integration_approval_id"],
            ["integration_approvals.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "execution_run_id", "attempt_number", name="uq_integration_attempt_number"
        ),
    )
    op.create_index(
        "ix_integration_attempts_execution_run_id",
        "integration_attempts",
        ["execution_run_id"],
    )
    op.create_index("ix_integration_attempts_status", "integration_attempts", ["status"])


def downgrade() -> None:
    op.drop_table("integration_attempts")
    op.drop_table("integration_approvals")
    op.drop_table("integration_eligibilities")
    op.drop_table("execution_run_revision_findings")
    op.drop_constraint("ck_review_finding_line_end", "patch_review_findings", type_="check")
    op.drop_constraint("ck_review_finding_line_start", "patch_review_findings", type_="check")
    op.drop_column("patch_review_findings", "required_change")
    op.drop_constraint("fk_execution_revision_review", "execution_runs", type_="foreignkey")
    op.drop_constraint("fk_execution_root", "execution_runs", type_="foreignkey")
    op.drop_constraint("fk_execution_parent", "execution_runs", type_="foreignkey")
    op.drop_constraint("ck_execution_lineage_depth", "execution_runs", type_="check")
    for column in (
        "lineage_depth",
        "root_execution_run_id",
        "revision_source_review_run_id",
        "parent_execution_run_id",
        "patch_status",
        "base_tree_sha",
    ):
        op.drop_column("execution_runs", column)
