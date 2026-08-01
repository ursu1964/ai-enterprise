from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import JobStatus
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.jobs.crash_safety import FailureClass, RetryPolicy
from ai_enterprise.infrastructure.jobs.models import (
    JobExecutionAttemptModel,
    WorkerInstanceModel,
)
from ai_enterprise.infrastructure.requirements_revision.models import (
    RequirementsRevisionCycleModel,
)


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    workers_marked_offline: int = 0
    jobs_recovered: int = 0
    jobs_dead_lettered: int = 0
    attempts_abandoned: int = 0


class JobRecoveryService:
    def __init__(self, session: AsyncSession, retry_policy: RetryPolicy) -> None:
        self._session = session
        self._retry_policy = retry_policy

    async def recover_expired(
        self,
        *,
        stale_worker_after: timedelta,
        limit: int = 100,
    ) -> RecoverySummary:
        now = datetime.now(UTC)
        stale_workers = (
            await self._session.scalars(
                select(WorkerInstanceModel)
                .where(
                    WorkerInstanceModel.status.in_(("online", "degraded")),
                    WorkerInstanceModel.last_heartbeat_at < now - stale_worker_after,
                )
                .with_for_update(skip_locked=True)
            )
        ).all()
        for worker in stale_workers:
            worker.status = "offline"
            worker.stopped_at = now

        jobs = (
            await self._session.scalars(
                select(JobModel)
                .where(
                    JobModel.status == JobStatus.LEASED,
                    JobModel.lease_expires_at <= now,
                )
                .order_by(JobModel.lease_expires_at.asc())
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).all()
        recovered = 0
        dead_lettered = 0
        abandoned = 0
        for job in jobs:
            token = job.lease_token
            if token is None:
                continue
            attempt = await self._session.scalar(
                select(JobExecutionAttemptModel)
                .where(
                    JobExecutionAttemptModel.job_id == job.id,
                    JobExecutionAttemptModel.lease_token == token,
                    JobExecutionAttemptModel.status == "running",
                )
                .with_for_update()
            )
            exhausted = job.attempt_count >= job.max_attempts
            if attempt is not None:
                attempt.status = "abandoned"
                attempt.completed_at = now
                attempt.execution_ms = max(
                    0, int((now - attempt.started_at).total_seconds() * 1000)
                )
                attempt.failure_class = FailureClass.INFRASTRUCTURE
                attempt.failure_code = "worker_lease_expired"
                attempt.failure_message = "Worker lease expired before completion"
                attempt.retryable = not exhausted
                abandoned += 1
            job.lease_owner = None
            job.lease_token = None
            job.lease_expires_at = None
            job.last_error = "Worker lease expired before completion"
            job.last_failure_class = FailureClass.INFRASTRUCTURE
            if exhausted:
                job.status = JobStatus.DEAD_LETTER
                job.completed_at = now
                dead_lettered += 1
            else:
                job.retry_count += 1
                job.status = JobStatus.RETRY_WAIT
                job.available_at = now + self._retry_policy.delay(job.retry_count)
                recovered += 1
            revision_cycle_id = job.payload.get("revision_cycle_id")
            if revision_cycle_id:
                cycle = await self._session.get(
                    RequirementsRevisionCycleModel, uuid.UUID(str(revision_cycle_id))
                )
                if cycle is not None:
                    cycle.status = "failed" if exhausted else "pending"
                    cycle.completed_at = now if exhausted else None

        await self._session.flush()
        return RecoverySummary(
            workers_marked_offline=len(stale_workers),
            jobs_recovered=recovered,
            jobs_dead_lettered=dead_lettered,
            attempts_abandoned=abandoned,
        )


class WorkerRegistry:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def register(self, *, worker_id: str, profile: str) -> None:
        now = datetime.now(UTC)
        worker = await self._session.scalar(
            select(WorkerInstanceModel)
            .where(WorkerInstanceModel.worker_id == worker_id)
            .with_for_update()
        )
        if worker is None:
            worker = WorkerInstanceModel(
                id=uuid.uuid4(),
                worker_id=worker_id,
                profile=profile,
                status="online",
                started_at=now,
                last_heartbeat_at=now,
            )
            self._session.add(worker)
        else:
            worker.profile = profile
            worker.status = "online"
            worker.started_at = now
            worker.last_heartbeat_at = now
            worker.stopped_at = None

    async def heartbeat(self, worker_id: str) -> bool:
        worker = await self._session.scalar(
            select(WorkerInstanceModel).where(
                WorkerInstanceModel.worker_id == worker_id,
                WorkerInstanceModel.status.in_(("online", "degraded")),
            )
        )
        if worker is None:
            return False
        worker.last_heartbeat_at = datetime.now(UTC)
        return True

    async def stop(self, worker_id: str) -> None:
        worker = await self._session.scalar(
            select(WorkerInstanceModel).where(WorkerInstanceModel.worker_id == worker_id)
        )
        if worker is not None:
            worker.status = "offline"
            worker.stopped_at = datetime.now(UTC)
