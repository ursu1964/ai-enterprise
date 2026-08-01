"""add architecture execution attempts

Revision ID: b18e70ac42d1
Revises: f74b2c619ea0
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.architecture.models import ArchitectureExecutionAttemptModel

revision: str = "b18e70ac42d1"
down_revision: str | None = "f74b2c619ea0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ArchitectureExecutionAttemptModel.__table__.create(op.get_bind(), checkfirst=False)


def downgrade() -> None:
    ArchitectureExecutionAttemptModel.__table__.drop(op.get_bind(), checkfirst=False)
