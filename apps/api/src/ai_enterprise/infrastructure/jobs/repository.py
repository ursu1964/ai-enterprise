import uuid
from collections.abc import Collection, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import JobStatus
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.jobs.crash_safety import LeaseLostError
from ai_enterprise.infrastructure.jobs.models import JobExecutionAttemptModel
from ai_enterprise.infrastructure.requirements_revision.models import (
    RequirementsRevisionCycleModel,
)


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

    async def record_setup_blockers(
        self,
        *,
        candidate_job_types: Collection[str],
        blockers: Mapping[str, str],
    ) -> None:
        """Expose current setup blockers without leasing work or consuming an attempt."""
        if not candidate_job_types:
            return
        jobs = (
            await self._session.scalars(
                select(JobModel).where(
                    JobModel.job_type.in_(tuple(candidate_job_types)),
                    JobModel.status.in_((JobStatus.QUEUED, JobStatus.RETRY_WAIT)),
                )
            )
        ).all()
        appended_marker = "\nCurrent Setup blocker ["
        for job in jobs:
            blocker = blockers.get(job.job_type)
            if blocker is not None:
                if job.last_error and not job.last_error.startswith("Setup blocker ["):
                    original_error = job.last_error.split(appended_marker, 1)[0]
                    job.last_error = f"{original_error}\nCurrent {blocker}"[:4000]
                else:
                    job.last_error = blocker[:4000]
                    job.last_failure_class = "configuration"
            elif job.last_error and job.last_error.startswith("Setup blocker ["):
                job.last_error = None
                job.last_failure_class = None
            elif job.last_error and appended_marker in job.last_error:
                job.last_error = job.last_error.split(appended_marker, 1)[0]
        await self._session.flush()

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta,
        allowed_job_types: Collection[str] | None = None,
        execution_timeout: timedelta = timedelta(minutes=30),
    ) -> JobModel | None:
        now = datetime.now(UTC)

        if allowed_job_types is not None and not allowed_job_types:
            return None

        filters = [
            JobModel.available_at <= now,
            JobModel.attempt_count < JobModel.max_attempts,
            or_(
                JobModel.status == JobStatus.QUEUED,
                JobModel.status == JobStatus.RETRY_WAIT,
            ),
            JobModel.lease_owner.is_(None),
            JobModel.lease_token.is_(None),
            JobModel.lease_expires_at.is_(None),
        ]
        if allowed_job_types is not None:
            filters.append(JobModel.job_type.in_(tuple(allowed_job_types)))

        statement = (
            select(JobModel)
            .where(*filters)
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
        job.lease_token = uuid.uuid4()
        job.lease_version += 1
        job.last_leased_at = now
        job.attempt_count += 1
        attempt = JobExecutionAttemptModel(
            id=uuid.uuid4(),
            job_id=job.id,
            attempt_number=job.attempt_count,
            worker_id=worker_id,
            lease_token=job.lease_token,
            lease_version=job.lease_version,
            status="running",
            started_at=now,
            deadline_at=now + execution_timeout,
            queue_wait_ms=max(0, int((now - job.created_at).total_seconds() * 1000)),
            revision_cycle_id=(
                uuid.UUID(str(job.payload["revision_cycle_id"]))
                if job.payload.get("revision_cycle_id")
                else None
            ),
            repair_attempted=False,
        )
        self._session.add(attempt)
        if attempt.revision_cycle_id is not None:
            cycle = await self._session.scalar(
                select(RequirementsRevisionCycleModel)
                .where(RequirementsRevisionCycleModel.id == attempt.revision_cycle_id)
                .with_for_update()
            )
            if cycle is None or cycle.status != "pending":
                raise RuntimeError("Revision cycle is not pending at lease acquisition")
            cycle.status = "executing"

        await self._session.flush()

        return job

    async def extend_lease(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        lease_token: uuid.UUID,
        lease_version: int,
        lease_duration: timedelta,
    ) -> bool:
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(JobModel)
                .where(
                    JobModel.id == job_id,
                    JobModel.status == JobStatus.LEASED,
                    JobModel.lease_owner == worker_id,
                    JobModel.lease_token == lease_token,
                    JobModel.lease_version == lease_version,
                    JobModel.lease_expires_at > now,
                )
                .values(lease_expires_at=now + lease_duration)
            ),
        )
        return bool(result.rowcount == 1)

    async def mark_succeeded(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        lease_token: uuid.UUID,
        lease_version: int,
    ) -> None:
        now = datetime.now(UTC)
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(JobModel)
                .where(*self._fence(job_id, worker_id, lease_token, lease_version, now))
                .values(
                    status=JobStatus.SUCCEEDED,
                    completed_at=now,
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                )
            ),
        )
        if result.rowcount != 1:
            raise LeaseLostError(f"Lease lost for job {job_id}")
        await self._finish_attempt(job_id, lease_token, "succeeded", now)

    async def mark_failed(
        self,
        *,
        job_id: uuid.UUID,
        worker_id: str,
        lease_token: uuid.UUID,
        lease_version: int,
        error: str,
        retry_delay: timedelta,
        failure_class: str = "unknown",
        failure_code: str = "execution_failed",
        retryable: bool = True,
        attempt_status: str = "failed",
    ) -> None:
        now = datetime.now(UTC)
        job = await self._session.scalar(
            select(JobModel)
            .where(*self._fence(job_id, worker_id, lease_token, lease_version, now))
            .with_for_update()
        )
        if job is None:
            raise LeaseLostError(f"Lease lost for job {job_id}")
        job.last_error = error[:4000]
        job.last_failure_class = failure_class
        job.lease_owner = None
        job.lease_token = None
        job.lease_expires_at = None
        exhausted = job.attempt_count >= job.max_attempts
        if not retryable or exhausted:
            job.status = JobStatus.DEAD_LETTER
            job.completed_at = now
        else:
            job.retry_count += 1
            job.status = JobStatus.RETRY_WAIT
            job.available_at = now + retry_delay
        await self._finish_attempt(
            job_id,
            lease_token,
            attempt_status,
            now,
            failure_class=failure_class,
            failure_code=failure_code,
            failure_message=error[:4000],
            retryable=retryable and not exhausted,
        )
        revision_cycle_id = job.payload.get("revision_cycle_id")
        if revision_cycle_id:
            cycle = await self._session.get(
                RequirementsRevisionCycleModel, uuid.UUID(str(revision_cycle_id))
            )
            if cycle is None:
                raise LeaseLostError("Revision cycle disappeared during failure finalization")
            cycle.status = "failed" if not retryable or exhausted else "pending"
            cycle.completed_at = now if cycle.status == "failed" else None
        await self._session.flush()

    @staticmethod
    def _fence(
        job_id: uuid.UUID,
        worker_id: str,
        lease_token: uuid.UUID,
        lease_version: int,
        now: datetime,
    ) -> tuple[Any, ...]:
        return (
            JobModel.id == job_id,
            JobModel.status == JobStatus.LEASED,
            JobModel.lease_owner == worker_id,
            JobModel.lease_token == lease_token,
            JobModel.lease_version == lease_version,
            JobModel.lease_expires_at > now,
        )

    async def _finish_attempt(
        self,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        status: str,
        now: datetime,
        *,
        failure_class: str | None = None,
        failure_code: str | None = None,
        failure_message: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        attempt = await self._session.scalar(
            select(JobExecutionAttemptModel).where(
                JobExecutionAttemptModel.job_id == job_id,
                JobExecutionAttemptModel.lease_token == lease_token,
            )
        )
        if attempt is None:
            raise LeaseLostError("Fenced execution attempt is missing")
        attempt.status = status
        attempt.completed_at = now
        attempt.execution_ms = max(0, int((now - attempt.started_at).total_seconds() * 1000))
        attempt.failure_class = failure_class
        attempt.failure_code = failure_code
        attempt.failure_message = failure_message
        attempt.retryable = retryable
