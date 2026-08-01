"""add governed recovery and resilient attempt evidence

Revision ID: f62c8a1047de
Revises: e31b6d42a901
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f62c8a1047de"
down_revision: str | None = "e31b6d42a901"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

UUID = sa.UUID
JSONB = postgresql.JSONB


def _run_table(name: str, attempt_table: str, attempt_column: str, constraint_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", UUID(), primary_key=True),
        sa.Column(attempt_column, UUID(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_stage", sa.String(80), nullable=False),
        sa.Column("claim_token_hash", sa.String(64), nullable=False),
        sa.Column("claim_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_class", sa.String(80)),
        sa.Column("failure_code", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint([attempt_column], [f"{attempt_table}.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(attempt_column, "run_number", name=constraint_name),
    )


def _stage_table(name: str, run_table: str, constraint_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("run_id", UUID(), nullable=False),
        sa.Column("stage_name", sa.String(80), nullable=False),
        sa.Column("stage_attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("input_binding_sha256", sa.String(64), nullable=False),
        sa.Column("output_binding_sha256", sa.String(64)),
        sa.Column("evidence_artifact_id", UUID()),
        sa.Column("failure_code", sa.String(128)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.BigInteger()),
        sa.ForeignKeyConstraint(["run_id"], [f"{run_table}.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("run_id", "stage_name", "stage_attempt", name=constraint_name),
    )


def upgrade() -> None:
    _run_table(
        "integration_attempt_runs",
        "integration_attempts",
        "integration_attempt_id",
        "uq_integration_run_number",
    )
    _stage_table(
        "integration_stage_executions",
        "integration_attempt_runs",
        "uq_integration_stage_run",
    )
    op.create_table(
        "commit_plans",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("attempt_kind", sa.String(32), nullable=False),
        sa.Column("attempt_id", UUID(), nullable=False),
        sa.Column("tree_sha", sa.String(64), nullable=False),
        sa.Column("parent_sha", sa.String(64), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_email", sa.String(320), nullable=False),
        sa.Column("author_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committer_name", sa.String(200), nullable=False),
        sa.Column("committer_email", sa.String(320), nullable=False),
        sa.Column("committer_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("message_sha256", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("binding_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("attempt_kind", "attempt_id", name="uq_commit_plan_attempt"),
    )
    op.create_table(
        "integration_commits",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("integration_attempt_id", UUID(), nullable=False, unique=True),
        sa.Column("commit_sha", sa.String(64), nullable=False, unique=True),
        sa.Column("tree_sha", sa.String(64), nullable=False),
        sa.Column("parent_commit_sha", sa.String(64), nullable=False),
        sa.Column("remote_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["integration_attempt_id"], ["integration_attempts.id"], ondelete="RESTRICT"
        ),
    )
    op.create_table(
        "rollback_records",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("integration_attempt_id", UUID(), nullable=False, unique=True),
        sa.Column("integration_commit_id", UUID(), nullable=False, unique=True),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("target_branch", sa.String(200), nullable=False),
        sa.Column("integration_commit_sha", sa.String(64), nullable=False),
        sa.Column("parent_commit_sha", sa.String(64), nullable=False),
        sa.Column("integration_tree_sha", sa.String(64), nullable=False),
        sa.Column("parent_tree_sha", sa.String(64), nullable=False),
        sa.Column("changed_paths", JSONB(), nullable=False),
        sa.Column("changed_paths_sha256", sa.String(64), nullable=False),
        sa.Column("inverse_diff_artifact_id", UUID(), nullable=False),
        sa.Column("inverse_diff_sha256", sa.String(64), nullable=False),
        sa.Column("original_patch_sha256", sa.String(64), nullable=False),
        sa.Column("approved_test_commands", JSONB(), nullable=False),
        sa.Column("approved_test_commands_sha256", sa.String(64), nullable=False),
        sa.Column("external_side_effects_declared", sa.Boolean(), nullable=False),
        sa.Column("database_change_detected", sa.Boolean(), nullable=False),
        sa.Column("deployment_change_detected", sa.Boolean(), nullable=False),
        sa.Column("recovery_policy_version", sa.String(80), nullable=False),
        sa.Column("rollback_binding_sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["integration_attempt_id"], ["integration_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["integration_commit_id"], ["integration_commits.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["inverse_diff_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"
        ),
    )
    op.create_table(
        "recovery_incidents",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("integration_attempt_id", UUID(), nullable=False),
        sa.Column("rollback_record_id", UUID(), nullable=False),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("reported_by", sa.String(200), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("affected_environment", sa.String(120), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_reference", sa.String(200)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["integration_attempt_id"], ["integration_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rollback_record_id"], ["rollback_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "recovery_assessments",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("incident_id", UUID(), nullable=False),
        sa.Column("rollback_record_id", UUID(), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("recommended_strategy", sa.String(40), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("expected_remote_head_sha", sa.String(64), nullable=False),
        sa.Column("integration_commit_is_ancestor", sa.Boolean(), nullable=False),
        sa.Column("direct_revert_possible", sa.Boolean(), nullable=False),
        sa.Column("database_coordination_required", sa.Boolean(), nullable=False),
        sa.Column("external_coordination_required", sa.Boolean(), nullable=False),
        sa.Column("required_test_commands", JSONB(), nullable=False),
        sa.Column("findings", JSONB(), nullable=False),
        sa.Column("assessment_policy_version", sa.String(80), nullable=False),
        sa.Column("assessment_binding_sha256", sa.String(64), nullable=False),
        sa.Column("assessed_by", sa.String(200), nullable=False),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["recovery_incidents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["rollback_record_id"], ["rollback_records.id"], ondelete="RESTRICT"
        ),
    )
    op.create_table(
        "rollback_approvals",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("recovery_assessment_id", UUID(), nullable=False),
        sa.Column("rollback_record_id", UUID(), nullable=False),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("target_branch", sa.String(200), nullable=False),
        sa.Column("recovery_strategy", sa.String(40), nullable=False),
        sa.Column("expected_remote_head_sha", sa.String(64), nullable=False),
        sa.Column("integration_commit_sha", sa.String(64), nullable=False),
        sa.Column("required_test_commands", JSONB(), nullable=False),
        sa.Column("required_test_commands_sha256", sa.String(64), nullable=False),
        sa.Column("approval_binding_sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("approver_subject", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["recovery_assessment_id"], ["recovery_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rollback_record_id"], ["rollback_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_active_rollback_approval",
        "rollback_approvals",
        ["recovery_assessment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "recovery_attempts",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("rollback_approval_id", UUID(), nullable=False, unique=True),
        sa.Column("recovery_assessment_id", UUID(), nullable=False),
        sa.Column("rollback_record_id", UUID(), nullable=False),
        sa.Column("project_id", UUID(), nullable=False),
        sa.Column("target_branch", sa.String(200), nullable=False),
        sa.Column("expected_remote_head_sha", sa.String(64), nullable=False),
        sa.Column("integration_commit_sha", sa.String(64), nullable=False),
        sa.Column("recovery_strategy", sa.String(40), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("correlation_id", UUID(), nullable=False),
        sa.Column("failure_class", sa.String(80)),
        sa.Column("failure_code", sa.String(128)),
        sa.Column("failure_message", sa.Text()),
        sa.Column("worker_id", sa.String(200)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("push_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["rollback_approval_id"], ["rollback_approvals.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recovery_assessment_id"], ["recovery_assessments.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["rollback_record_id"], ["rollback_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
    )
    _run_table(
        "recovery_attempt_runs",
        "recovery_attempts",
        "recovery_attempt_id",
        "uq_recovery_run_number",
    )
    _stage_table(
        "recovery_stage_executions",
        "recovery_attempt_runs",
        "uq_recovery_stage_run",
    )
    op.create_table(
        "recovery_test_runs",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("recovery_attempt_id", UUID(), nullable=False),
        sa.Column("command_index", sa.Integer(), nullable=False),
        sa.Column("command", JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("stdout_artifact_id", UUID()),
        sa.Column("stderr_artifact_id", UUID()),
        sa.Column("duration_ms", sa.BigInteger()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["recovery_attempt_id"], ["recovery_attempts.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["stdout_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stderr_artifact_id"], ["artifacts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "recovery_attempt_id", "command_index", name="uq_recovery_test_command"
        ),
    )
    op.create_table(
        "recovery_commits",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("recovery_attempt_id", UUID(), nullable=False, unique=True),
        sa.Column("commit_sha", sa.String(64), nullable=False, unique=True),
        sa.Column("tree_sha", sa.String(64), nullable=False),
        sa.Column("parent_commit_sha", sa.String(64), nullable=False),
        sa.Column("reverted_integration_commit_sha", sa.String(64), nullable=False),
        sa.Column("commit_message_sha256", sa.String(64), nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("author_email", sa.String(320), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["recovery_attempt_id"], ["recovery_attempts.id"], ondelete="RESTRICT"
        ),
    )
    op.create_table(
        "recovery_remote_verifications",
        sa.Column("id", UUID(), primary_key=True),
        sa.Column("recovery_commit_id", UUID(), nullable=False, unique=True),
        sa.Column("remote_commit_sha", sa.String(64), nullable=False),
        sa.Column("remote_tree_sha", sa.String(64), nullable=False),
        sa.Column("remote_parent_sha", sa.String(64), nullable=False),
        sa.Column("integration_commit_in_history", sa.Boolean(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["recovery_commit_id"], ["recovery_commits.id"], ondelete="RESTRICT"
        ),
    )


def downgrade() -> None:
    op.drop_table("recovery_remote_verifications")
    op.drop_table("recovery_commits")
    op.drop_table("recovery_test_runs")
    op.drop_table("recovery_stage_executions")
    op.drop_table("recovery_attempt_runs")
    op.drop_table("recovery_attempts")
    op.drop_index("uq_active_rollback_approval", table_name="rollback_approvals")
    op.drop_table("rollback_approvals")
    op.drop_table("recovery_assessments")
    op.drop_table("recovery_incidents")
    op.drop_table("rollback_records")
    op.drop_table("integration_commits")
    op.drop_table("commit_plans")
    op.drop_table("integration_stage_executions")
    op.drop_table("integration_attempt_runs")
