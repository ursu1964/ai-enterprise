"""add P9 extended resilience governance

Revision ID: f39c2a71d804
Revises: e25a83bc1904
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.resilience import extended_models  # noqa: F401

revision: str = "f39c2a71d804"
down_revision: str | None = "e25a83bc1904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "resilience_regions",
    "region_ownership_leases",
    "data_residency_policies",
    "sovereign_execution_zones",
    "governed_model_providers",
    "governed_model_definitions",
    "model_substitution_events",
    "cryptographic_profiles",
    "cryptographic_key_versions",
    "signature_records",
    "authority_succession_plans",
    "emergency_authority_grants",
    "institutional_runbooks",
    "institutional_rehearsals",
    "vendor_exit_plans",
    "technology_substitution_records",
    "resilience_experiments",
    "artifact_migration_records",
    "archive_verification_runs",
    "crisis_mode_activations",
    "institutional_governance_records",
)


def upgrade() -> None:
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=False)
