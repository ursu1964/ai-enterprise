import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.application.audit.writer import AuditWriter
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


class OrganizationPersistenceError(ValueError):
    def __init__(self, detail: str, status_code: int = 409) -> None:
        super().__init__(detail)
        self.status_code = status_code


def canonical_hash(document: object) -> str:
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


class OrganizationPersistenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _audit(
        self,
        event_type: str,
        actor: Actor,
        correlation_id: uuid.UUID,
        organization_id: uuid.UUID | None,
        *,
        decision: str = "allowed",
        causation_id: uuid.UUID | None = None,
        **evidence: Any,
    ) -> None:
        profile_id = evidence.get("agent_profile_id")
        profile_version_id = evidence.get("profile_version_id")
        role_version_id = evidence.get("role_version_id")
        assignment_id = evidence.get("assignment_id")
        self.session.add(
            OrganizationalDecisionModel(
                id=uuid.uuid4(),
                organization_id=organization_id,
                event_type=event_type,
                actor_principal=actor.subject,
                agent_profile_id=profile_id,
                profile_version_id=profile_version_id,
                role_version_id=role_version_id,
                assignment_id=assignment_id,
                capability=evidence.get("capability"),
                scope_type=evidence.get("scope_type"),
                scope_id=evidence.get("scope_id"),
                decision=decision,
                policy_versions=evidence.get("policy_versions", {}),
                configuration_hashes=evidence.get("configuration_hashes", []),
                correlation_id=correlation_id,
                causation_id=causation_id,
                evidence=evidence,
            )
        )
        project_id = evidence.get("project_id")
        await AuditWriter(self.session).append_event(
            stream_id=(
                f"project:{project_id}"
                if isinstance(project_id, uuid.UUID)
                else f"organization:{organization_id}"
                if organization_id is not None
                else "organization:platform"
            ),
            project_id=project_id if isinstance(project_id, uuid.UUID) else None,
            event_type=event_type,
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            payload={
                "organization_id": str(organization_id) if organization_id else None,
                "correlation_id": str(correlation_id),
                "decision": decision,
            },
        )

    async def create_organization(
        self, key: str, name: str, policy_set_id: uuid.UUID, actor: Actor, correlation_id: uuid.UUID
    ) -> OrganizationModel:
        if await self.session.scalar(
            select(OrganizationModel).where(OrganizationModel.organization_key == key)
        ):
            raise OrganizationPersistenceError("Organization key already exists")
        row = OrganizationModel(
            id=uuid.uuid4(),
            organization_key=key,
            name=name,
            status="draft",
            policy_set_id=policy_set_id,
            version=0,
        )
        self.session.add(row)
        await self._audit("OrganizationCreated", actor, correlation_id, row.id)
        await self.session.commit()
        return row

    async def activate_organization(
        self,
        row: OrganizationModel,
        expected_version: int | None,
        actor: Actor,
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None,
    ) -> OrganizationModel:
        if expected_version is not None and row.version != expected_version:
            raise OrganizationPersistenceError("Organization version conflict")
        if row.status not in {"draft", "suspended"}:
            raise OrganizationPersistenceError(
                "Organization cannot be activated from current status"
            )
        row.status, row.version = "active", row.version + 1
        await self._audit(
            "OrganizationActivated", actor, correlation_id, row.id, causation_id=causation_id
        )
        await self.session.commit()
        return row

    async def create_unit(
        self,
        organization_id: uuid.UUID,
        values: dict[str, Any],
        actor: Actor,
        correlation_id: uuid.UUID,
        causation_id: uuid.UUID | None,
    ) -> OrganizationalUnitModel:
        org = await self.session.get(OrganizationModel, organization_id)
        if org is None:
            raise OrganizationPersistenceError("Organization not found", 404)
        parent_id = values.get("parent_unit_id")
        if parent_id is not None:
            parent = await self.session.get(OrganizationalUnitModel, parent_id)
            if parent is None or parent.organization_id != organization_id:
                raise OrganizationPersistenceError("Parent unit is outside organization")
        row = OrganizationalUnitModel(
            id=uuid.uuid4(), organization_id=organization_id, status="active", **values
        )
        self.session.add(row)
        await self._audit(
            "OrganizationalUnitCreated",
            actor,
            correlation_id,
            organization_id,
            causation_id=causation_id,
            unit_id=str(row.id),
        )
        await self.session.commit()
        return row

    async def create_role(
        self,
        organization_id: uuid.UUID,
        role_key: str,
        name: str,
        document: dict[str, Any],
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> RoleModel:
        if await self.session.get(OrganizationModel, organization_id) is None:
            raise OrganizationPersistenceError("Organization not found", 404)
        role = RoleModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            role_key=role_key,
            name=name,
            status="draft",
        )
        version = RoleVersionModel(
            id=uuid.uuid4(),
            role_id=role.id,
            version_number=1,
            role_document=document,
            role_hash=canonical_hash(document),
            status="draft",
        )
        self.session.add_all((role, version))
        await self._audit(
            "RoleVersionCreated",
            actor,
            correlation_id,
            organization_id,
            role_version_id=version.id,
            role_hash=version.role_hash,
        )
        await self.session.commit()
        return role

    async def create_role_version(
        self, role: RoleModel, document: dict[str, Any], actor: Actor, correlation_id: uuid.UUID
    ) -> RoleVersionModel:
        versions = list(
            (
                await self.session.scalars(
                    select(RoleVersionModel).where(RoleVersionModel.role_id == role.id)
                )
            ).all()
        )
        row = RoleVersionModel(
            id=uuid.uuid4(),
            role_id=role.id,
            version_number=max((v.version_number for v in versions), default=0) + 1,
            role_document=document,
            role_hash=canonical_hash(document),
            status="draft",
        )
        self.session.add(row)
        await self._audit(
            "RoleVersionCreated",
            actor,
            correlation_id,
            role.organization_id,
            role_version_id=row.id,
            role_hash=row.role_hash,
        )
        await self.session.commit()
        return row

    async def activate_role_version(
        self, version: RoleVersionModel, actor: Actor, correlation_id: uuid.UUID
    ) -> RoleVersionModel:
        role = await self.session.get(RoleModel, version.role_id)
        if role is None:
            raise OrganizationPersistenceError("Role not found", 404)
        if version.status != "draft":
            raise OrganizationPersistenceError("Only draft role versions can be activated")
        version.status, role.status, role.current_version_id = "active", "active", version.id
        await self._audit(
            "RoleVersionActivated",
            actor,
            correlation_id,
            role.organization_id,
            role_version_id=version.id,
            role_hash=version.role_hash,
        )
        await self.session.commit()
        return version

    async def create_agent(
        self,
        organization_id: uuid.UUID,
        home_unit_id: uuid.UUID,
        agent_key: str,
        display_name: str,
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> AgentProfileModel:
        unit = await self.session.get(OrganizationalUnitModel, home_unit_id)
        if unit is None or unit.organization_id != organization_id:
            raise OrganizationPersistenceError("Home unit is outside organization")
        row = AgentProfileModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            home_unit_id=home_unit_id,
            agent_key=agent_key,
            display_name=display_name,
            status="draft",
            state_version=0,
        )
        self.session.add(row)
        await self._audit(
            "AgentProfileCreated", actor, correlation_id, organization_id, agent_profile_id=row.id
        )
        await self.session.commit()
        return row

    async def create_agent_version(
        self,
        profile: AgentProfileModel,
        document: dict[str, Any],
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> AgentProfileVersionModel:
        versions = list(
            (
                await self.session.scalars(
                    select(AgentProfileVersionModel).where(
                        AgentProfileVersionModel.agent_profile_id == profile.id
                    )
                )
            ).all()
        )
        row = AgentProfileVersionModel(
            id=uuid.uuid4(),
            agent_profile_id=profile.id,
            version_number=max((v.version_number for v in versions), default=0) + 1,
            configuration_document=document,
            configuration_hash=canonical_hash(document),
            approval_status="pending",
        )
        self.session.add(row)
        await self._audit(
            "AgentProfileVersionCreated",
            actor,
            correlation_id,
            profile.organization_id,
            agent_profile_id=profile.id,
            profile_version_id=row.id,
            configuration_hashes=[row.configuration_hash],
        )
        await self.session.commit()
        return row

    async def approve_agent_version(
        self, version: AgentProfileVersionModel, actor: Actor, correlation_id: uuid.UUID
    ) -> AgentProfileVersionModel:
        if actor.actor_type != "human":
            raise OrganizationPersistenceError("Agent profile approval is human-only", 403)
        if version.approval_status != "pending":
            raise OrganizationPersistenceError("Agent profile version is not pending")
        profile = await self.session.get(AgentProfileModel, version.agent_profile_id)
        assert profile is not None
        version.approval_status = "approved"
        await self._audit(
            "AgentProfileVersionApproved",
            actor,
            correlation_id,
            profile.organization_id,
            agent_profile_id=profile.id,
            profile_version_id=version.id,
            configuration_hashes=[version.configuration_hash],
        )
        await self.session.commit()
        return version

    async def transition_agent(
        self,
        profile: AgentProfileModel,
        target: str,
        actor: Actor,
        correlation_id: uuid.UUID,
        reason: str | None,
    ) -> AgentProfileModel:
        if target == "active":
            version = (
                await self.session.get(AgentProfileVersionModel, profile.current_version_id)
                if profile.current_version_id
                else await self.session.scalar(
                    select(AgentProfileVersionModel)
                    .where(
                        AgentProfileVersionModel.agent_profile_id == profile.id,
                        AgentProfileVersionModel.approval_status == "approved",
                    )
                    .order_by(AgentProfileVersionModel.version_number.desc())
                )
            )
            if version is None:
                raise OrganizationPersistenceError("An approved profile version is required")
            profile.current_version_id = version.id
            event = "AgentProfileActivated"
        else:
            event = "AgentProfileSuspended"
        profile.status, profile.state_version = target, profile.state_version + 1
        await self._audit(
            event,
            actor,
            correlation_id,
            profile.organization_id,
            agent_profile_id=profile.id,
            profile_version_id=profile.current_version_id,
            reason=reason,
        )
        await self.session.commit()
        return profile

    async def create_assignment(
        self,
        profile: AgentProfileModel,
        values: dict[str, Any],
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> AgentAssignmentModel:
        version = await self.session.get(
            AgentProfileVersionModel, values["agent_profile_version_id"]
        )
        role_version = await self.session.get(RoleVersionModel, values["role_version_id"])
        if version is None or version.agent_profile_id != profile.id:
            raise OrganizationPersistenceError("Profile version does not belong to agent")
        if role_version is None:
            raise OrganizationPersistenceError("Role version not found", 404)
        document = {
            **values["assignment_document"],
            "profile_version": str(version.id),
            "role_version": str(role_version.id),
            "scope_type": values["scope_type"],
            "scope_id": str(values["scope_id"]),
            "granted_capabilities": sorted(values["granted_capabilities"]),
            "denied_capabilities": sorted(values["denied_capabilities"]),
        }
        row = AgentAssignmentModel(
            id=uuid.uuid4(),
            organization_id=profile.organization_id,
            agent_profile_id=profile.id,
            status="draft",
            assigned_by=uuid.uuid5(uuid.NAMESPACE_URL, actor.subject),
            assignment_document=document,
            assignment_hash=canonical_hash(document),
            **{k: v for k, v in values.items() if k != "assignment_document"},
        )
        self.session.add(row)
        await self._audit(
            "AgentAssignmentCreated",
            actor,
            correlation_id,
            profile.organization_id,
            agent_profile_id=profile.id,
            profile_version_id=version.id,
            role_version_id=role_version.id,
            assignment_id=row.id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
        )
        await self.session.commit()
        return row

    async def transition_assignment(
        self, row: AgentAssignmentModel, target: str, actor: Actor, correlation_id: uuid.UUID
    ) -> AgentAssignmentModel:
        if target == "active":
            profile = await self.session.get(AgentProfileModel, row.agent_profile_id)
            version = await self.session.get(AgentProfileVersionModel, row.agent_profile_version_id)
            role = await self.session.scalar(
                select(RoleModel)
                .join(RoleVersionModel, RoleVersionModel.role_id == RoleModel.id)
                .where(RoleVersionModel.id == row.role_version_id)
            )
            if (
                profile is None
                or profile.status != "active"
                or version is None
                or version.approval_status != "approved"
                or role is None
                or role.status != "active"
            ):
                raise OrganizationPersistenceError(
                    "Active agent, approved profile version, and active role are required"
                )
            event = "AgentAssignmentActivated"
        else:
            event = "AgentAssignmentRevoked"
        row.status = target
        await self._audit(
            event,
            actor,
            correlation_id,
            row.organization_id,
            agent_profile_id=row.agent_profile_id,
            profile_version_id=row.agent_profile_version_id,
            role_version_id=row.role_version_id,
            assignment_id=row.id,
            scope_type=row.scope_type,
            scope_id=row.scope_id,
        )
        await self.session.commit()
        return row

    async def evaluate(
        self,
        actor_id: uuid.UUID,
        capability: str,
        scope_type: str,
        scope_id: uuid.UUID,
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        assignments = list(
            (
                await self.session.scalars(
                    select(AgentAssignmentModel)
                    .join(AgentProfileModel)
                    .join(
                        AgentProfileVersionModel,
                        AgentProfileVersionModel.id
                        == AgentAssignmentModel.agent_profile_version_id,
                    )
                    .join(
                        RoleVersionModel,
                        RoleVersionModel.id == AgentAssignmentModel.role_version_id,
                    )
                    .where(
                        AgentAssignmentModel.agent_profile_id == actor_id,
                        AgentAssignmentModel.status == "active",
                        AgentProfileModel.status == "active",
                        AgentProfileVersionModel.approval_status == "approved",
                        RoleVersionModel.status == "active",
                        AgentAssignmentModel.scope_type == scope_type,
                        AgentAssignmentModel.scope_id == scope_id,
                        AgentAssignmentModel.valid_from <= now,
                        or_(
                            AgentAssignmentModel.valid_until.is_(None),
                            AgentAssignmentModel.valid_until > now,
                        ),
                    )
                    .order_by(AgentAssignmentModel.created_at, AgentAssignmentModel.id)
                )
            ).all()
        )
        allowed_row = next(
            (
                row
                for row in assignments
                if capability in row.granted_capabilities
                and capability not in row.denied_capabilities
            ),
            None,
        )
        human_only = await self.session.get(CapabilityModel, capability)
        reasons: list[dict[str, str]] = []
        if human_only is not None and human_only.human_only:
            allowed_row = None
            reasons.append({"code": "AUTH-005", "message": "Capability is human-only"})
        elif not assignments:
            reasons.append(
                {"code": "AUTH-001", "message": "No active assignment covers this scope"}
            )
        elif allowed_row is None:
            reasons.append(
                {"code": "AUTH-002", "message": "Capability is not granted or is explicitly denied"}
            )
        organization_id = assignments[0].organization_id if assignments else None
        await self._audit(
            "AuthorityEvaluated" if allowed_row else "AuthorityDenied",
            actor,
            correlation_id,
            organization_id,
            decision="allowed" if allowed_row else "denied",
            agent_profile_id=actor_id,
            profile_version_id=allowed_row.agent_profile_version_id if allowed_row else None,
            role_version_id=allowed_row.role_version_id if allowed_row else None,
            assignment_id=allowed_row.id if allowed_row else None,
            capability=capability,
            scope_type=scope_type,
            scope_id=scope_id,
            reasons=reasons,
        )
        await self.session.commit()
        return {
            "allowed": allowed_row is not None,
            "decision": "allow" if allowed_row else "deny",
            "reasons": reasons,
            "assignment_id": allowed_row.id if allowed_row else None,
            "agent_profile_version_id": allowed_row.agent_profile_version_id
            if allowed_row
            else None,
            "role_version_id": allowed_row.role_version_id if allowed_row else None,
        }

    async def compose_crew(
        self,
        workflow_type: str,
        project_id: uuid.UUID,
        artifact_id: uuid.UUID,
        policy_version: str,
        organization_id: uuid.UUID | None,
        actor: Actor,
        correlation_id: uuid.UUID,
    ) -> CrewManifestModel:
        if organization_id is None:
            organization_id = await self.session.scalar(
                select(OrganizationModel.id)
                .where(OrganizationModel.status == "active")
                .order_by(OrganizationModel.organization_key)
            )
        if organization_id is None:
            raise OrganizationPersistenceError("No active organization", 422)
        now = datetime.now(UTC)
        rows = list(
            (
                await self.session.execute(
                    select(
                        AgentAssignmentModel,
                        AgentProfileModel,
                        AgentProfileVersionModel,
                        RoleVersionModel,
                        RoleModel,
                    )
                    .join(
                        AgentProfileModel,
                        AgentProfileModel.id == AgentAssignmentModel.agent_profile_id,
                    )
                    .join(
                        AgentProfileVersionModel,
                        AgentProfileVersionModel.id
                        == AgentAssignmentModel.agent_profile_version_id,
                    )
                    .join(
                        RoleVersionModel,
                        RoleVersionModel.id == AgentAssignmentModel.role_version_id,
                    )
                    .join(RoleModel, RoleModel.id == RoleVersionModel.role_id)
                    .where(
                        AgentAssignmentModel.organization_id == organization_id,
                        AgentAssignmentModel.status == "active",
                        AgentProfileModel.status == "active",
                        AgentProfileVersionModel.approval_status == "approved",
                        RoleVersionModel.status == "active",
                        AgentAssignmentModel.valid_from <= now,
                        or_(
                            AgentAssignmentModel.valid_until.is_(None),
                            AgentAssignmentModel.valid_until > now,
                        ),
                    )
                    .order_by(
                        RoleModel.role_key,
                        AgentProfileModel.agent_key,
                        AgentAssignmentModel.created_at,
                        AgentAssignmentModel.id,
                    )
                )
            ).all()
        )
        required = {
            "architecture-analysis": {"system-architect", "architecture-reviewer"},
            "requirements-analysis": {"requirements-analyst", "requirements-reviewer"},
            "work-package-decomposition": {"work-package-planner"},
            "implementation": {"implementation-engineer"},
        }.get(workflow_type, set())
        selected: list[dict[str, Any]] = []
        for assignment, profile, version, role_version, role in rows:
            if required and role.role_key not in required:
                continue
            if any(item["role_key"] == role.role_key for item in selected):
                continue
            selected.append(
                {
                    "agent_profile_id": str(profile.id),
                    "agent_profile_version_id": str(version.id),
                    "assignment_id": str(assignment.id),
                    "role_version_id": str(role_version.id),
                    "role_key": role.role_key,
                    "configuration_hash": version.configuration_hash,
                    "assignment_hash": assignment.assignment_hash,
                    "tool_permissions": version.configuration_document.get("tool_permissions", []),
                    "knowledge_policy": version.configuration_document.get("knowledge_policy"),
                    "model_policy": version.configuration_document.get("model_policy"),
                }
            )
        missing = sorted(required - {item["role_key"] for item in selected})
        if missing:
            await self._audit(
                "CrewCompositionRejected",
                actor,
                correlation_id,
                organization_id,
                decision="denied",
                project_id=project_id,
                missing_roles=missing,
                policy_versions={"crew": policy_version},
            )
            await self.session.commit()
            raise OrganizationPersistenceError(
                f"Missing eligible crew roles: {', '.join(missing)}", 422
            )
        document = {
            "workflow_type": workflow_type,
            "project_id": str(project_id),
            "artifact_id": str(artifact_id),
            "organization_id": str(organization_id),
            "policy_version": policy_version,
            "members": selected,
        }
        row = CrewManifestModel(
            id=uuid.uuid4(),
            organization_id=organization_id,
            workflow_type=workflow_type,
            project_id=project_id,
            artifact_id=artifact_id,
            policy_version=policy_version,
            manifest_document=document,
            manifest_hash=canonical_hash(document),
        )
        self.session.add(row)
        await self._audit(
            "CrewComposed",
            actor,
            correlation_id,
            organization_id,
            project_id=project_id,
            policy_versions={"crew": policy_version},
            configuration_hashes=[item["configuration_hash"] for item in selected],
            manifest_hash=row.manifest_hash,
        )
        await self.session.commit()
        return row
