from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.audit.policies import AuditCursor
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    ExecutionEventModel,
    ExecutionRunModel,
    PatchReviewEventModel,
    PatchReviewRunModel,
    ProjectModel,
    WorkPackageModel,
)


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: UUID
    project_id: UUID
    aggregate_type: str
    aggregate_id: UUID
    event_type: str
    occurred_at: datetime
    actor_type: str
    actor_id: str | None
    correlation_id: UUID | None
    causation_id: UUID | None
    sequence: int
    payload: dict[str, Any]


def _uuid(value: Any) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except ValueError:
        return None


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_project(self, project_id: UUID) -> ProjectModel | None:
        return await self._session.get(ProjectModel, project_id)

    async def list_project_chain_records(self, project_id: UUID) -> list[AuditChainRecordModel]:
        records = await self._session.execute(
            select(AuditChainRecordModel)
            .where(AuditChainRecordModel.stream_id == f"project:{project_id}")
            .order_by(AuditChainRecordModel.sequence.asc())
        )
        return list(records.scalars().all())

    async def list_timeline(
        self, *, project_id: UUID, limit: int, cursor: AuditCursor | None,
        aggregate_type: str | None, event_type: str | None,
    ) -> list[AuditRecord]:
        records: list[AuditRecord] = []
        global_events = (await self._session.execute(
            select(AuditEventModel).where(AuditEventModel.project_id == project_id)
        )).scalars().all()
        for event in global_events:
            payload = dict(event.payload)
            aggregate_id = _uuid(payload.get("aggregate_id")) or project_id
            records.append(AuditRecord(
                event.id, project_id, str(payload.get("aggregate_type", "project")),
                aggregate_id, event.event_type, event.created_at, event.actor_type,
                event.actor_id, _uuid(payload.get("correlation_id")),
                _uuid(payload.get("causation_id")), int(payload.get("sequence", 0)), payload,
            ))

        execution_events = (await self._session.execute(
            select(ExecutionEventModel, ExecutionRunModel.project_id)
            .join(ExecutionRunModel, ExecutionRunModel.id == ExecutionEventModel.execution_run_id)
            .where(ExecutionRunModel.project_id == project_id)
        )).all()
        for event, event_project_id in execution_events:
            payload = dict(event.payload)
            records.append(AuditRecord(
                event.id, event_project_id, "execution_run", event.execution_run_id,
                event.event_type, event.occurred_at, str(payload.get("actor_type", "worker")),
                payload.get("actor_id"), _uuid(payload.get("correlation_id")),
                _uuid(payload.get("causation_id")), int(payload.get("sequence", 0)), payload,
            ))

        review_events = (await self._session.execute(
            select(PatchReviewEventModel, PatchReviewRunModel.project_id)
            .join(PatchReviewRunModel,
                  PatchReviewRunModel.id == PatchReviewEventModel.patch_review_run_id)
            .where(PatchReviewRunModel.project_id == project_id)
        )).all()
        for event, event_project_id in review_events:
            payload = dict(event.payload)
            records.append(AuditRecord(
                event.id, event_project_id, "patch_review_run", event.patch_review_run_id,
                event.event_type, event.occurred_at, str(payload.get("actor_type", "worker")),
                payload.get("actor_id"), _uuid(payload.get("correlation_id")),
                _uuid(payload.get("causation_id")), int(payload.get("sequence", 0)), payload,
            ))

        records.sort(key=lambda item: (item.occurred_at, item.sequence, item.id))
        if aggregate_type:
            records = [item for item in records if item.aggregate_type == aggregate_type]
        if event_type:
            records = [item for item in records if item.event_type == event_type]
        if cursor:
            marker = (cursor.occurred_at, cursor.sequence, cursor.event_id)
            records = [
                item for item in records
                if (item.occurred_at, item.sequence, item.id) > marker
            ]
        return records[: limit + 1]

    async def lifecycle(self, project_id: UUID) -> dict[str, Any]:
        async def rows(model: Any) -> list[Any]:
            return list((await self._session.execute(
                select(model).where(model.project_id == project_id)
            )).scalars().all())

        return {
            "artifacts": await rows(ArtifactModel),
            "crew_runs": await rows(CrewRunModel),
            "approvals": await rows(ApprovalModel),
            "work_packages": await rows(WorkPackageModel),
            "executions": await rows(ExecutionRunModel),
            "reviews": await rows(PatchReviewRunModel),
        }

    async def counts(self, project_id: UUID) -> tuple[int, int, int]:
        async def count(model: Any) -> int:
            value = await self._session.scalar(
                select(func.count()).select_from(model).where(model.project_id == project_id)
            )
            return int(value or 0)

        event_count = await count(AuditEventModel)
        event_count += len(await self.list_timeline(
            project_id=project_id, limit=1_000_000, cursor=None,
            aggregate_type="execution_run", event_type=None,
        ))
        event_count += len(await self.list_timeline(
            project_id=project_id, limit=1_000_000, cursor=None,
            aggregate_type="patch_review_run", event_type=None,
        ))
        return event_count, await count(ArtifactModel), await count(ApprovalModel)
