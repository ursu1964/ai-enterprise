from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ai_enterprise.infrastructure.database.models import JobModel

RESOLUTION_KEY = "operator_resolution"


def job_resolution(job: JobModel) -> dict[str, Any] | None:
    value = job.payload.get(RESOLUTION_KEY)
    return value if isinstance(value, dict) else None


def job_is_acknowledged(job: JobModel) -> bool:
    resolution = job_resolution(job)
    return bool(resolution and resolution.get("state") == "acknowledged")


def unresolved_problem_jobs(jobs: list[JobModel]) -> list[JobModel]:
    return [
        job
        for job in jobs
        if job.status in {"failed", "dead_letter", "abandoned"} and not job_is_acknowledged(job)
    ]


def acknowledge_job(
    job: JobModel,
    *,
    actor_id: str,
    reason: str,
    action_taken: str,
    now: datetime | None = None,
) -> None:
    timestamp = now or datetime.now(UTC)
    payload = dict(job.payload)
    payload[RESOLUTION_KEY] = {
        "state": "acknowledged",
        "acknowledged_by": actor_id,
        "acknowledged_at": timestamp.isoformat(),
        "reason": reason,
        "action_taken": action_taken,
    }
    job.payload = payload
