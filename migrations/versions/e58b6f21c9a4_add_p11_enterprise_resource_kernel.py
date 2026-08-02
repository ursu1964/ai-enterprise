"""add P11 enterprise resource kernel

Revision ID: e58b6f21c9a4
Revises: c62ad23ef401
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.enterprise_kernel import (
    models as enterprise_kernel_models,  # noqa: F401
)

revision: str = "e58b6f21c9a4"
down_revision: str | None = "c62ad23ef401"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "enterprise_resources",
    "enterprise_resource_audit",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=False)
