import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    architecture_provider_ready,
)
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.jobs.dispatcher import JobDispatcher


@pytest.mark.asyncio
async def test_governed_architecture_job_uses_trusted_worker_entry(monkeypatch) -> None:
    handle = AsyncMock()

    class FakeEntry:
        def __init__(self, session, settings) -> None:
            pass

        async def handle(self, run_id: uuid.UUID) -> None:
            await handle(run_id)

    monkeypatch.setattr(
        "ai_enterprise.infrastructure.jobs.dispatcher.ArchitectureWorkerEntry", FakeEntry
    )
    run_id = uuid.uuid4()
    job = MagicMock(spec=JobModel)
    job.job_type = JobType.RUN_ARCHITECTURE_CREW
    job.payload = {"run_id": str(run_id), "governed_architecture_run": True}
    await JobDispatcher(session=AsyncMock(), settings=Settings()).dispatch(job)
    handle.assert_awaited_once_with(run_id)


@pytest.mark.asyncio
async def test_scripted_provider_is_ready_without_network() -> None:
    assert await architecture_provider_ready(
        ArchitectureProviderConfig(provider="scripted")
    )
    assert not await architecture_provider_ready(
        ArchitectureProviderConfig(provider="unsupported")
    )
