import uuid
from datetime import UTC, datetime

from ai_enterprise.application.enterprise_kernel.dto import (
    KernelActor,
    RegisterEnterpriseResource,
    ScheduleEnterpriseWork,
)
from ai_enterprise.application.enterprise_kernel.ports import (
    EnterpriseKernelAuditSink,
    EnterpriseResourceRepository,
)
from ai_enterprise.domain.enterprise_kernel.entities import (
    EnterpriseResource,
    EnterpriseResourceAuditRecord,
    EnterpriseResourceClaim,
    EnterpriseResourceEvidence,
    EnterpriseResourceRelation,
    EnterpriseSchedule,
)
from ai_enterprise.domain.enterprise_kernel.enums import (
    EnterpriseResourceState,
    EnterpriseScheduleState,
)
from ai_enterprise.domain.enterprise_kernel.exceptions import (
    EnterpriseResourceAlreadyExists,
    EnterpriseResourceNotFound,
    EnterpriseScheduleAlreadyExists,
    InvalidEnterpriseSchedule,
)
from ai_enterprise.domain.enterprise_kernel.policies import (
    EnterpriseSchedulingPolicy,
    ResourceRegistrationPolicy,
)
from ai_enterprise.domain.hashing import hash_json


class EnterpriseKernelService:
    def __init__(
        self,
        repository: EnterpriseResourceRepository,
        audit: EnterpriseKernelAuditSink,
    ) -> None:
        self._repository = repository
        self._audit = audit
        self._policy = ResourceRegistrationPolicy()
        self._scheduling = EnterpriseSchedulingPolicy()

    async def register_resource(
        self, request: RegisterEnterpriseResource, actor: KernelActor
    ) -> EnterpriseResource:
        existing = await self._repository.get_by_key(request.organization_id, request.resource_key)
        if existing is not None:
            raise EnterpriseResourceAlreadyExists(
                "Enterprise resource key is already registered for this organization"
            )
        now = datetime.now(UTC)
        material = request.model_dump(mode="json") | {
            "version": 1,
            "state": EnterpriseResourceState.REGISTERED,
            "registered_by": actor.subject,
            "registered_at": now.isoformat(),
        }
        resource = EnterpriseResource(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            resource_type=request.resource_type,
            resource_key=request.resource_key,
            display_name=request.display_name,
            version=1,
            state=EnterpriseResourceState.REGISTERED,
            owner_id=request.owner_id,
            access_policy_ids=request.access_policy_ids,
            governance_policy_ids=request.governance_policy_ids,
            retention_policy_id=request.retention_policy_id,
            provenance=request.provenance,
            semantic_relations=tuple(
                EnterpriseResourceRelation(**item.model_dump())
                for item in request.semantic_relations
            ),
            evidence=tuple(
                EnterpriseResourceEvidence(**item.model_dump()) for item in request.evidence
            ),
            metadata=request.metadata,
            registered_by=actor.subject,
            registered_at=now,
            content_hash=hash_json(material),
        )
        self._policy.require_managed(resource)
        await self._repository.add(resource)
        await self._record(
            "enterprise_resource.registered",
            resource.id,
            actor.subject,
            {
                "organization_id": str(resource.organization_id),
                "resource_type": resource.resource_type,
                "resource_key": resource.resource_key,
                "version": resource.version,
                "content_hash": resource.content_hash,
            },
        )
        await self._repository.commit()
        return resource

    async def get_resource(self, resource_id: uuid.UUID) -> EnterpriseResource:
        resource = await self._repository.get(resource_id)
        if resource is None:
            raise EnterpriseResourceNotFound("Enterprise resource not found")
        return resource

    async def schedule_work(
        self, request: ScheduleEnterpriseWork, actor: KernelActor
    ) -> EnterpriseSchedule:
        existing = await self._repository.get_schedule_by_key(
            request.organization_id, request.schedule_key
        )
        if existing is not None:
            raise EnterpriseScheduleAlreadyExists(
                "Enterprise schedule key is already registered for this organization"
            )
        target = await self._repository.get(request.target_resource_id)
        if target is None or target.organization_id != request.organization_id:
            raise EnterpriseResourceNotFound("Schedule target resource is not registered")
        if target.version != request.target_resource_version:
            raise InvalidEnterpriseSchedule("Schedule target resource version is not current")
        missing_dependencies = []
        for dependency_id in request.dependencies:
            dependency = await self._repository.get(dependency_id)
            if dependency is None or dependency.organization_id != request.organization_id:
                missing_dependencies.append(str(dependency_id))
        if missing_dependencies:
            raise InvalidEnterpriseSchedule(
                "Schedule dependencies are not registered: " + ", ".join(missing_dependencies)
            )
        now = datetime.now(UTC)
        material = request.model_dump(mode="json") | {
            "state": EnterpriseScheduleState.QUEUED,
            "scheduled_by": actor.subject,
            "scheduled_at": now.isoformat(),
        }
        schedule = EnterpriseSchedule(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            schedule_key=request.schedule_key,
            work_type=request.work_type,
            priority=request.priority,
            target_resource_id=request.target_resource_id,
            target_resource_version=request.target_resource_version,
            dependencies=request.dependencies,
            required_approval_gate_ids=request.required_approval_gate_ids,
            capability_requirements=request.capability_requirements,
            resource_claims=tuple(
                EnterpriseResourceClaim(**item.model_dump()) for item in request.resource_claims
            ),
            evidence=tuple(
                EnterpriseResourceEvidence(**item.model_dump()) for item in request.evidence
            ),
            state=EnterpriseScheduleState.QUEUED,
            scheduled_by=actor.subject,
            scheduled_at=now,
            content_hash=hash_json(material),
        )
        self._scheduling.require_schedulable(schedule)
        await self._repository.add_schedule(schedule)
        await self._record(
            "enterprise_schedule.queued",
            schedule.id,
            actor.subject,
            {
                "organization_id": str(schedule.organization_id),
                "schedule_key": schedule.schedule_key,
                "target_resource_id": str(schedule.target_resource_id),
                "dependency_count": len(schedule.dependencies),
                "content_hash": schedule.content_hash,
            },
        )
        await self._repository.commit()
        return schedule

    async def _record(
        self, event_type: str, resource_id: uuid.UUID, actor_id: str, payload: dict[str, object]
    ) -> None:
        occurred_at = datetime.now(UTC)
        payload_hash = hash_json(payload)
        await self._audit.append(
            EnterpriseResourceAuditRecord(
                event_type=event_type,
                resource_id=resource_id,
                actor_id=actor_id,
                occurred_at=occurred_at,
                payload=payload,
                payload_hash=payload_hash,
            )
        )
