import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.execution_workflow import (
    ExecutionApplicationService,
)
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.database.models import JobModel


class JobDispatcher:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._session = session
        self._settings = settings

    async def dispatch(self, job: JobModel) -> None:
        service = ProjectWorkflowService(
            session=self._session,
            settings=self._settings,
        )

        if job.job_type == JobType.RUN_REQUIREMENTS_CREW:
            await service.execute_requirements_run(
                run_id=self._required_uuid(job, "run_id")
            )
            return

        if job.job_type == JobType.RUN_ARCHITECTURE_CREW:
            await service.execute_architecture_run(
                run_id=self._required_uuid(job, "run_id")
            )
            return

        if job.job_type == JobType.PLAN_WORK_PACKAGE:
            await service.execute_work_package_planning(
                run_id=self._required_uuid(job, "run_id")
            )
            return

        if job.job_type == JobType.EXECUTE_WORK_PACKAGE:
            execution_service = ExecutionApplicationService(
                session=self._session,
                settings=self._settings,
            )

            await execution_service.execute_work_package(
                execution_id=self._required_uuid(job, "execution_id")
            )
            return

        raise RuntimeError(f"Unsupported job type: {job.job_type}")

    @staticmethod
    def _required_uuid(
        job: JobModel,
        field_name: str,
    ) -> uuid.UUID:
        raw_value = job.payload.get(field_name)

        if not raw_value:
            raise RuntimeError(
                f"Job {job.id} is missing payload field {field_name}"
            )

        try:
            return uuid.UUID(str(raw_value))
        except ValueError as exc:
            raise RuntimeError(
                f"Job {job.id} has invalid UUID in {field_name}"
            ) from exc
