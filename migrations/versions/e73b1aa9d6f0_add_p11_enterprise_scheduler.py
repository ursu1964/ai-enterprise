"""add P11 enterprise scheduler

Revision ID: e73b1aa9d6f0
Revises: e58b6f21c9a4
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.enterprise_kernel import (
    models as enterprise_kernel_models,  # noqa: F401
)

revision: str = "e73b1aa9d6f0"
down_revision: str | None = "e58b6f21c9a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.tables["enterprise_schedules"].create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    Base.metadata.tables["enterprise_schedules"].drop(bind=op.get_bind(), checkfirst=False)
