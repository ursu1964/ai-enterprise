import uuid
from datetime import UTC, datetime

from ai_enterprise.application.enterprise_kernel.dto import (
    KernelActor,
    OpenOrganizationalThread,
    RecordOperatingMaturity,
    RegisterEnterpriseModule,
    RegisterEnterpriseResource,
    ScheduleEnterpriseWork,
)
from ai_enterprise.application.enterprise_kernel.ports import (
    EnterpriseKernelAuditSink,
    EnterpriseResourceRepository,
)
from ai_enterprise.domain.enterprise_kernel.entities import (
    EnterpriseModule,
    EnterpriseResource,
    EnterpriseResourceAuditRecord,
    EnterpriseResourceClaim,
    EnterpriseResourceEvidence,
    EnterpriseResourceRelation,
    EnterpriseSchedule,
    OperatingMaturitySnapshot,
    OrganizationalThread,
)
from ai_enterprise.domain.enterprise_kernel.enums import (
    EnterpriseModuleState,
    EnterpriseResourceState,
    EnterpriseScheduleState,
    OrganizationalThreadState,
)
from ai_enterprise.domain.enterprise_kernel.exceptions import (
    EnterpriseModuleAlreadyExists,
    EnterpriseResourceAlreadyExists,
    EnterpriseResourceNotFound,
    EnterpriseScheduleAlreadyExists,
    EnterpriseScheduleNotFound,
    InvalidEnterpriseSchedule,
    InvalidOperatingMaturity,
    OperatingMaturityAlreadyExists,
    OrganizationalThreadAlreadyExists,
)
from ai_enterprise.domain.enterprise_kernel.policies import (
    EnterpriseModulePolicy,
    EnterpriseSchedulingPolicy,
    OperatingMaturityPolicy,
    OrganizationalThreadPolicy,
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
        self._modules = EnterpriseModulePolicy()
        self._threads = OrganizationalThreadPolicy()
        self._maturity = OperatingMaturityPolicy()

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

    async def register_module(
        self, request: RegisterEnterpriseModule, actor: KernelActor
    ) -> EnterpriseModule:
        existing = await self._repository.get_module_by_key(
            request.organization_id, request.module_key
        )
        if existing is not None:
            raise EnterpriseModuleAlreadyExists(
                "Enterprise module key is already registered for this organization"
            )
        await self._require_resources(
            request.organization_id,
            request.owned_resource_ids + request.integration_resource_ids,
            "Module resources are not registered",
        )
        now = datetime.now(UTC)
        material = request.model_dump(mode="json") | {
            "state": EnterpriseModuleState.REGISTERED,
            "registered_by": actor.subject,
            "registered_at": now.isoformat(),
        }
        module = EnterpriseModule(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            module_key=request.module_key,
            display_name=request.display_name,
            capability_ids=request.capability_ids,
            owned_resource_ids=request.owned_resource_ids,
            integration_resource_ids=request.integration_resource_ids,
            governance_policy_ids=request.governance_policy_ids,
            evidence=tuple(
                EnterpriseResourceEvidence(**item.model_dump()) for item in request.evidence
            ),
            state=EnterpriseModuleState.REGISTERED,
            registered_by=actor.subject,
            registered_at=now,
            content_hash=hash_json(material),
        )
        self._modules.require_governed_module(module)
        await self._repository.add_module(module)
        await self._record(
            "enterprise_module.registered",
            module.id,
            actor.subject,
            {
                "organization_id": str(module.organization_id),
                "module_key": module.module_key,
                "capability_count": len(module.capability_ids),
                "content_hash": module.content_hash,
            },
        )
        await self._repository.commit()
        return module

    async def open_thread(
        self, request: OpenOrganizationalThread, actor: KernelActor
    ) -> OrganizationalThread:
        existing = await self._repository.get_thread_by_key(
            request.organization_id, request.thread_key
        )
        if existing is not None:
            raise OrganizationalThreadAlreadyExists(
                "Organizational thread key is already registered for this organization"
            )
        await self._require_resources(
            request.organization_id,
            request.resource_sequence,
            "Thread resources are not registered",
        )
        missing_schedules = []
        for schedule_id in request.schedule_sequence:
            schedule = await self._repository.get_schedule(schedule_id)
            if schedule is None or schedule.organization_id != request.organization_id:
                missing_schedules.append(str(schedule_id))
        if missing_schedules:
            raise EnterpriseScheduleNotFound(
                "Thread schedules are not registered: " + ", ".join(missing_schedules)
            )
        schedules = [
            await self._repository.get_schedule(schedule_id)
            for schedule_id in request.schedule_sequence
        ]
        if any(
            schedule is not None and schedule.target_resource_id not in request.resource_sequence
            for schedule in schedules
        ):
            raise InvalidEnterpriseSchedule("Thread schedules must target resources in lineage")
        now = datetime.now(UTC)
        material = request.model_dump(mode="json") | {
            "state": OrganizationalThreadState.OPEN,
            "opened_by": actor.subject,
            "opened_at": now.isoformat(),
        }
        thread = OrganizationalThread(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            thread_key=request.thread_key,
            root_resource_id=request.root_resource_id,
            resource_sequence=request.resource_sequence,
            schedule_sequence=request.schedule_sequence,
            current_state=OrganizationalThreadState.OPEN,
            owner_id=request.owner_id,
            evidence=tuple(
                EnterpriseResourceEvidence(**item.model_dump()) for item in request.evidence
            ),
            opened_by=actor.subject,
            opened_at=now,
            content_hash=hash_json(material),
        )
        self._threads.require_thread_lineage(thread)
        await self._repository.add_thread(thread)
        await self._record(
            "organizational_thread.opened",
            thread.id,
            actor.subject,
            {
                "organization_id": str(thread.organization_id),
                "thread_key": thread.thread_key,
                "resource_count": len(thread.resource_sequence),
                "schedule_count": len(thread.schedule_sequence),
                "content_hash": thread.content_hash,
            },
        )
        await self._repository.commit()
        return thread

    async def record_maturity(
        self, request: RecordOperatingMaturity, actor: KernelActor
    ) -> OperatingMaturitySnapshot:
        existing = await self._repository.get_maturity_snapshot_by_key(
            request.organization_id, request.snapshot_key
        )
        if existing is not None:
            raise OperatingMaturityAlreadyExists(
                "Operating maturity snapshot key is already registered for this organization"
            )
        resources = await self._repository.list_for_organization(request.organization_id)
        actual_resource_types = {resource.resource_type for resource in resources}
        if set(request.covered_resource_types) - actual_resource_types:
            raise InvalidOperatingMaturity(
                "Resource coverage must be proven by registered resources"
            )
        modules = await self._repository.list_modules_for_organization(request.organization_id)
        threads = await self._repository.list_threads_for_organization(request.organization_id)
        if request.module_count != len(modules):
            raise InvalidOperatingMaturity("Module count must match registered modules")
        active_threads = sum(
            thread.current_state is OrganizationalThreadState.OPEN for thread in threads
        )
        if request.active_thread_count != active_threads:
            raise InvalidOperatingMaturity("Active thread count must match open threads")
        now = datetime.now(UTC)
        material = request.model_dump(mode="json") | {
            "recorded_by": actor.subject,
            "recorded_at": now.isoformat(),
        }
        snapshot = OperatingMaturitySnapshot(
            id=uuid.uuid4(),
            organization_id=request.organization_id,
            snapshot_key=request.snapshot_key,
            maturity_level=request.maturity_level,
            covered_resource_types=request.covered_resource_types,
            module_count=request.module_count,
            active_thread_count=request.active_thread_count,
            evidence=tuple(
                EnterpriseResourceEvidence(**item.model_dump()) for item in request.evidence
            ),
            recorded_by=actor.subject,
            recorded_at=now,
            content_hash=hash_json(material),
        )
        self._maturity.require_evidence_bound_coverage(snapshot)
        await self._repository.add_maturity_snapshot(snapshot)
        await self._record(
            "operating_maturity.recorded",
            snapshot.id,
            actor.subject,
            {
                "organization_id": str(snapshot.organization_id),
                "snapshot_key": snapshot.snapshot_key,
                "maturity_level": snapshot.maturity_level,
                "content_hash": snapshot.content_hash,
            },
        )
        await self._repository.commit()
        return snapshot

    async def _require_resources(
        self, organization_id: uuid.UUID, resource_ids: tuple[uuid.UUID, ...], message: str
    ) -> None:
        missing = []
        for resource_id in resource_ids:
            resource = await self._repository.get(resource_id)
            if resource is None or resource.organization_id != organization_id:
                missing.append(str(resource_id))
        if missing:
            raise EnterpriseResourceNotFound(message + ": " + ", ".join(missing))

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
