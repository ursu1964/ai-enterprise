import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.application.operator_job_resolution import acknowledge_job, job_resolution
from ai_enterprise.infrastructure.database.models import AuditEventModel, JobModel
from ai_enterprise.infrastructure.jobs.crash_safety import RetryPolicy
from ai_enterprise.infrastructure.jobs.models import JobExecutionAttemptModel, WorkerInstanceModel
from ai_enterprise.infrastructure.jobs.recovery import JobRecoveryService

router = APIRouter(prefix="/operator/jobs", tags=["operator-jobs"])


class AcknowledgeJobRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=1_000)
    action_taken: str = Field(min_length=5, max_length=1_000)


def _require_operator(actor: ActorDependency) -> None:
    if actor.actor_type != "human" or actor.role not in {
        "operator",
        "administrator",
        "admin",
        "platform-admin",
        "platform_administrator",
    }:
        raise HTTPException(status_code=403, detail="Human operator authority is required")


@router.post("/recover-expired")
async def recover_expired(
    session: SessionDependency,
    actor: ActorDependency,
    settings: SettingsDependency,
) -> dict[str, int]:
    _require_operator(actor)
    summary = await JobRecoveryService(
        session,
        RetryPolicy(
            base_seconds=settings.worker_retry_base_seconds,
            maximum_seconds=settings.worker_retry_maximum_seconds,
        ),
    ).recover_expired(
        stale_worker_after=timedelta(seconds=settings.worker_stale_after_seconds)
    )
    await session.commit()
    return {
        "workers_marked_offline": summary.workers_marked_offline,
        "jobs_recovered": summary.jobs_recovered,
        "jobs_dead_lettered": summary.jobs_dead_lettered,
        "attempts_abandoned": summary.attempts_abandoned,
    }


@router.get("")
async def list_jobs(
    session: SessionDependency,
    actor: ActorDependency,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    _require_operator(actor)
    statement = select(JobModel).order_by(JobModel.created_at.desc()).limit(limit)
    if status is not None:
        statement = statement.where(JobModel.status == status)
    jobs = (await session.scalars(statement)).all()
    return [
        {
            "id": job.id,
            "project_id": job.project_id,
            "job_type": job.job_type,
            "status": job.status,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "retry_count": job.retry_count,
            "available_at": job.available_at,
            "lease_owner": job.lease_owner,
            "lease_expires_at": job.lease_expires_at,
            "last_failure_class": job.last_failure_class,
            "last_error": job.last_error,
            "operator_resolution": job_resolution(job),
        }
        for job in jobs
    ]


@router.post("/by-id/{job_id}/acknowledge")
async def acknowledge(
    job_id: uuid.UUID,
    request: AcknowledgeJobRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _require_operator(actor)
    job = await session.get(JobModel, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status not in {"failed", "dead_letter", "abandoned"}:
        raise HTTPException(409, "Only failed or dead-letter jobs can be acknowledged")
    acknowledge_job(
        job,
        actor_id=actor.subject,
        reason=request.reason,
        action_taken=request.action_taken,
    )
    session.add(
        AuditEventModel(
            project_id=job.project_id,
            event_type="operator.job_acknowledged",
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            payload={
                "job_id": str(job.id),
                "job_type": job.job_type,
                "status": job.status,
                "reason": request.reason,
                "action_taken": request.action_taken,
            },
        )
    )
    await session.commit()
    return {
        "job_id": job.id,
        "status": job.status,
        "operator_resolution": job_resolution(job),
    }


@router.get("/by-id/{job_id}/attempts")
async def list_attempts(
    job_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _require_operator(actor)
    attempts = (
        await session.scalars(
            select(JobExecutionAttemptModel)
            .where(JobExecutionAttemptModel.job_id == job_id)
            .order_by(JobExecutionAttemptModel.attempt_number.asc())
        )
    ).all()
    return [
        {
            "id": attempt.id,
            "attempt_number": attempt.attempt_number,
            "worker_id": attempt.worker_id,
            "lease_version": attempt.lease_version,
            "status": attempt.status,
            "started_at": attempt.started_at,
            "deadline_at": attempt.deadline_at,
            "completed_at": attempt.completed_at,
            "queue_wait_ms": attempt.queue_wait_ms,
            "execution_ms": attempt.execution_ms,
            "failure_class": attempt.failure_class,
            "failure_code": attempt.failure_code,
            "retryable": attempt.retryable,
        }
        for attempt in attempts
    ]


@router.get("/worker-instances")
async def list_workers(
    session: SessionDependency, actor: ActorDependency
) -> list[dict[str, object]]:
    _require_operator(actor)
    workers = (
        await session.scalars(
            select(WorkerInstanceModel).order_by(WorkerInstanceModel.started_at.desc())
        )
    ).all()
    return [
        {
            "worker_id": worker.worker_id,
            "profile": worker.profile,
            "status": worker.status,
            "started_at": worker.started_at,
            "last_heartbeat_at": worker.last_heartbeat_at,
            "stopped_at": worker.stopped_at,
        }
        for worker in workers
    ]
