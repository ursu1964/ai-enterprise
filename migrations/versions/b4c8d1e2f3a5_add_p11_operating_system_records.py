"""add P11 operating system records

Revision ID: b4c8d1e2f3a5
Revises: a3b7c9d0e2f4
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.enterprise_kernel import (
    models as enterprise_kernel_models,  # noqa: F401
)

revision: str = "b4c8d1e2f3a5"
down_revision: str | None = "a3b7c9d0e2f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "enterprise_modules",
    "organizational_threads",
    "operating_maturity_snapshots",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=False)
