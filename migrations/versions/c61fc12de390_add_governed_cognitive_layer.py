"""add governed cognitive layer

Revision ID: c61fc12de390
Revises: c52eb01cd289
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c61fc12de390"
down_revision: str | None = "c52eb01cd289"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _immutable(table: str) -> None:
    name = f"prevent_{table}_mutation"
    op.execute(
        f"CREATE FUNCTION {name}() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION "
        f"'{table} is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        f"CREATE TRIGGER {name}_trigger BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {name}()"
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    types = (
        "'semantic_object','ontology','reasoning','executive_question','scenario',"
        "'simulation','digital_twin','cognitive_memory','synthesis','recommendation',"
        "'strategic_objective','dashboard_snapshot','cross_domain_reasoning',"
        "'strategic_memory','cognitive_policy','strategic_intelligence'"
    )
    op.create_table(
        "cognitive_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("record_type", sa.String(60), nullable=False),
        sa.Column("record_key", sa.String(240), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("record_document", jsonb, nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_manifest", jsonb, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4)),
        sa.Column("parent_record_id", sa.Uuid(), sa.ForeignKey("cognitive_records.id")),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "record_type", "record_key", "version"),
        sa.UniqueConstraint("organization_id", "id", name="uq_cognitive_records_org_id"),
        sa.CheckConstraint(f"record_type IN ({types})"),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$' AND evidence_hash ~ '^[0-9a-f]{64}$'"),
        sa.CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)"),
    )
    op.create_foreign_key(
        "fk_cognitive_parent_org",
        "cognitive_records",
        "cognitive_records",
        ["organization_id", "parent_record_id"],
        ["organization_id", "id"],
    )
    op.create_table(
        "cognitive_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("record_id", sa.Uuid(), sa.ForeignKey("cognitive_records.id"), nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('accept','reject','defer')"),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'"),
    )
    op.create_foreign_key(
        "fk_cognitive_decision_org",
        "cognitive_decisions",
        "cognitive_records",
        ["organization_id", "record_id"],
        ["organization_id", "id"],
    )
    op.create_table(
        "cognitive_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "source_record_id", sa.Uuid(), sa.ForeignKey("cognitive_records.id"), nullable=False
        ),
        sa.Column(
            "target_record_id", sa.Uuid(), sa.ForeignKey("cognitive_records.id"), nullable=False
        ),
        sa.Column("relationship", sa.String(60), nullable=False),
        sa.Column("link_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_record_id", "target_record_id", "relationship"),
        sa.CheckConstraint("source_record_id <> target_record_id"),
        sa.CheckConstraint(
            "relationship IN ('supports','derived_from','measures','affects',"
            "'contradicts','depends_on')"
        ),
        sa.CheckConstraint("link_hash ~ '^[0-9a-f]{64}$'"),
    )
    for column in ("source_record_id", "target_record_id"):
        op.create_foreign_key(
            f"fk_cognitive_links_{column}_org",
            "cognitive_links",
            "cognitive_records",
            ["organization_id", column],
            ["organization_id", "id"],
        )
    for table in ("cognitive_records", "cognitive_decisions", "cognitive_links"):
        _immutable(table)


def downgrade() -> None:
    for table in reversed(("cognitive_records", "cognitive_decisions", "cognitive_links")):
        name = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER {name}_trigger ON {table}")
        op.execute(f"DROP FUNCTION {name}()")
    op.drop_table("cognitive_links")
    op.drop_table("cognitive_decisions")
    op.drop_constraint("fk_cognitive_parent_org", "cognitive_records", type_="foreignkey")
    op.drop_table("cognitive_records")
