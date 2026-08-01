"""add governed enterprise evolution platform

Revision ID: c42b87eaf956
Revises: c31a76d9e845
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c42b87eaf956"
down_revision: str | None = "c31a76d9e845"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable(table: str) -> None:
    name = f"prevent_{table}_mutation"
    op.execute(
        f"CREATE FUNCTION {name}() RETURNS trigger AS $$ BEGIN "
        f"RAISE EXCEPTION '{table} is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        f"CREATE TRIGGER {name}_trigger BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {name}()"
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "enterprise_improvements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("improvement_key", sa.String(240), nullable=False, unique=True),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("origin", sa.String(120), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("expected_benefit", sa.Text(), nullable=False),
        sa.Column("risk_document", jsonb, nullable=False),
        sa.Column("dependencies", postgresql.ARRAY(sa.String(240)), nullable=False),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("proposal_document", jsonb, nullable=False),
        sa.Column("proposal_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("proposed_by", sa.String(200), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "enterprise_evolution_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("improvement_id", sa.Uuid(), sa.ForeignKey("enterprise_improvements.id")),
        sa.Column("artifact_type", sa.String(60), nullable=False),
        sa.Column("artifact_key", sa.String(240), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("artifact_document", jsonb, nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column(
            "parent_artifact_id", sa.Uuid(), sa.ForeignKey("enterprise_evolution_artifacts.id")
        ),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("artifact_type", "artifact_key", "version"),
    )
    op.create_table(
        "enterprise_evolution_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("target_type", sa.String(60), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("board_role", sa.String(80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("target_type", "target_id", "target_hash", "decision"),
    )
    op.create_table(
        "enterprise_improvement_transitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "improvement_id", sa.Uuid(), sa.ForeignKey("enterprise_improvements.id"), nullable=False
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(30)),
        sa.Column("to_state", sa.String(30), nullable=False),
        sa.Column("evidence_artifact_ids", jsonb, nullable=False),
        sa.Column("evidence_set_hash", sa.String(64), nullable=False),
        sa.Column("decision_id", sa.Uuid(), sa.ForeignKey("enterprise_evolution_decisions.id")),
        sa.Column("transitioned_by", sa.String(200), nullable=False),
        sa.Column("transitioned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("improvement_id", "sequence"),
    )
    for table in (
        "enterprise_improvements",
        "enterprise_evolution_artifacts",
        "enterprise_evolution_decisions",
        "enterprise_improvement_transitions",
    ):
        _immutable(table)


def downgrade() -> None:
    tables = (
        "enterprise_improvements",
        "enterprise_evolution_artifacts",
        "enterprise_evolution_decisions",
        "enterprise_improvement_transitions",
    )
    for table in reversed(tables):
        name = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER {name}_trigger ON {table}")
        op.execute(f"DROP FUNCTION {name}()")
    for table in reversed(tables):
        op.drop_table(table)
