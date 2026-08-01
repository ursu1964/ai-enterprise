from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.dto import (
    AuditActorResponse,
    AuditEventResponse,
    AuditTimelineResponse,
    IntegrityResponse,
    ProjectAuditSummaryResponse,
    ProjectProvenanceResponse,
)
from ai_enterprise.domain.audit.exceptions import AuditProjectNotFoundError
from ai_enterprise.domain.audit.policies import AuditCursor, sanitize_payload
from ai_enterprise.infrastructure.audit.audit_repository import AuditRepository
from ai_enterprise.infrastructure.audit.event_hasher import verify_hash_chain
from ai_enterprise.infrastructure.audit.provenance_builder import ProvenanceBuilder


class AuditQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._repository = AuditRepository(session)

    async def timeline(
        self, *, project_id: UUID, limit: int, cursor_value: str | None = None,
        aggregate_type: str | None = None, event_type: str | None = None,
    ) -> AuditTimelineResponse:
        await self._require_project(project_id)
        cursor = AuditCursor.decode(cursor_value) if cursor_value else None
        records = await self._repository.list_timeline(
            project_id=project_id, limit=limit, cursor=cursor,
            aggregate_type=aggregate_type, event_type=event_type,
        )
        has_more = len(records) > limit
        page = records[:limit]
        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = AuditCursor(last.occurred_at, last.sequence, last.id).encode()
        return AuditTimelineResponse(
            project_id=project_id,
            events=[AuditEventResponse(
                id=item.id, project_id=item.project_id,
                aggregate_type=item.aggregate_type, aggregate_id=item.aggregate_id,
                event_type=item.event_type, occurred_at=item.occurred_at,
                actor=AuditActorResponse(type=item.actor_type, id=item.actor_id),
                correlation_id=item.correlation_id, causation_id=item.causation_id,
                sequence=item.sequence, payload=sanitize_payload(item.payload),
            ) for item in page],
            next_cursor=next_cursor, has_more=has_more,
        )

    async def summary(self, project_id: UUID) -> ProjectAuditSummaryResponse:
        project = await self._require_project(project_id)
        lifecycle = await self._repository.lifecycle(project_id)
        executions = sorted(lifecycle["executions"], key=lambda item: item.created_at)
        reviews = sorted(lifecycle["reviews"], key=lambda item: item.created_at)
        execution = executions[-1] if executions else None
        review = reviews[-1] if reviews else None
        accepted = bool(
            execution and review and execution.status == "succeeded"
            and review.status == "accepted" and execution.patch_sha256
            and review.actual_patch_sha256 == execution.patch_sha256
        )
        event_count, artifact_count, approval_count = await self._repository.counts(project_id)
        return ProjectAuditSummaryResponse(
            project_id=project.id, project_name=project.name,
            manifest_sha256=project.manifest_hash,
            latest_execution_status=execution.status if execution else None,
            latest_review_status=review.status if review else None,
            candidate_patch_accepted=accepted, event_count=event_count,
            artifact_count=artifact_count, approval_count=approval_count,
        )

    async def provenance(self, project_id: UUID) -> ProjectProvenanceResponse:
        project = await self._require_project(project_id)
        lifecycle = await self._repository.lifecycle(project_id)
        return ProvenanceBuilder().build(project=project, **lifecycle)

    async def integrity(self, project_id: UUID) -> IntegrityResponse:
        timeline = await self.timeline(project_id=project_id, limit=10_000)
        events: list[dict[str, Any]] = [
            {"id": str(event.id), "event_type": event.event_type,
             "occurred_at": event.occurred_at.isoformat(), **event.payload}
            for event in timeline.events
        ]
        if any("event_hash" not in event for event in events):
            return IntegrityResponse(
                project_id=project_id, integrity_status="unsupported",
                event_count=len(events),
            )
        failures = verify_hash_chain(events)
        return IntegrityResponse(
            project_id=project_id, integrity_status="failed" if failures else "verified",
            event_count=len(events), failures=failures,
        )

    async def export_data(self, project_id: UUID) -> dict[str, Any]:
        summary = await self.summary(project_id)
        provenance = await self.provenance(project_id)
        timeline = await self.timeline(project_id=project_id, limit=10_000)
        return {
            "summary.json": summary.model_dump(mode="json"),
            "timeline.json": timeline.model_dump(mode="json"),
            "provenance.json": provenance.model_dump(mode="json"),
        }

    async def _require_project(self, project_id: UUID) -> Any:
        project = await self._repository.get_project(project_id)
        if project is None:
            raise AuditProjectNotFoundError(f"Project {project_id} not found")
        return project
