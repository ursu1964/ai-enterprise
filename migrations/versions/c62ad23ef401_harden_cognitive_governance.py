"""harden cognitive governance

Revision ID: c62ad23ef401
Revises: c61fc12de390
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c62ad23ef401"
down_revision: str | None = "c61fc12de390"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _trigger(table: str, enabled: bool) -> None:
    action = "ENABLE" if enabled else "DISABLE"
    op.execute(f"ALTER TABLE {table} {action} TRIGGER prevent_{table}_mutation_trigger")


def upgrade() -> None:
    op.add_column("cognitive_records", sa.Column("classification", sa.String(30)))
    _trigger("cognitive_records", False)
    op.execute("UPDATE cognitive_records SET classification = 'internal'")
    _trigger("cognitive_records", True)
    op.alter_column("cognitive_records", "classification", nullable=False)
    op.create_check_constraint(
        "ck_cognitive_records_classification",
        "cognitive_records",
        "classification IN ('public','internal','confidential','restricted')",
    )
    op.add_column("cognitive_decisions", sa.Column("decision_nonce", sa.Uuid()))
    _trigger("cognitive_decisions", False)
    op.execute("UPDATE cognitive_decisions SET decision_nonce = id")
    _trigger("cognitive_decisions", True)
    op.alter_column("cognitive_decisions", "decision_nonce", nullable=False)
    op.create_unique_constraint(
        "uq_cognitive_decision_nonce",
        "cognitive_decisions",
        ["organization_id", "record_id", "decision_nonce"],
    )
    op.create_unique_constraint(
        "uq_cognitive_records_org_id_hash",
        "cognitive_records",
        ["organization_id", "id", "record_hash"],
    )
    op.create_foreign_key(
        "fk_cognitive_decision_exact_record",
        "cognitive_decisions",
        "cognitive_records",
        ["organization_id", "record_id", "record_hash"],
        ["organization_id", "id", "record_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_cognitive_decision_exact_record", "cognitive_decisions", type_="foreignkey"
    )
    op.drop_constraint("uq_cognitive_records_org_id_hash", "cognitive_records", type_="unique")
    op.drop_constraint("uq_cognitive_decision_nonce", "cognitive_decisions", type_="unique")
    op.drop_column("cognitive_decisions", "decision_nonce")
    op.drop_constraint("ck_cognitive_records_classification", "cognitive_records", type_="check")
    op.drop_column("cognitive_records", "classification")
