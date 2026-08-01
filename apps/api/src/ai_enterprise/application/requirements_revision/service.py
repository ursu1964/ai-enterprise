import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import ArtifactType, JobType, ProjectStatus, RunStatus
from ai_enterprise.domain.requirements_revision.models import RequirementsReviewDecision
from ai_enterprise.domain.requirements_revision.policies import (
    RequirementsRevisionError,
    RevisionFeedbackPolicy,
)
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.jobs.models import JobExecutionAttemptModel
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.requirements_revision.models import (
    RequirementsArtifactLineageModel,
    RequirementsRevisionCycleModel,
    RequirementsRevisionRequestModel,
)


class RequirementsRevisionService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def request_changes(
        self,
        *,
        project_id: uuid.UUID,
        requirements_run_id: uuid.UUID,
        artifact_id: uuid.UUID,
        reviewer: str,
        decision: RequirementsReviewDecision,
    ) -> RequirementsRevisionCycleModel:
        project = await self._session.scalar(
            select(ProjectModel).where(ProjectModel.id == project_id).with_for_update()
        )
        artifact = await self._session.scalar(
            select(ArtifactModel).where(
                ArtifactModel.id == artifact_id,
                ArtifactModel.project_id == project_id,
                ArtifactModel.artifact_type == ArtifactType.REQUIREMENTS_SPECIFICATION,
            )
        )
        if (
            project is None
            or artifact is None
            or artifact.run_id is None
            or artifact.run_id != requirements_run_id
        ):
            raise RequirementsRevisionError("Requirements artifact lineage was not found")
        if project.status != ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL:
            raise RequirementsRevisionError("Project is not awaiting requirements review")
        active = await self._session.scalar(
            select(RequirementsRevisionCycleModel).where(
                RequirementsRevisionCycleModel.requirements_run_id == artifact.run_id,
                RequirementsRevisionCycleModel.status.in_(("pending", "executing")),
            )
        )
        if active is not None:
            raise RequirementsRevisionError("Requirements run already has an active revision")

        feedback = RevisionFeedbackPolicy().create(
            artifact_id=artifact.id,
            artifact_hash=artifact.content_hash,
            decision=decision,
        )
        approval = ApprovalModel(
            id=uuid.uuid4(),
            project_id=project_id,
            artifact_id=artifact.id,
            decision="changes_requested",
            reviewer=reviewer,
            comment=decision.summary,
        )
        request = RequirementsRevisionRequestModel(
            id=uuid.uuid4(),
            project_id=project_id,
            requirements_run_id=artifact.run_id,
            source_artifact_id=artifact.id,
            source_review_decision_id=approval.id,
            requested_by=reviewer,
            feedback_summary=feedback.summary,
            feedback_items=list(feedback.findings),
            feedback_hash=feedback.feedback_hash,
        )
        cycle_number = (
            int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(RequirementsRevisionCycleModel)
                    .where(RequirementsRevisionCycleModel.requirements_run_id == artifact.run_id)
                )
                or 0
            )
            + 1
        )
        cycle = RequirementsRevisionCycleModel(
            id=uuid.uuid4(),
            requirements_run_id=artifact.run_id,
            revision_request_id=request.id,
            cycle_number=cycle_number,
            status="pending",
        )
        attempt = CrewRunModel(
            id=uuid.uuid4(),
            project_id=project_id,
            crew_name="requirements_crew",
            status=RunStatus.QUEUED,
            input_payload={
                "project_name": project.name,
                "project_description": project.description,
                "manifest_hash": project.manifest_hash,
                "revision_cycle_id": str(cycle.id),
                "revision_cycle_number": cycle_number,
                "previous_artifact_id": str(artifact.id),
                "previous_artifact_hash": artifact.content_hash,
                "revision_feedback_summary": feedback.summary,
                "revision_feedback": list(feedback.findings),
                "revision_feedback_hash": feedback.feedback_hash,
            },
        )
        project.status = ProjectStatus.REQUIREMENTS_QUEUED
        self._session.add_all([approval, request, cycle, attempt])
        await self._session.flush()
        await JobRepository(self._session).enqueue(
            project_id=project_id,
            run_id=attempt.id,
            job_type=JobType.RUN_REQUIREMENTS_CREW,
            payload={
                "project_id": str(project_id),
                "run_id": str(attempt.id),
                "revision_cycle_id": str(cycle.id),
            },
            priority=100,
            max_attempts=3,
        )
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project_id,
                event_type="requirements.revision.requested",
                actor_type="human",
                actor_id=reviewer,
                payload={
                    "source_artifact_id": str(artifact.id),
                    "source_review_decision_id": str(approval.id),
                    "revision_request_id": str(request.id),
                    "revision_cycle_id": str(cycle.id),
                    "execution_run_id": str(attempt.id),
                    "feedback_hash": feedback.feedback_hash,
                },
            )
        )
        await self._session.commit()
        return cycle

    async def list_revisions(
        self, requirements_run_id: uuid.UUID
    ) -> list[RequirementsRevisionCycleModel]:
        return list(
            (
                await self._session.scalars(
                    select(RequirementsRevisionCycleModel)
                    .where(
                        RequirementsRevisionCycleModel.requirements_run_id == requirements_run_id
                    )
                    .order_by(RequirementsRevisionCycleModel.cycle_number)
                )
            ).all()
        )

    async def list_artifact_history(
        self, requirements_run_id: uuid.UUID
    ) -> list[RequirementsArtifactLineageModel]:
        return list(
            (
                await self._session.scalars(
                    select(RequirementsArtifactLineageModel)
                    .join(
                        ArtifactModel,
                        ArtifactModel.id == RequirementsArtifactLineageModel.artifact_id,
                    )
                    .where(ArtifactModel.run_id == requirements_run_id)
                    .order_by(RequirementsArtifactLineageModel.version)
                )
            ).all()
        )

    async def complete_cycle(
        self,
        *,
        execution_run_id: uuid.UUID,
        artifact_id: uuid.UUID,
        raw_output_hash: str,
        repair_attempted: bool,
        repair_succeeded: bool | None,
        validation_errors: list[dict[str, object]] | None,
    ) -> None:
        execution_run = await self._session.get(CrewRunModel, execution_run_id)
        if execution_run is None:
            return
        cycle_id = execution_run.input_payload.get("revision_cycle_id")
        if not cycle_id:
            return
        cycle = await self._session.scalar(
            select(RequirementsRevisionCycleModel)
            .where(RequirementsRevisionCycleModel.id == uuid.UUID(str(cycle_id)))
            .with_for_update()
        )
        request = await self._session.get(
            RequirementsRevisionRequestModel, cycle.revision_request_id if cycle else None
        )
        if cycle is None or request is None or cycle.status not in {"pending", "executing"}:
            raise RequirementsRevisionError("Revision cycle is not completable")
        job_id = await self._session.scalar(
            select(JobModel.id).where(JobModel.run_id == execution_run_id)
        )
        execution_attempt = await self._session.scalar(
            select(JobExecutionAttemptModel)
            .where(
                JobExecutionAttemptModel.job_id == job_id,
                JobExecutionAttemptModel.revision_cycle_id == cycle.id,
            )
            .order_by(JobExecutionAttemptModel.attempt_number.desc())
            .limit(1)
        )
        if execution_attempt is not None:
            execution_attempt.raw_output_hash = raw_output_hash
            execution_attempt.repair_attempted = repair_attempted
            execution_attempt.repair_succeeded = repair_succeeded
            execution_attempt.validation_errors = validation_errors
        current_version = int(
            await self._session.scalar(
                select(RequirementsArtifactLineageModel.version).where(
                    RequirementsArtifactLineageModel.artifact_id == request.source_artifact_id
                )
            )
            or 1
        )
        cycle.status = "completed"
        cycle.resulting_artifact_id = artifact_id
        cycle.completed_at = datetime.now(UTC)
        self._session.add(
            RequirementsArtifactLineageModel(
                id=uuid.uuid4(),
                artifact_id=artifact_id,
                revision_cycle_id=cycle.id,
                previous_artifact_id=request.source_artifact_id,
                version=current_version + 1,
                revision_feedback_hash=request.feedback_hash,
            )
        )

    async def record_initial_artifact(self, artifact_id: uuid.UUID) -> None:
        existing = await self._session.scalar(
            select(RequirementsArtifactLineageModel).where(
                RequirementsArtifactLineageModel.artifact_id == artifact_id
            )
        )
        if existing is None:
            self._session.add(
                RequirementsArtifactLineageModel(
                    id=uuid.uuid4(),
                    artifact_id=artifact_id,
                    revision_cycle_id=None,
                    previous_artifact_id=None,
                    version=1,
                    revision_feedback_hash=None,
                )
            )
