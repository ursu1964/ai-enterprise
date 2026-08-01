from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.jobs.profiles import (
    GENERAL_JOB_TYPES,
    INTEGRATION_JOB_TYPES,
    RECOVERY_JOB_TYPES,
    WorkerProfile,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.worker import run_worker


def test_general_and_integration_job_profiles_are_disjoint() -> None:
    assert GENERAL_JOB_TYPES.isdisjoint(INTEGRATION_JOB_TYPES)
    assert JobType.INTEGRATE_APPROVED_PATCH not in GENERAL_JOB_TYPES
    assert INTEGRATION_JOB_TYPES == {JobType.INTEGRATE_APPROVED_PATCH}
    assert RECOVERY_JOB_TYPES == {JobType.RECOVER_INTEGRATION}
    assert RECOVERY_JOB_TYPES.isdisjoint(GENERAL_JOB_TYPES)
    assert RECOVERY_JOB_TYPES.isdisjoint(INTEGRATION_JOB_TYPES)


@pytest.mark.asyncio
async def test_claim_query_is_filtered_to_general_job_types() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    claimed = await JobRepository(session).claim_next(
        worker_id="general-worker",
        lease_duration=timedelta(seconds=30),
        allowed_job_types=GENERAL_JOB_TYPES,
    )

    assert claimed is None
    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "jobs.job_type IN" in sql
    assert JobType.EXECUTE_WORK_PACKAGE.value in sql
    assert JobType.INTEGRATE_APPROVED_PATCH.value not in sql


@pytest.mark.asyncio
async def test_claim_query_is_filtered_to_integration_job_type() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    await JobRepository(session).claim_next(
        worker_id="integration-worker",
        lease_duration=timedelta(seconds=30),
        allowed_job_types=INTEGRATION_JOB_TYPES,
    )

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert JobType.INTEGRATE_APPROVED_PATCH.value in sql
    assert JobType.EXECUTE_WORK_PACKAGE.value not in sql


@pytest.mark.asyncio
async def test_empty_profile_cannot_claim_any_job() -> None:
    session = AsyncMock()
    claimed = await JobRepository(session).claim_next(
        worker_id="unconfigured-worker",
        lease_duration=timedelta(seconds=30),
        allowed_job_types=(),
    )
    assert claimed is None
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_integration_worker_fails_before_claim_without_processor() -> None:
    with pytest.raises(RuntimeError, match="credential broker"):
        await run_worker(profile=WorkerProfile.INTEGRATION)


@pytest.mark.asyncio
async def test_recovery_worker_fails_before_claim_without_processor() -> None:
    with pytest.raises(RuntimeError, match="restricted credential broker"):
        await run_worker(profile=WorkerProfile.RECOVERY)


@pytest.mark.asyncio
async def test_claim_query_is_filtered_to_recovery_job_type() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    await JobRepository(session).claim_next(
        worker_id="recovery-worker",
        lease_duration=timedelta(seconds=30),
        allowed_job_types=RECOVERY_JOB_TYPES,
    )

    statement = session.execute.await_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert JobType.RECOVER_INTEGRATION.value in sql
    assert JobType.INTEGRATE_APPROVED_PATCH.value not in sql
    assert JobType.EXECUTE_WORK_PACKAGE.value not in sql
