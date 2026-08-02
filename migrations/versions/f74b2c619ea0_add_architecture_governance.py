"""add governed architecture persistence

Revision ID: f74b2c619ea0
Revises: e63a1d90b7f4
"""

from collections.abc import Sequence

import sqlalchemy as sa
from ai_enterprise.infrastructure.architecture import (
    models as architecture_models,  # noqa: F401
)
from ai_enterprise.infrastructure.database.models import Base
from alembic import op

revision: str = "f74b2c619ea0"
down_revision: str | None = "e63a1d90b7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "architecture_runs",
    "architecture_artifacts",
    "architecture_reviews",
    "architecture_review_findings",
    "architecture_revision_requests",
    "architecture_approvals",
)


def upgrade() -> None:
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in TABLES]
    Base.metadata.create_all(bind, tables=tables, checkfirst=False)
    op.create_index(
        "uq_architecture_active_run_project",
        "architecture_runs",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('ready', 'running')"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("uq_architecture_active_run_project", table_name="architecture_runs")
    tables = [Base.metadata.tables[name] for name in TABLES]
    Base.metadata.drop_all(bind, tables=tables, checkfirst=False)
