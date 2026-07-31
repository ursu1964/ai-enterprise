import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import JobStatus
from ai_enterprise.infrastructure.database.models import JobModel


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        *,
        project_id: uuid.UUID,
        run_id: uuid.UUID | None,
        job_type: str,
        payload: dict[str, Any],
        priority: int = 100,
        max_attempts: int = 3,
    ) -> JobModel:
        job = JobModel(
            id=uuid.uuid4(),
            project_id=project_id,
            run_id=run_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            payload=payload,
            priority=priority,
            max_attempts=max_attempts,
        )

        self._session.add(job)
        await self._session.flush()

        return job

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta,
    ) -> JobModel | None:
        now = datetime.now(UTC)

        statement = (
            select(JobModel)
            .where(
                JobModel.available_at <= now,
                JobModel.attempt_count < JobModel.max_attempts,
                or_(
                    JobModel.status == JobStatus.QUEUED,
                    (
                        (JobModel.status == JobStatus.LEASED)
                        & (JobModel.lease_expires_at < now)
                    ),
                ),
            )
            .order_by(
                JobModel.priority.asc(),
                JobModel.created_at.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        result = await self._session.execute(statement)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        job.status = JobStatus.LEASED
        job.lease_owner = worker_id
        job.lease_expires_at = now + lease_duration
        job.attempt_count += 1

        await self._session.flush()

        return job

    async def extend_lease(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        lease_duration: timedelta,
    ) -> bool:
        job = await self._session.get(JobModel, job_id)

        if (
            job is None
            or job.status != JobStatus.LEASED
            or job.lease_owner != worker_id
        ):
            return False

        job.lease_expires_at = datetime.now(UTC) + lease_duration
        await self._session.flush()

        return True

    async def mark_succeeded(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
    ) -> None:
        job = await self._session.get(JobModel, job_id)

        if job is None:
            raise RuntimeError(f"Job {job_id} does not exist")

        if job.lease_owner != worker_id:
            raise RuntimeError(
                f"Worker {worker_id} does not own job {job_id}"
            )

        job.status = JobStatus.SUCCEEDED
        job.completed_at = datetime.now(UTC)
        job.lease_owner = None
        job.lease_expires_at = None

        await self._session.flush()

    async def mark_failed(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        error: str,
        retry_delay: timedelta,
    ) -> None:
        job = await self._session.get(JobModel, job_id)

        if job is None:
            raise RuntimeError(f"Job {job_id} does not exist")

        if job.lease_owner != worker_id:
            raise RuntimeError(
                f"Worker {worker_id} does not own job {job_id}"
            )

        job.last_error = error
        job.lease_owner = None
        job.lease_expires_at = None

        if job.attempt_count >= job.max_attempts:
            job.status = JobStatus.DEAD_LETTER
            job.completed_at = datetime.now(UTC)
        else:
            job.status = JobStatus.QUEUED
            job.available_at = datetime.now(UTC) + retry_delay

        await self._session.flush()
