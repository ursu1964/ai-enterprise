"""add organizational kernel

Revision ID: d71e4a8c5f20
Revises: c60f3e1a9b72
"""

from collections.abc import Sequence

from ai_enterprise.infrastructure.organization.models import (
    AgentAssignmentModel,
    AgentProfileModel,
    AgentProfileVersionModel,
    CapabilityModel,
    CrewManifestModel,
    OrganizationalDecisionModel,
    OrganizationalUnitModel,
    OrganizationModel,
    RoleModel,
    RoleVersionModel,
)
from alembic import op

revision: str = "d71e4a8c5f20"
down_revision: str | None = "c60f3e1a9b72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    OrganizationModel,
    OrganizationalUnitModel,
    RoleModel,
    RoleVersionModel,
    CapabilityModel,
    AgentProfileModel,
    AgentProfileVersionModel,
    AgentAssignmentModel,
    CrewManifestModel,
    OrganizationalDecisionModel,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=False)
