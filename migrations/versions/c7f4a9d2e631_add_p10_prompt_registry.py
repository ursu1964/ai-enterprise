"""add P10 prompt registry

Revision ID: c7f4a9d2e631
Revises: b4c8d1e2f3a5
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.agent_runtime import models as agent_runtime_models  # noqa: F401
from ai_enterprise.infrastructure.database.models import Base

revision: str = "c7f4a9d2e631"
down_revision: str | None = "b4c8d1e2f3a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("prompt_registries", "prompt_versions")


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=False)
