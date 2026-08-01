"""add governed federated ecosystem

Revision ID: c51da90bc178
Revises: c43c98fb0a67
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c51da90bc178"
down_revision: str | None = "c43c98fb0a67"
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
    op.create_table(
        "ecosystem_entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("entity_key", sa.String(240), nullable=False),
        sa.Column("display_name", sa.String(240), nullable=False),
        sa.Column("entity_document", jsonb, nullable=False),
        sa.Column("entity_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "entity_type", "entity_key"),
        sa.CheckConstraint(
            "entity_type IN ('partner','supplier','customer','cloud_provider',"
            "'identity_provider','open_source_project','regulator',"
            "'certification_body','external_service')"
        ),
    )
    op.create_table(
        "ecosystem_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("entity_id", sa.Uuid(), sa.ForeignKey("ecosystem_entities.id"), nullable=False),
        sa.Column("asset_type", sa.String(60), nullable=False),
        sa.Column("asset_key", sa.String(240), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("asset_document", jsonb, nullable=False),
        sa.Column("asset_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("evidence_manifest", jsonb, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("parent_asset_id", sa.Uuid(), sa.ForeignKey("ecosystem_assets.id")),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "asset_type", "asset_key", "version"),
        sa.CheckConstraint(
            "asset_type IN ('connector','external_contract','federation_agreement',"
            "'trust_assessment','identity_mapping','capability_offer','dependency',"
            "'vendor_risk','data_exchange','regulatory_policy','cloud_binding',"
            "'event_binding','federation_protocol','connector_health','contract_drift')"
        ),
    )
    op.create_table(
        "ecosystem_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("asset_id", sa.Uuid(), sa.ForeignKey("ecosystem_assets.id"), nullable=False),
        sa.Column("asset_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("board_role", sa.String(80), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("asset_id", "asset_hash", "decision"),
        sa.CheckConstraint("decision IN ('approve','reject')"),
    )
    op.create_table(
        "ecosystem_gateway_invocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "connector_asset_id", sa.Uuid(), sa.ForeignKey("ecosystem_assets.id"), nullable=False
        ),
        sa.Column(
            "contract_asset_id", sa.Uuid(), sa.ForeignKey("ecosystem_assets.id"), nullable=False
        ),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(160), nullable=False),
        sa.Column("identity_reference", sa.String(240), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64)),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("evidence_document", jsonb, nullable=False),
        sa.Column("invocation_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "direction IN ('inbound','outbound') AND status IN "
            "('authorized','denied','completed','failed')"
        ),
    )
    op.create_table(
        "ecosystem_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column(
            "source_entity_id", sa.Uuid(), sa.ForeignKey("ecosystem_entities.id"), nullable=False
        ),
        sa.Column(
            "target_entity_id", sa.Uuid(), sa.ForeignKey("ecosystem_entities.id"), nullable=False
        ),
        sa.Column("relationship", sa.String(60), nullable=False),
        sa.Column("edge_document", jsonb, nullable=False),
        sa.Column("edge_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_entity_id", "target_entity_id", "relationship"),
        sa.CheckConstraint("source_entity_id <> target_entity_id"),
        sa.CheckConstraint(
            "relationship IN ('consumes','provides','certifies','regulates',"
            "'supplies','collaborates','federates_with','trusts')"
        ),
    )
    for table in (
        "ecosystem_entities",
        "ecosystem_assets",
        "ecosystem_approvals",
        "ecosystem_gateway_invocations",
        "ecosystem_edges",
    ):
        _immutable(table)


def downgrade() -> None:
    tables = (
        "ecosystem_entities",
        "ecosystem_assets",
        "ecosystem_approvals",
        "ecosystem_gateway_invocations",
        "ecosystem_edges",
    )
    for table in reversed(tables):
        name = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER {name}_trigger ON {table}")
        op.execute(f"DROP FUNCTION {name}()")
    for table in reversed(tables):
        op.drop_table(table)
