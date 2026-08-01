"""add production foundation

Revision ID: e25a83bc1904
Revises: d14f62a90c71
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database import foundation_models  # noqa: F401
from ai_enterprise.infrastructure.database.models import Base

revision: str = "e25a83bc1904"
down_revision: str | None = "d14f62a90c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "actor_identities",
    "authority_grants",
    "transactional_outbox",
    "audit_chain_records",
    "artifact_versions",
    "external_effect_ledger",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind)
