import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    EnterpriseResourceType,
    EnterpriseScheduleState,
)

from .models import EnterpriseResourceAuditModel, EnterpriseResourceModel, EnterpriseScheduleModel


def _relation_payload(value: EnterpriseResourceRelation) -> dict[str, Any]:
    return {
        "relation_type": value.relation_type,
        "target_resource_id": str(value.target_resource_id),
        "target_version": value.target_version,
    }


def _evidence_payload(value: EnterpriseResourceEvidence) -> dict[str, str]:
    return {
        "artifact_id": str(value.artifact_id),
        "content_hash": value.content_hash,
        "evidence_type": value.evidence_type,
    }


def _claim_payload(value: EnterpriseResourceClaim) -> dict[str, object]:
    return {
        "resource_kind": value.resource_kind,
        "amount": value.amount,
        "unit": value.unit,
    }


def _relation(value: dict[str, Any]) -> EnterpriseResourceRelation:
    return EnterpriseResourceRelation(
        relation_type=str(value["relation_type"]),
        target_resource_id=uuid.UUID(str(value["target_resource_id"])),
        target_version=value.get("target_version"),
    )


def _evidence(value: dict[str, Any]) -> EnterpriseResourceEvidence:
    return EnterpriseResourceEvidence(
        artifact_id=uuid.UUID(str(value["artifact_id"])),
        content_hash=str(value["content_hash"]),
        evidence_type=str(value["evidence_type"]),
    )


def _claim(value: dict[str, Any]) -> EnterpriseResourceClaim:
    return EnterpriseResourceClaim(
        resource_kind=str(value["resource_kind"]),
        amount=int(value["amount"]),
        unit=str(value["unit"]),
    )


class SqlAlchemyEnterpriseResourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, resource: EnterpriseResource) -> None:
        self._session.add(
            EnterpriseResourceModel(
                id=resource.id,
                organization_id=resource.organization_id,
                resource_type=resource.resource_type,
                resource_key=resource.resource_key,
                display_name=resource.display_name,
                version=resource.version,
                state=resource.state,
                owner_id=resource.owner_id,
                access_policy_ids=list(resource.access_policy_ids),
                governance_policy_ids=list(resource.governance_policy_ids),
                retention_policy_id=resource.retention_policy_id,
                provenance=resource.provenance,
                semantic_relations=[
                    _relation_payload(item) for item in resource.semantic_relations
                ],
                evidence=[_evidence_payload(item) for item in resource.evidence],
                resource_metadata=resource.metadata,
                registered_by=resource.registered_by,
                registered_at=resource.registered_at,
                content_hash=resource.content_hash,
            )
        )

    async def get(self, resource_id: uuid.UUID) -> EnterpriseResource | None:
        model = await self._session.get(EnterpriseResourceModel, resource_id)
        return self._resource(model) if model else None

    async def get_by_key(
        self, organization_id: uuid.UUID, resource_key: str
    ) -> EnterpriseResource | None:
        model = await self._session.scalar(
            select(EnterpriseResourceModel).where(
                EnterpriseResourceModel.organization_id == organization_id,
                EnterpriseResourceModel.resource_key == resource_key,
            )
        )
        return self._resource(model) if model else None

    async def list_for_organization(
        self, organization_id: uuid.UUID
    ) -> tuple[EnterpriseResource, ...]:
        result = await self._session.scalars(
            select(EnterpriseResourceModel)
            .where(EnterpriseResourceModel.organization_id == organization_id)
            .order_by(EnterpriseResourceModel.resource_key)
        )
        return tuple(self._resource(item) for item in result.all())

    async def add_schedule(self, schedule: EnterpriseSchedule) -> None:
        self._session.add(
            EnterpriseScheduleModel(
                id=schedule.id,
                organization_id=schedule.organization_id,
                schedule_key=schedule.schedule_key,
                work_type=schedule.work_type,
                priority=schedule.priority,
                target_resource_id=schedule.target_resource_id,
                target_resource_version=schedule.target_resource_version,
                dependencies=[str(item) for item in schedule.dependencies],
                required_approval_gate_ids=list(schedule.required_approval_gate_ids),
                capability_requirements=list(schedule.capability_requirements),
                resource_claims=[_claim_payload(item) for item in schedule.resource_claims],
                evidence=[_evidence_payload(item) for item in schedule.evidence],
                state=schedule.state,
                scheduled_by=schedule.scheduled_by,
                scheduled_at=schedule.scheduled_at,
                content_hash=schedule.content_hash,
            )
        )

    async def get_schedule(self, schedule_id: uuid.UUID) -> EnterpriseSchedule | None:
        model = await self._session.get(EnterpriseScheduleModel, schedule_id)
        return self._schedule(model) if model else None

    async def get_schedule_by_key(
        self, organization_id: uuid.UUID, schedule_key: str
    ) -> EnterpriseSchedule | None:
        model = await self._session.scalar(
            select(EnterpriseScheduleModel).where(
                EnterpriseScheduleModel.organization_id == organization_id,
                EnterpriseScheduleModel.schedule_key == schedule_key,
            )
        )
        return self._schedule(model) if model else None

    async def list_schedules_for_organization(
        self, organization_id: uuid.UUID
    ) -> tuple[EnterpriseSchedule, ...]:
        result = await self._session.scalars(
            select(EnterpriseScheduleModel)
            .where(EnterpriseScheduleModel.organization_id == organization_id)
            .order_by(EnterpriseScheduleModel.priority.desc(), EnterpriseScheduleModel.scheduled_at)
        )
        return tuple(self._schedule(item) for item in result.all())

    async def commit(self) -> None:
        await self._session.commit()

    @staticmethod
    def _resource(model: EnterpriseResourceModel) -> EnterpriseResource:
        return EnterpriseResource(
            id=model.id,
            organization_id=model.organization_id,
            resource_type=EnterpriseResourceType(model.resource_type),
            resource_key=model.resource_key,
            display_name=model.display_name,
            version=model.version,
            state=EnterpriseResourceState(model.state),
            owner_id=model.owner_id,
            access_policy_ids=tuple(model.access_policy_ids),
            governance_policy_ids=tuple(model.governance_policy_ids),
            retention_policy_id=model.retention_policy_id,
            provenance=model.provenance,
            semantic_relations=tuple(_relation(item) for item in model.semantic_relations),
            evidence=tuple(_evidence(item) for item in model.evidence),
            metadata=model.resource_metadata,
            registered_by=model.registered_by,
            registered_at=model.registered_at,
            content_hash=model.content_hash,
        )

    @staticmethod
    def _schedule(model: EnterpriseScheduleModel) -> EnterpriseSchedule:
        return EnterpriseSchedule(
            id=model.id,
            organization_id=model.organization_id,
            schedule_key=model.schedule_key,
            work_type=model.work_type,
            priority=model.priority,
            target_resource_id=model.target_resource_id,
            target_resource_version=model.target_resource_version,
            dependencies=tuple(uuid.UUID(str(item)) for item in model.dependencies),
            required_approval_gate_ids=tuple(model.required_approval_gate_ids),
            capability_requirements=tuple(model.capability_requirements),
            resource_claims=tuple(_claim(item) for item in model.resource_claims),
            evidence=tuple(_evidence(item) for item in model.evidence),
            state=EnterpriseScheduleState(model.state),
            scheduled_by=model.scheduled_by,
            scheduled_at=model.scheduled_at,
            content_hash=model.content_hash,
        )


class SqlAlchemyEnterpriseKernelAuditSink:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, record: EnterpriseResourceAuditRecord) -> None:
        self._session.add(
            EnterpriseResourceAuditModel(
                event_type=record.event_type,
                resource_id=record.resource_id,
                actor_id=record.actor_id,
                occurred_at=record.occurred_at,
                payload=record.payload,
                payload_hash=record.payload_hash,
            )
        )
