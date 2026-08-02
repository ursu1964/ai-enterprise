"""add workflow transition policy evidence

Revision ID: d8e9f0a1b2c3
Revises: c7f4a9d2e631
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d8e9f0a1b2c3"
down_revision: str | None = "c7f4a9d2e631"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workflow_transitions",
        sa.Column(
            "policy_evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.alter_column("workflow_transitions", "policy_evidence", server_default=None)


def downgrade() -> None:
    op.drop_column("workflow_transitions", "policy_evidence")
