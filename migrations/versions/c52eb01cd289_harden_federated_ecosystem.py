"""harden federated ecosystem boundaries

Revision ID: c52eb01cd289
Revises: c51da90bc178
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c52eb01cd289"
down_revision: str | None = "c51da90bc178"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ecosystem_approvals_asset_id_asset_hash_decision_key",
        "ecosystem_approvals",
        type_="unique",
    )
    op.add_column(
        "ecosystem_gateway_invocations",
        sa.Column("request_nonce", sa.Uuid(), nullable=True),
    )
    op.execute(
        "ALTER TABLE ecosystem_gateway_invocations "
        "DISABLE TRIGGER prevent_ecosystem_gateway_invocations_mutation_trigger"
    )
    op.execute("UPDATE ecosystem_gateway_invocations SET request_nonce = id")
    op.execute(
        "ALTER TABLE ecosystem_gateway_invocations "
        "ENABLE TRIGGER prevent_ecosystem_gateway_invocations_mutation_trigger"
    )
    op.alter_column("ecosystem_gateway_invocations", "request_nonce", nullable=False)

    op.create_unique_constraint(
        "uq_ecosystem_entities_org_id", "ecosystem_entities", ["organization_id", "id"]
    )
    op.create_unique_constraint(
        "uq_ecosystem_assets_org_id", "ecosystem_assets", ["organization_id", "id"]
    )
    op.create_foreign_key(
        "fk_ecosystem_assets_entity_org",
        "ecosystem_assets",
        "ecosystem_entities",
        ["organization_id", "entity_id"],
        ["organization_id", "id"],
    )
    op.create_foreign_key(
        "fk_ecosystem_approvals_asset_org",
        "ecosystem_approvals",
        "ecosystem_assets",
        ["organization_id", "asset_id"],
        ["organization_id", "id"],
    )
    for column in ("connector_asset_id", "contract_asset_id"):
        op.create_foreign_key(
            f"fk_ecosystem_invocations_{column}_org",
            "ecosystem_gateway_invocations",
            "ecosystem_assets",
            ["organization_id", column],
            ["organization_id", "id"],
        )
    for column in ("source_entity_id", "target_entity_id"):
        op.create_foreign_key(
            f"fk_ecosystem_edges_{column}_org",
            "ecosystem_edges",
            "ecosystem_entities",
            ["organization_id", column],
            ["organization_id", "id"],
        )
    op.create_unique_constraint(
        "uq_ecosystem_invocation_nonce",
        "ecosystem_gateway_invocations",
        ["organization_id", "connector_asset_id", "request_nonce"],
    )
    op.create_check_constraint(
        "ck_ecosystem_approval_expiry",
        "ecosystem_approvals",
        "(decision = 'approve' AND expires_at > decided_at) OR decision = 'reject'",
    )
    for table, columns in {
        "ecosystem_entities": ("entity_hash",),
        "ecosystem_assets": ("asset_hash", "evidence_hash"),
        "ecosystem_approvals": ("asset_hash",),
        "ecosystem_gateway_invocations": ("request_hash", "response_hash", "invocation_hash"),
        "ecosystem_edges": ("edge_hash",),
    }.items():
        for column in columns:
            op.create_check_constraint(
                f"ck_{table}_{column}_sha256",
                table,
                f"{column} IS NULL OR {column} ~ '^[0-9a-f]{{64}}$'",
            )


def downgrade() -> None:
    for table, columns in {
        "ecosystem_entities": ("entity_hash",),
        "ecosystem_assets": ("asset_hash", "evidence_hash"),
        "ecosystem_approvals": ("asset_hash",),
        "ecosystem_gateway_invocations": ("request_hash", "response_hash", "invocation_hash"),
        "ecosystem_edges": ("edge_hash",),
    }.items():
        for column in columns:
            op.drop_constraint(f"ck_{table}_{column}_sha256", table, type_="check")
    op.drop_constraint("ck_ecosystem_approval_expiry", "ecosystem_approvals", type_="check")
    op.drop_constraint(
        "uq_ecosystem_invocation_nonce", "ecosystem_gateway_invocations", type_="unique"
    )
    for column in ("source_entity_id", "target_entity_id"):
        op.drop_constraint(
            f"fk_ecosystem_edges_{column}_org", "ecosystem_edges", type_="foreignkey"
        )
    for column in ("connector_asset_id", "contract_asset_id"):
        op.drop_constraint(
            f"fk_ecosystem_invocations_{column}_org",
            "ecosystem_gateway_invocations",
            type_="foreignkey",
        )
    op.drop_constraint(
        "fk_ecosystem_approvals_asset_org", "ecosystem_approvals", type_="foreignkey"
    )
    op.drop_constraint("fk_ecosystem_assets_entity_org", "ecosystem_assets", type_="foreignkey")
    op.drop_constraint("uq_ecosystem_assets_org_id", "ecosystem_assets", type_="unique")
    op.drop_constraint("uq_ecosystem_entities_org_id", "ecosystem_entities", type_="unique")
    op.drop_column("ecosystem_gateway_invocations", "request_nonce")
    op.create_unique_constraint(
        "ecosystem_approvals_asset_id_asset_hash_decision_key",
        "ecosystem_approvals",
        ["asset_id", "asset_hash", "decision"],
    )
