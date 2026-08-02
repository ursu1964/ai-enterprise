import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_enterprise.api.routes.operator_jobs import router
from ai_enterprise.application.operator_job_resolution import acknowledge_job, job_is_acknowledged
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.jobs.crash_safety import (
    FailureClass,
    LeaseLostError,
    RetryPolicy,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository


def test_retry_policy_classifies_and_caps_backoff() -> None:
    policy = RetryPolicy(base_seconds=10, maximum_seconds=45)

    timeout = policy.classify(TimeoutError("deadline"))
    denied = policy.classify(PermissionError("denied"))

    assert timeout.failure_class is FailureClass.TEMPORARY_PROVIDER
    assert timeout.retryable is True
    assert denied.failure_class is FailureClass.AUTHORIZATION
    assert denied.retryable is False
    assert policy.delay(1) == timedelta(seconds=10)
    assert policy.delay(9) == timedelta(seconds=45)


@pytest.mark.asyncio
async def test_stale_worker_cannot_commit_success_after_lease_reassignment() -> None:
    session = AsyncMock()
    fenced_result = MagicMock()
    fenced_result.rowcount = 0
    session.execute.return_value = fenced_result
    repository = JobRepository(session)

    with pytest.raises(LeaseLostError):
        await repository.mark_succeeded(
            job_id=uuid.uuid4(),
            worker_id="stale-worker",
            lease_token=uuid.uuid4(),
            lease_version=1,
        )


def test_operator_recovery_and_visibility_routes_are_registered() -> None:
    paths = {route.path for route in router.routes}

    assert "/operator/jobs/recover-expired" in paths
    assert "/operator/jobs" in paths
    assert "/operator/jobs/by-id/{job_id}/acknowledge" in paths
    assert "/operator/jobs/by-id/{job_id}/attempts" in paths
    assert "/operator/jobs/worker-instances" in paths


def test_acknowledged_dead_letter_keeps_evidence_but_marks_resolution() -> None:
    job = JobModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        run_id=None,
        job_type="plan_work_package",
        status="dead_letter",
        payload={"original": "evidence"},
        priority=100,
        attempt_count=3,
        max_attempts=3,
        retry_count=0,
        available_at=datetime.now(UTC),
        lease_owner=None,
        lease_expires_at=None,
        lease_token=None,
        lease_version=0,
        last_failure_class="validation",
        last_leased_at=None,
        last_error="historical failure",
        completed_at=None,
    )

    acknowledge_job(
        job,
        actor_id="operator",
        reason="Historical failed experiment already reviewed.",
        action_taken="Preserved as evidence and excluded from current health.",
    )

    assert job.payload["original"] == "evidence"
    assert job_is_acknowledged(job) is True
    assert job.payload["operator_resolution"]["acknowledged_by"] == "operator"
