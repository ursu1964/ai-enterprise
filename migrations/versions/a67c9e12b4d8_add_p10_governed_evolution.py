"""add P10 governed evolution

Revision ID: a67c9e12b4d8
Revises: f39c2a71d804
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.evolution import models as evolution_models  # noqa: F401

revision: str = "a67c9e12b4d8"
down_revision: str | None = "f39c2a71d804"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "architecture_governance_records",
    "policy_evolution_records",
    "workflow_evolution_records",
    "agent_crew_evolution_records",
    "schema_evolution_records",
    "enterprise_experiment_records",
    "simulation_shadow_records",
    "transformation_rollout_records",
    "control_validation_records",
    "improvement_debt_records",
    "constitutional_governance_records",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=False)
