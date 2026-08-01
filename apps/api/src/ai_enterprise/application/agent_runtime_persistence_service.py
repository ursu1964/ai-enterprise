import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentRuntimeSessionModel,
    AgentRuntimeSpecificationModel,
    ModelDeploymentModel,
    SkillModel,
    SkillVersionModel,
    ToolDefinitionModel,
)
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.organization.models import AgentAssignmentModel


class AgentRuntimePersistenceError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


class AgentRuntimePersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _audit(
        self, event: str, actor: Actor, project_id: uuid.UUID | None, **payload: Any
    ) -> None:
        self.session.add(
            AuditEventModel(
                project_id=project_id,
                event_type=event,
                actor_type=actor.actor_type,
                actor_id=actor.subject,
                payload=payload,
            )
        )

    async def create_skill(
        self,
        organization_id: uuid.UUID,
        key: str,
        name: str,
        document: dict[str, Any],
        actor: Actor,
    ) -> SkillModel:
        if await self.session.scalar(
            select(SkillModel).where(
                SkillModel.organization_id == organization_id, SkillModel.skill_key == key
            )
        ):
            raise AgentRuntimePersistenceError("Skill key already exists")
        skill = SkillModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            skill_key=key,
            name=name,
            status="draft",
        )
        version = SkillVersionModel(
            id=uuid.uuid4(),
            skill_id=skill.id,
            version_number=1,
            skill_document=document,
            skill_hash=canonical_hash(document),
            approval_status="draft",
        )
        self.session.add_all((skill, version))
        self._audit(
            "SkillVersionCreated",
            actor,
            None,
            skill_id=str(skill.id),
            version_id=str(version.id),
            skill_hash=version.skill_hash,
        )
        await self.session.commit()
        return skill

    async def create_skill_version(
        self, skill: SkillModel, document: dict[str, Any], actor: Actor
    ) -> SkillVersionModel:
        number = (
            await self.session.scalar(
                select(func.max(SkillVersionModel.version_number)).where(
                    SkillVersionModel.skill_id == skill.id
                )
            )
            or 0
        )
        version = SkillVersionModel(
            id=uuid.uuid4(),
            skill_id=skill.id,
            version_number=number + 1,
            skill_document=document,
            skill_hash=canonical_hash(document),
            approval_status="draft",
        )
        self.session.add(version)
        self._audit(
            "SkillVersionCreated",
            actor,
            None,
            skill_id=str(skill.id),
            version_id=str(version.id),
            skill_hash=version.skill_hash,
        )
        await self.session.commit()
        return version

    async def approve_skill_version(
        self, version: SkillVersionModel, actor: Actor
    ) -> SkillVersionModel:
        if version.approval_status != "draft":
            raise AgentRuntimePersistenceError("Only draft skill versions may be approved")
        skill = await self.session.get(SkillModel, version.skill_id)
        if skill is None:
            raise AgentRuntimePersistenceError("Skill not found", 404)
        version.approval_status, skill.status, skill.current_version_id = (
            "approved",
            "active",
            version.id,
        )
        self._audit(
            "SkillVersionApproved",
            actor,
            None,
            skill_id=str(skill.id),
            version_id=str(version.id),
            skill_hash=version.skill_hash,
        )
        await self.session.commit()
        return version

    async def register_tool(
        self, key: str, version: str, document: dict[str, Any], actor: Actor
    ) -> ToolDefinitionModel:
        if actor.role not in {"platform-admin", "platform_administrator"}:
            raise AgentRuntimePersistenceError("Platform administrator role required", 403)
        if await self.session.get(ToolDefinitionModel, (key, version)):
            raise AgentRuntimePersistenceError("Tool version already registered")
        row = ToolDefinitionModel(
            tool_key=key,
            version=version,
            tool_document=document,
            tool_hash=canonical_hash(document),
            status="active",
        )
        self.session.add(row)
        self._audit(
            "ToolDefinitionRegistered",
            actor,
            None,
            tool_key=key,
            version=version,
            tool_hash=row.tool_hash,
        )
        await self.session.commit()
        return row

    async def register_deployment(
        self, values: dict[str, Any], actor: Actor
    ) -> ModelDeploymentModel:
        if actor.role not in {"platform-admin", "platform_administrator"}:
            raise AgentRuntimePersistenceError("Platform administrator role required", 403)
        row = ModelDeploymentModel(
            id=uuid.uuid4(), status="registered", health_document={}, **values
        )
        self.session.add(row)
        self._audit(
            "ModelDeploymentRegistered",
            actor,
            None,
            deployment_id=str(row.id),
            provider_key=row.provider_key,
            model_reference=row.model_reference,
        )
        await self.session.commit()
        return row

    async def start_session(self, values: dict[str, Any], actor: Actor) -> AgentRuntimeSessionModel:
        specification = await self.session.get(
            AgentRuntimeSpecificationModel, values["runtime_specification_id"]
        )
        assignment = await self.session.get(AgentAssignmentModel, values["assignment_id"])
        if specification is None or specification.status != "active":
            raise AgentRuntimePersistenceError("Active runtime specification required")
        if assignment is None or assignment.status != "active":
            raise AgentRuntimePersistenceError("Active assignment required")
        immutable_ids = (
            "agent_profile_id",
            "agent_profile_version_id",
            "assignment_id",
            "role_version_id",
        )
        if any(getattr(specification, name) != values[name] for name in immutable_ids):
            raise AgentRuntimePersistenceError("Runtime identity does not match specification", 403)
        if (
            assignment.scope_type != values["scope_type"]
            or assignment.scope_id != values["scope_id"]
        ):
            raise AgentRuntimePersistenceError("Runtime scope does not match assignment", 403)
        row = AgentRuntimeSessionModel(
            id=uuid.uuid4(),
            runtime_specification_hash=specification.configuration_hash,
            status="created",
            counters={},
            **values,
        )
        self.session.add(row)
        self._audit(
            "AgentRuntimeSessionCreated",
            actor,
            values["scope_id"] if values["scope_type"] == "project" else None,
            runtime_session_id=str(row.id),
            specification_hash=row.runtime_specification_hash,
        )
        await self.session.commit()
        return row

    async def cancel_session(
        self, row: AgentRuntimeSessionModel, actor: Actor
    ) -> AgentRuntimeSessionModel:
        if row.status in {"completed", "cancelled", "failed", "timed_out"}:
            raise AgentRuntimePersistenceError("Terminal runtime session cannot be cancelled")
        row.status, row.completed_at = "cancelled", datetime.now(UTC)
        self._audit(
            "AgentRuntimeSessionCancelled",
            actor,
            row.scope_id if row.scope_type == "project" else None,
            runtime_session_id=str(row.id),
        )
        await self.session.commit()
        return row
