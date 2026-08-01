"""add P9 M1 resilience control plane

Revision ID: c91a74e8f603
Revises: b73e91c4d205
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c91a74e8f603"
down_revision: str | None = "b73e91c4d205"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resilience_services",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("service_type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("primary_owner", sa.String(200), nullable=False),
        sa.Column("deputy_owner", sa.String(200), nullable=False),
        sa.CheckConstraint("primary_owner <> deputy_owner", name="ck_resilience_distinct_owners"),
    )
    op.create_table(
        "resilience_recovery_objectives",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("service_id", sa.UUID(), sa.ForeignKey("resilience_services.id"), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("rto_seconds", sa.Integer(), nullable=False),
        sa.Column("rpo_seconds", sa.Integer(), nullable=False),
        sa.Column("mtpd_seconds", sa.Integer(), nullable=False),
        sa.Column("work_recovery_time_seconds", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("service_id", "policy_version"),
        sa.CheckConstraint("rto_seconds > 0 AND rpo_seconds >= 0 AND mtpd_seconds > 0"),
        sa.CheckConstraint("rpo_seconds <= mtpd_seconds"),
        sa.CheckConstraint("rto_seconds + work_recovery_time_seconds <= mtpd_seconds"),
    )
    op.create_table(
        "resilience_service_dependencies",
        sa.Column(
            "service_id", sa.UUID(), sa.ForeignKey("resilience_services.id"), primary_key=True
        ),
        sa.Column(
            "dependency_service_id",
            sa.UUID(),
            sa.ForeignKey("resilience_services.id"),
            primary_key=True,
        ),
        sa.Column("requirement", sa.String(40), nullable=False),
        sa.Column("fail_open_prohibited", sa.Boolean(), nullable=False),
        sa.CheckConstraint("service_id <> dependency_service_id"),
    )
    op.create_table(
        "continuity_activations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("mode", sa.String(60), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("allowed_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("prohibited_capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("activated_by", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_reviewed_by", sa.String(200)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("expires_at > activated_at"),
    )
    op.create_table(
        "continuity_capability_decisions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("capability", sa.String(100), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(200)),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("policy_versions", postgresql.JSONB(), nullable=False),
        sa.Column("activation_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "backup_manifests",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("backup_type", sa.String(80), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=False),
        sa.Column("encryption_profile", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("audit_checkpoint_hash", sa.String(128), nullable=False),
        sa.Column("storage_locations", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("object_count >= 0 AND total_bytes >= 0"),
    )
    op.create_table(
        "restore_verifications",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("backup_id", sa.UUID(), sa.ForeignKey("backup_manifests.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("isolated_environment", sa.Boolean(), nullable=False),
        sa.Column("production_credentials_disabled", sa.Boolean(), nullable=False),
        sa.Column("external_dispatch_blocked", sa.Boolean(), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
    )
    op.create_table(
        "disaster_recovery_plans",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("plan_key", sa.String(100), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("authority_role", sa.String(100), nullable=False),
        sa.Column("step_definitions", postgresql.JSONB(), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("plan_key", "plan_version"),
    )
    op.create_table(
        "disaster_recovery_runs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("commander", sa.String(200), nullable=False),
        sa.Column("recovery_site", sa.String(200), nullable=False),
        sa.Column("selected_recovery_point", sa.String(200)),
        sa.Column("unresolved_workflows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_external_effects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_artifacts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("exit_reviewed_by", sa.String(200)),
    )
    op.create_table(
        "disaster_recovery_steps",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("disaster_recovery_runs.id"), nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("input_binding_sha256", sa.String(128), nullable=False),
        sa.Column("output_binding_sha256", sa.String(128)),
        sa.Column("evidence_artifact_ids", postgresql.JSONB(), nullable=False),
        sa.Column("failure_code", sa.String(128)),
        sa.UniqueConstraint("run_id", "step_key", "attempt_number"),
    )


def downgrade() -> None:
    for table in (
        "disaster_recovery_steps",
        "disaster_recovery_runs",
        "disaster_recovery_plans",
        "restore_verifications",
        "backup_manifests",
        "continuity_capability_decisions",
        "continuity_activations",
        "resilience_service_dependencies",
        "resilience_recovery_objectives",
        "resilience_services",
    ):
        op.drop_table(table)
