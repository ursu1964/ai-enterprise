"""add governed agent runtime

Revision ID: a92d41c70be3
Revises: d71e4a8c5f20
"""

from collections.abc import Sequence

from alembic import op

from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentEscalationModel,
    AgentOutputValidationModel,
    AgentRuntimeSessionModel,
    AgentRuntimeSpecificationModel,
    CapabilitySkillBindingModel,
    ContextManifestModel,
    ModelDeploymentModel,
    ModelInvocationModel,
    ModelRoutingPolicyModel,
    SkillModel,
    SkillVersionModel,
    ToolDefinitionModel,
    ToolInvocationModel,
)

revision: str = "a92d41c70be3"
down_revision: str | None = "d71e4a8c5f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    SkillModel,
    SkillVersionModel,
    CapabilitySkillBindingModel,
    ToolDefinitionModel,
    ModelDeploymentModel,
    ModelRoutingPolicyModel,
    AgentRuntimeSpecificationModel,
    AgentRuntimeSessionModel,
    ContextManifestModel,
    ToolInvocationModel,
    ModelInvocationModel,
    AgentOutputValidationModel,
    AgentEscalationModel,
)


def upgrade() -> None:
    bind = op.get_bind()
    for model in TABLES:
        model.__table__.create(bind, checkfirst=False)


def downgrade() -> None:
    bind = op.get_bind()
    for model in reversed(TABLES):
        model.__table__.drop(bind, checkfirst=False)
