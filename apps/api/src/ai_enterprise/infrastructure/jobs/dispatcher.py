import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.architecture_execution import ArchitectureWorkerEntry
from ai_enterprise.application.decomposition_service import DecompositionService
from ai_enterprise.application.execution_workflow import (
    ExecutionApplicationService,
)
from ai_enterprise.application.integration.processor import IntegrationWorkerEntry
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.application.recovery.processor import RecoveryWorkerEntry
from ai_enterprise.application.review.service import (
    ReviewCandidatePatchService,
)
from ai_enterprise.application.workflow.service import WorkflowService
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.decomposition.crewai_provider import CrewAIDecompositionProvider


class JobDispatcher:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        integration_entry: IntegrationWorkerEntry | None = None,
        recovery_entry: RecoveryWorkerEntry | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._integration_entry = integration_entry
        self._recovery_entry = recovery_entry

    async def dispatch(self, job: JobModel) -> None:
        if job.job_type == JobType.ADVANCE_WORKFLOW:
            await WorkflowService(self._session, self._settings).advance(
                self._required_uuid(job, "workflow_id")
            )
            return

        service = ProjectWorkflowService(
            session=self._session,
            settings=self._settings,
        )

        if job.job_type == JobType.RUN_REQUIREMENTS_CREW:
            await service.execute_requirements_run(run_id=self._required_uuid(job, "run_id"))
            await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.RUN_ARCHITECTURE_CREW:
            if job.payload.get("governed_architecture_run") is True:
                await ArchitectureWorkerEntry(self._session, self._settings).handle(
                    self._required_uuid(job, "run_id")
                )
            else:
                await service.execute_architecture_run(run_id=self._required_uuid(job, "run_id"))
                await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.RUN_WORK_PACKAGE_DECOMPOSITION:
            provider = CrewAIDecompositionProvider(
                model_name=self._settings.decomposition_model_name,
                base_url=self._settings.decomposition_model_base_url,
                temperature=self._settings.decomposition_temperature,
                timeout_seconds=self._settings.decomposition_timeout_seconds,
                max_tokens=self._settings.decomposition_max_tokens,
            )
            await DecompositionService(
                self._session, snapshots_root=self._settings.decomposition_snapshots_root
            ).execute(self._required_uuid(job, "decomposition_run_id"), provider)
            return

        if job.job_type == JobType.PLAN_WORK_PACKAGE:
            await service.execute_work_package_planning(run_id=self._required_uuid(job, "run_id"))
            await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.EXECUTE_WORK_PACKAGE:
            execution_service = ExecutionApplicationService(
                session=self._session,
                settings=self._settings,
            )

            await execution_service.execute_work_package(
                execution_id=self._required_uuid(job, "execution_id")
            )
            await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.REVIEW_CANDIDATE_PATCH:
            review_service = ReviewCandidatePatchService(
                session=self._session,
                settings=self._settings,
            )

            await review_service.review_candidate_patch(
                review_id=self._required_uuid(job, "review_id")
            )
            await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.INTEGRATE_APPROVED_PATCH:
            if self._integration_entry is None:
                raise RuntimeError(
                    "Integration processor requires an explicitly configured "
                    "credential broker and rollback metadata hook"
                )
            await self._integration_entry.handle(self._required_uuid(job, "integration_attempt_id"))
            await WorkflowService(self._session, self._settings).notify(job.project_id)
            return

        if job.job_type == JobType.RECOVER_INTEGRATION:
            if self._recovery_entry is None:
                raise RuntimeError(
                    "Recovery processor requires an explicitly configured "
                    "restricted credential broker"
                )
            await self._recovery_entry.handle(self._required_uuid(job, "recovery_attempt_id"))
            return

        raise RuntimeError(f"Unsupported job type: {job.job_type}")

    @staticmethod
    def _required_uuid(
        job: JobModel,
        field_name: str,
    ) -> uuid.UUID:
        raw_value = job.payload.get(field_name)

        if not raw_value:
            raise RuntimeError(f"Job {job.id} is missing payload field {field_name}")

        try:
            return uuid.UUID(str(raw_value))
        except ValueError as exc:
            raise RuntimeError(f"Job {job.id} has invalid UUID in {field_name}") from exc
