from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.enterprise_kernel_authority import enterprise_kernel_actor
from ai_enterprise.api.routes.enterprise_kernel import router
from ai_enterprise.application.enterprise_kernel.dto import (
    OpenOrganizationalThread,
    RecordOperatingMaturity,
    RegisterEnterpriseModule,
    RegisterEnterpriseResource,
    ScheduleEnterpriseWork,
)
from ai_enterprise.application.enterprise_kernel.service import EnterpriseKernelService
from ai_enterprise.domain.enterprise_kernel.entities import (
    EnterpriseModule,
    EnterpriseResource,
    EnterpriseResourceAuditRecord,
    EnterpriseResourceEvidence,
    EnterpriseSchedule,
    OperatingMaturitySnapshot,
    OrganizationalThread,
)
from ai_enterprise.domain.enterprise_kernel.enums import (
    EnterpriseResourceState,
    EnterpriseResourceType,
    EnterpriseScheduleState,
)
from ai_enterprise.domain.enterprise_kernel.exceptions import (
    EnterpriseResourceNotFound,
    EnterpriseScheduleNotFound,
    InvalidEnterpriseResource,
    InvalidEnterpriseSchedule,
    InvalidOperatingMaturity,
    InvalidOrganizationalThread,
)
from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.infrastructure.enterprise_kernel.models import (
    EnterpriseModuleModel,
    EnterpriseResourceAuditModel,
    EnterpriseResourceModel,
    EnterpriseScheduleModel,
    OperatingMaturitySnapshotModel,
    OrganizationalThreadModel,
)
from ai_enterprise.infrastructure.enterprise_kernel.repository import (
    SqlAlchemyEnterpriseResourceRepository,
)
from ai_enterprise.main import app


class MemoryRepository:
    def __init__(self) -> None:
        self.values: dict[object, EnterpriseResource] = {}
        self.schedules: dict[object, EnterpriseSchedule] = {}
        self.modules: dict[object, EnterpriseModule] = {}
        self.threads: dict[object, OrganizationalThread] = {}
        self.snapshots: dict[object, OperatingMaturitySnapshot] = {}
        self.committed = False

    async def add(self, resource: EnterpriseResource) -> None:
        self.values[resource.id] = resource

    async def get(self, resource_id):
        return self.values.get(resource_id)

    async def get_by_key(self, organization_id, resource_key):
        return next(
            (
                item
                for item in self.values.values()
                if item.organization_id == organization_id and item.resource_key == resource_key
            ),
            None,
        )

    async def list_for_organization(self, organization_id):
        return tuple(
            item for item in self.values.values() if item.organization_id == organization_id
        )

    async def add_schedule(self, schedule: EnterpriseSchedule) -> None:
        self.schedules[schedule.id] = schedule

    async def get_schedule(self, schedule_id):
        return self.schedules.get(schedule_id)

    async def get_schedule_by_key(self, organization_id, schedule_key):
        return next(
            (
                item
                for item in self.schedules.values()
                if item.organization_id == organization_id and item.schedule_key == schedule_key
            ),
            None,
        )

    async def list_schedules_for_organization(self, organization_id):
        return tuple(
            item for item in self.schedules.values() if item.organization_id == organization_id
        )

    async def add_module(self, module: EnterpriseModule) -> None:
        self.modules[module.id] = module

    async def get_module_by_key(self, organization_id, module_key):
        return next(
            (
                item
                for item in self.modules.values()
                if item.organization_id == organization_id and item.module_key == module_key
            ),
            None,
        )

    async def list_modules_for_organization(self, organization_id):
        return tuple(
            item for item in self.modules.values() if item.organization_id == organization_id
        )

    async def add_thread(self, thread: OrganizationalThread) -> None:
        self.threads[thread.id] = thread

    async def get_thread_by_key(self, organization_id, thread_key):
        return next(
            (
                item
                for item in self.threads.values()
                if item.organization_id == organization_id and item.thread_key == thread_key
            ),
            None,
        )

    async def list_threads_for_organization(self, organization_id):
        return tuple(
            item for item in self.threads.values() if item.organization_id == organization_id
        )

    async def add_maturity_snapshot(self, snapshot: OperatingMaturitySnapshot) -> None:
        self.snapshots[snapshot.id] = snapshot

    async def get_maturity_snapshot_by_key(self, organization_id, snapshot_key):
        return next(
            (
                item
                for item in self.snapshots.values()
                if item.organization_id == organization_id and item.snapshot_key == snapshot_key
            ),
            None,
        )

    async def list_maturity_snapshots_for_organization(self, organization_id):
        return tuple(
            item for item in self.snapshots.values() if item.organization_id == organization_id
        )

    async def commit(self) -> None:
        self.committed = True


class MemoryAudit:
    def __init__(self) -> None:
        self.records: list[EnterpriseResourceAuditRecord] = []

    async def append(self, record: EnterpriseResourceAuditRecord) -> None:
        self.records.append(record)


def request(**overrides) -> RegisterEnterpriseResource:
    data = {
        "organization_id": uuid4(),
        "resource_type": EnterpriseResourceType.PROJECT,
        "resource_key": "project.alpha",
        "display_name": "Project Alpha",
        "owner_id": "alice",
        "access_policy_ids": ("policy-access",),
        "governance_policy_ids": ("policy-governance",),
        "retention_policy_id": "retention-standard",
        "provenance": {"source": "intake", "command_id": str(uuid4())},
        "evidence": (
            {
                "artifact_id": uuid4(),
                "content_hash": "a" * 64,
                "evidence_type": "intake_record",
            },
        ),
        "metadata": {"portfolio": "core"},
    }
    data.update(overrides)
    return RegisterEnterpriseResource(**data)


def schedule_request(target: EnterpriseResource, **overrides) -> ScheduleEnterpriseWork:
    data = {
        "organization_id": target.organization_id,
        "schedule_key": "schedule.project.alpha.requirements",
        "work_type": "requirements_analysis",
        "priority": 70,
        "target_resource_id": target.id,
        "target_resource_version": target.version,
        "dependencies": (),
        "required_approval_gate_ids": ("requirements-intake-approved",),
        "capability_requirements": ("requirements.analyze",),
        "resource_claims": (
            {"resource_kind": "agent_slot", "amount": 1, "unit": "slot"},
        ),
        "evidence": (
            {
                "artifact_id": uuid4(),
                "content_hash": "d" * 64,
                "evidence_type": "schedule_basis",
            },
        ),
    }
    data.update(overrides)
    return ScheduleEnterpriseWork(**data)


def module_request(resource: EnterpriseResource, **overrides) -> RegisterEnterpriseModule:
    data = {
        "organization_id": resource.organization_id,
        "module_key": "module.requirements",
        "display_name": "Requirements Module",
        "capability_ids": ("requirements.analyze",),
        "owned_resource_ids": (resource.id,),
        "integration_resource_ids": (),
        "governance_policy_ids": ("policy-governance",),
        "evidence": (
            {
                "artifact_id": uuid4(),
                "content_hash": "1" * 64,
                "evidence_type": "module_certification",
            },
        ),
    }
    data.update(overrides)
    return RegisterEnterpriseModule(**data)


def thread_request(
    root: EnterpriseResource,
    next_resource: EnterpriseResource,
    schedule: EnterpriseSchedule,
    **overrides,
) -> OpenOrganizationalThread:
    data = {
        "organization_id": root.organization_id,
        "thread_key": "thread.project.alpha",
        "root_resource_id": root.id,
        "resource_sequence": (root.id, next_resource.id),
        "schedule_sequence": (schedule.id,),
        "owner_id": "alice",
        "evidence": (
            {
                "artifact_id": uuid4(),
                "content_hash": "2" * 64,
                "evidence_type": "thread_lineage",
            },
        ),
    }
    data.update(overrides)
    return OpenOrganizationalThread(**data)


def maturity_request(**overrides) -> RecordOperatingMaturity:
    data = {
        "organization_id": uuid4(),
        "snapshot_key": "maturity.2026-q3",
        "maturity_level": 2,
        "covered_resource_types": tuple(EnterpriseResourceType),
        "module_count": 1,
        "active_thread_count": 1,
        "evidence": (
            {
                "artifact_id": uuid4(),
                "content_hash": "3" * 64,
                "evidence_type": "coverage_report",
            },
            {
                "artifact_id": uuid4(),
                "content_hash": "4" * 64,
                "evidence_type": "operating_review",
            },
        ),
    }
    data.update(overrides)
    return RecordOperatingMaturity(**data)


@pytest.mark.asyncio
async def test_resource_registration_requires_managed_kernel_metadata() -> None:
    service = EnterpriseKernelService(MemoryRepository(), MemoryAudit())
    with pytest.raises(InvalidEnterpriseResource, match="owner"):
        await service.register_resource(
            request(owner_id=" "),
            enterprise_kernel_actor(Actor("alice", "human", "enterprise_kernel_admin"), "x"),
        )


@pytest.mark.asyncio
async def test_resource_registration_hashes_persists_and_audits_initial_version() -> None:
    repository = MemoryRepository()
    audit = MemoryAudit()
    service = EnterpriseKernelService(repository, audit)

    value = await service.register_resource(
        request(),
        enterprise_kernel_actor(
            Actor("alice", "human", "enterprise_kernel_admin"),
            "enterprise_resource.register",
        ),
    )

    assert value.version == 1
    assert value.state is EnterpriseResourceState.REGISTERED
    assert value.content_hash
    assert repository.committed is True
    assert audit.records[0].event_type == "enterprise_resource.registered"
    assert audit.records[0].payload["content_hash"] == value.content_hash


@pytest.mark.asyncio
async def test_schedule_requires_registered_dependency_resources() -> None:
    repository = MemoryRepository()
    audit = MemoryAudit()
    service = EnterpriseKernelService(repository, audit)
    actor = enterprise_kernel_actor(Actor("alice", "human", "enterprise_kernel_admin"), "x")
    target = await service.register_resource(request(), actor)

    with pytest.raises(InvalidEnterpriseSchedule, match="dependencies"):
        await service.schedule_work(
            schedule_request(target, dependencies=(uuid4(),)),
            actor,
        )


@pytest.mark.asyncio
async def test_schedule_hashes_persists_and_audits_queued_work() -> None:
    repository = MemoryRepository()
    audit = MemoryAudit()
    service = EnterpriseKernelService(repository, audit)
    actor = enterprise_kernel_actor(
        Actor("alice", "human", "enterprise_kernel_admin"),
        "enterprise_schedule.create",
    )
    target = await service.register_resource(request(), actor)

    schedule = await service.schedule_work(schedule_request(target), actor)

    assert schedule.state is EnterpriseScheduleState.QUEUED
    assert schedule.target_resource_id == target.id
    assert schedule.content_hash
    assert repository.schedules[schedule.id] == schedule
    assert audit.records[-1].event_type == "enterprise_schedule.queued"
    assert audit.records[-1].payload["content_hash"] == schedule.content_hash


@pytest.mark.asyncio
async def test_module_registration_requires_managed_owned_resources() -> None:
    repository = MemoryRepository()
    service = EnterpriseKernelService(repository, MemoryAudit())
    actor = enterprise_kernel_actor(
        Actor("alice", "human", "enterprise_kernel_admin"),
        "enterprise_module.register",
    )
    resource = await service.register_resource(request(), actor)

    with pytest.raises(EnterpriseResourceNotFound, match="Module resources"):
        await service.register_module(
            module_request(resource, owned_resource_ids=(uuid4(),)),
            actor,
        )

@pytest.mark.asyncio
async def test_module_thread_and_maturity_records_close_p11_kernel_coverage() -> None:
    repository = MemoryRepository()
    audit = MemoryAudit()
    service = EnterpriseKernelService(repository, audit)
    actor = enterprise_kernel_actor(
        Actor("alice", "human", "enterprise_kernel_admin"),
        "enterprise_module.register",
    )
    organization_id = uuid4()
    project = await service.register_resource(
        request(organization_id=organization_id, resource_key="project.alpha"),
        actor,
    )
    requirement = await service.register_resource(
        request(
            organization_id=organization_id,
            resource_type=EnterpriseResourceType.REQUIREMENT,
            resource_key="requirement.alpha",
        ),
        actor,
    )
    for resource_type in EnterpriseResourceType:
        if resource_type in {EnterpriseResourceType.PROJECT, EnterpriseResourceType.REQUIREMENT}:
            continue
        await service.register_resource(
            request(
                organization_id=organization_id,
                resource_type=resource_type,
                resource_key=f"{resource_type.value}.alpha",
                display_name=f"{resource_type.value} Alpha",
            ),
            actor,
        )
    schedule = await service.schedule_work(schedule_request(project), actor)

    module = await service.register_module(module_request(project), actor)
    thread = await service.open_thread(thread_request(project, requirement, schedule), actor)
    snapshot = await service.record_maturity(
        maturity_request(organization_id=organization_id),
        actor,
    )

    assert repository.modules[module.id] == module
    assert repository.threads[thread.id] == thread
    assert repository.snapshots[snapshot.id] == snapshot
    assert thread.resource_sequence == (project.id, requirement.id)
    assert set(snapshot.covered_resource_types) == set(EnterpriseResourceType)
    assert all(len(item.content_hash) == 64 for item in (module, thread, snapshot))
    assert audit.records[-3].event_type == "enterprise_module.registered"
    assert audit.records[-2].event_type == "organizational_thread.opened"
    assert audit.records[-1].event_type == "operating_maturity.recorded"


@pytest.mark.asyncio
async def test_thread_requires_registered_schedules_and_complete_lineage() -> None:
    repository = MemoryRepository()
    service = EnterpriseKernelService(repository, MemoryAudit())
    actor = enterprise_kernel_actor(Actor("alice", "human", "enterprise_kernel_admin"), "x")
    organization_id = uuid4()
    project = await service.register_resource(request(organization_id=organization_id), actor)
    requirement = await service.register_resource(
        request(
            organization_id=organization_id,
            resource_type=EnterpriseResourceType.REQUIREMENT,
            resource_key="requirement.alpha",
        ),
        actor,
    )
    other = await service.register_resource(
        request(
            organization_id=organization_id,
            resource_type=EnterpriseResourceType.ARCHITECTURE,
            resource_key="architecture.alpha",
        ),
        actor,
    )
    schedule = await service.schedule_work(schedule_request(project), actor)

    with pytest.raises(EnterpriseScheduleNotFound, match="Thread schedules"):
        await service.open_thread(
            thread_request(project, requirement, schedule, schedule_sequence=(uuid4(),)),
            actor,
        )
    with pytest.raises(InvalidOrganizationalThread, match="root"):
        await service.open_thread(
            thread_request(
                project,
                requirement,
                schedule,
                root_resource_id=other.id,
                thread_key="thread.invalid",
                resource_sequence=(project.id, requirement.id),
            ),
            actor,
        )


@pytest.mark.asyncio
async def test_maturity_requires_full_resource_coverage_and_evidence_bound_level() -> None:
    repository = MemoryRepository()
    service = EnterpriseKernelService(repository, MemoryAudit())
    actor = enterprise_kernel_actor(Actor("alice", "human", "enterprise_kernel_admin"), "x")

    with pytest.raises(InvalidOperatingMaturity, match="proven"):
        await service.record_maturity(
            maturity_request(covered_resource_types=(EnterpriseResourceType.PROJECT,)),
            actor,
        )
    organization_id = uuid4()
    project = None
    for resource_type in EnterpriseResourceType:
        resource = await service.register_resource(
            request(
                organization_id=organization_id,
                resource_type=resource_type,
                resource_key=f"{resource_type.value}.evidence",
                display_name=f"{resource_type.value} Evidence",
            ),
            actor,
        )
        if resource_type is EnterpriseResourceType.PROJECT:
            project = resource
    assert project is not None
    await service.register_module(module_request(project), actor)
    with pytest.raises(InvalidOperatingMaturity, match="evidence"):
        await service.record_maturity(
            maturity_request(
                organization_id=organization_id,
                snapshot_key="maturity.invalid",
                maturity_level=3,
                module_count=1,
                active_thread_count=0,
                evidence=(
                    {
                        "artifact_id": uuid4(),
                        "content_hash": "5" * 64,
                        "evidence_type": "thin_review",
                    },
                ),
            ),
            actor,
        )


def test_enterprise_resource_models_are_registered_in_metadata() -> None:
    assert EnterpriseResourceModel.__tablename__ in Base.metadata.tables
    assert EnterpriseResourceAuditModel.__tablename__ in Base.metadata.tables
    assert EnterpriseScheduleModel.__tablename__ in Base.metadata.tables
    assert EnterpriseModuleModel.__tablename__ in Base.metadata.tables
    assert OrganizationalThreadModel.__tablename__ in Base.metadata.tables
    assert OperatingMaturitySnapshotModel.__tablename__ in Base.metadata.tables
    assert EnterpriseResourceModel.__table__.c.content_hash.unique is True
    assert EnterpriseScheduleModel.__table__.c.content_hash.unique is True
    assert EnterpriseModuleModel.__table__.c.content_hash.unique is True
    assert OrganizationalThreadModel.__table__.c.content_hash.unique is True
    assert OperatingMaturitySnapshotModel.__table__.c.content_hash.unique is True
    assert "updated_at" not in EnterpriseResourceModel.__table__.c


def test_repository_round_trips_resource_model() -> None:
    now = datetime.now(UTC)
    resource_id = uuid4()
    evidence_id = uuid4()
    model = EnterpriseResourceModel(
        id=resource_id,
        organization_id=uuid4(),
        resource_type="project",
        resource_key="project.alpha",
        display_name="Project Alpha",
        version=1,
        state="registered",
        owner_id="alice",
        access_policy_ids=["policy-access"],
        governance_policy_ids=["policy-governance"],
        retention_policy_id="retention-standard",
        provenance={"source": "intake"},
        semantic_relations=[],
        evidence=[
            {
                "artifact_id": str(evidence_id),
                "content_hash": "b" * 64,
                "evidence_type": "intake_record",
            }
        ],
        resource_metadata={"portfolio": "core"},
        registered_by="alice",
        registered_at=now,
        content_hash="c" * 64,
    )

    value = SqlAlchemyEnterpriseResourceRepository._resource(model)

    assert value.id == resource_id
    assert value.resource_type is EnterpriseResourceType.PROJECT
    assert value.evidence == (
        EnterpriseResourceEvidence(evidence_id, "b" * 64, "intake_record"),
    )


def test_repository_round_trips_schedule_model() -> None:
    now = datetime.now(UTC)
    schedule_id = uuid4()
    target_id = uuid4()
    dependency_id = uuid4()
    evidence_id = uuid4()
    model = EnterpriseScheduleModel(
        id=schedule_id,
        organization_id=uuid4(),
        schedule_key="schedule.alpha",
        work_type="implementation",
        priority=90,
        target_resource_id=target_id,
        target_resource_version=1,
        dependencies=[str(dependency_id)],
        required_approval_gate_ids=["architecture-approved"],
        capability_requirements=["implementation.python"],
        resource_claims=[{"resource_kind": "agent_slot", "amount": 1, "unit": "slot"}],
        evidence=[
            {
                "artifact_id": str(evidence_id),
                "content_hash": "e" * 64,
                "evidence_type": "schedule_basis",
            }
        ],
        state="queued",
        scheduled_by="alice",
        scheduled_at=now,
        content_hash="f" * 64,
    )

    value = SqlAlchemyEnterpriseResourceRepository._schedule(model)

    assert value.id == schedule_id
    assert value.dependencies == (dependency_id,)
    assert value.state is EnterpriseScheduleState.QUEUED
    assert value.resource_claims[0].resource_kind == "agent_slot"


def test_enterprise_kernel_api_surface_is_registered() -> None:
    paths = {route.path for route in router.routes}
    assert "/enterprise-kernel/resources" in paths
    assert "/enterprise-kernel/resources/{resource_id}" in paths
    assert "/enterprise-kernel/schedules" in paths
    assert "/enterprise-kernel/modules" in paths
    assert "/enterprise-kernel/threads" in paths
    assert "/enterprise-kernel/maturity-snapshots" in paths
    registered = set(app.openapi()["paths"])
    assert "/api/v1/enterprise-kernel/resources" in registered
    assert "/api/v1/enterprise-kernel/schedules" in registered
    assert "/api/v1/enterprise-kernel/modules" in registered
    assert "/api/v1/enterprise-kernel/threads" in registered
    assert "/api/v1/enterprise-kernel/maturity-snapshots" in registered


def test_enterprise_kernel_authority_is_human_and_capability_bound() -> None:
    actor = Actor("alice", "human", "engineer", frozenset({"enterprise_resource.register"}))
    assert enterprise_kernel_actor(actor, "enterprise_resource.register").subject == "alice"
    with pytest.raises(HTTPException, match="human"):
        enterprise_kernel_actor(
            Actor("agent", "agent", "enterprise_kernel_admin"),
            "enterprise_resource.register",
        )
    with pytest.raises(HTTPException, match="Missing capability"):
        enterprise_kernel_actor(Actor("bob", "human", "engineer"), "enterprise_resource.register")
