import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_enterprise.api.routes.operator_jobs import router
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
    assert "/operator/jobs/by-id/{job_id}/attempts" in paths
    assert "/operator/jobs/worker-instances" in paths
