"""add r21 execution orchestrator records

Revision ID: d6e8f2a1c9b4
Revises: c4f7a9e2b6d1
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d6e8f2a1c9b4"
down_revision: str | None = "c4f7a9e2b6d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _compilations()
    _plans()
    _executions()
    _checkpoints()
    _work_packages()
    _approval_gates()
    _approval_decisions()
    _events()
    _evidence()
    _idempotency()
    for table_name in (
        "r21_project_compilations",
        "r21_execution_plans",
        "r21_executions",
        "r21_execution_checkpoints",
        "r21_work_packages",
        "r21_approval_gates",
        "r21_approval_decisions",
        "r21_execution_events",
        "r21_evidence_records",
        "r21_idempotency_records",
    ):
        _immutable(table_name)


def downgrade() -> None:
    for table_name in (
        "r21_idempotency_records",
        "r21_evidence_records",
        "r21_execution_events",
        "r21_approval_decisions",
        "r21_approval_gates",
        "r21_work_packages",
        "r21_execution_checkpoints",
        "r21_executions",
        "r21_execution_plans",
        "r21_project_compilations",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table_name}_mutation_trigger ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation")
        op.drop_table(table_name)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_key", sa.String(length=160), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _compilations() -> None:
    op.create_table(
        "r21_project_compilations",
        *_base_columns(),
        sa.Column("compilation_id", sa.String(length=160), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("compilation_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "compilation_hash"),
    )
    _indexes("r21_project_compilations", "project_key", "manifest_hash")


def _plans() -> None:
    op.create_table(
        "r21_execution_plans",
        *_base_columns(),
        sa.Column("execution_plan_id", sa.String(length=200), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.Column("manifest_version", sa.String(length=80), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "execution_plan_id", "plan_hash"),
        sa.UniqueConstraint("project_key", "plan_hash"),
    )
    _indexes("r21_execution_plans", "project_key", "execution_plan_id")


def _executions() -> None:
    op.create_table(
        "r21_executions",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("execution_plan_id", sa.String(length=200), nullable=False),
        sa.Column("project_state", sa.String(length=80), nullable=False),
        sa.Column("execution_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "execution_id", "execution_hash"),
        sa.UniqueConstraint("project_key", "execution_hash"),
    )
    _indexes("r21_executions", "project_key", "execution_id", "execution_plan_id", "project_state")


def _checkpoints() -> None:
    op.create_table(
        "r21_execution_checkpoints",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=200), nullable=False),
        sa.Column("project_state", sa.String(length=80), nullable=False),
        sa.Column("checkpoint_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_execution_checkpoints", "execution_id", "project_key", "project_state")


def _work_packages() -> None:
    op.create_table(
        "r21_work_packages",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("work_package_id", sa.String(length=200), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_work_packages", "execution_id", "work_package_id", "state")


def _approval_gates() -> None:
    op.create_table(
        "r21_approval_gates",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("gate_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("gate_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_approval_gates", "execution_id", "gate_id", "status")


def _approval_decisions() -> None:
    op.create_table(
        "r21_approval_decisions",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("gate_id", sa.String(length=200), nullable=False),
        sa.Column("decision_id", sa.String(length=200), nullable=False),
        sa.Column("actor_role", sa.String(length=120), nullable=False),
        sa.Column("decision_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_approval_decisions", "execution_id", "gate_id", "actor_role")


def _events() -> None:
    op.create_table(
        "r21_execution_events",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("event_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("checksum", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_execution_events", "execution_id", "event_type", "project_key")


def _evidence() -> None:
    op.create_table(
        "r21_evidence_records",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=False),
        sa.Column("evidence_id", sa.String(length=200), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=200), nullable=False),
        sa.Column("evidence_type", sa.String(length=120), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    _indexes("r21_evidence_records", "execution_id", "entity_id", "evidence_type")


def _idempotency() -> None:
    op.create_table(
        "r21_idempotency_records",
        *_base_columns(),
        sa.Column("execution_id", sa.String(length=200), nullable=True),
        sa.Column("scope", sa.String(length=160), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "idempotency_key"),
    )
    _indexes("r21_idempotency_records", "project_key", "execution_id", "status")


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def _immutable(table_name: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_{table_name}_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{table_name} is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER prevent_{table_name}_mutation_trigger
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION prevent_{table_name}_mutation();
        """
    )
