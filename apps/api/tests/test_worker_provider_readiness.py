import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from docker.errors import DockerException

from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobStatus, JobType
from ai_enterprise.infrastructure.database.models import JobModel
from ai_enterprise.infrastructure.jobs import readiness as readiness_module
from ai_enterprise.infrastructure.jobs.readiness import (
    WorkerReadinessCache,
    assess_worker_readiness,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.worker import _report_setup_blocker_changes


@pytest.mark.asyncio
async def test_unavailable_model_capabilities_are_removed_before_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unavailable(_config: object) -> bool:
        return False

    monkeypatch.setattr(readiness_module, "architecture_provider_ready", unavailable)
    candidates = frozenset(
        {
            JobType.ADVANCE_WORKFLOW,
            JobType.RUN_ARCHITECTURE_CREW,
            JobType.RUN_WORK_PACKAGE_DECOMPOSITION,
            JobType.PLAN_WORK_PACKAGE,
        }
    )

    result = await assess_worker_readiness(
        Settings(architecture_provider="crewai-ollama", _env_file=None), candidates
    )

    assert result.permitted_job_types == {JobType.ADVANCE_WORKFLOW}
    assert {blocker.code for blocker in result.blockers} == {
        "architecture_provider_unavailable",
        "decomposition_provider_unavailable",
        "planning_provider_unavailable",
    }
    assert all("Next:" in blocker.evidence for blocker in result.blockers)


@pytest.mark.asyncio
async def test_unconfigured_restricted_executor_blocks_execution_without_docker_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    docker_probe = MagicMock(side_effect=AssertionError("docker must not be probed"))
    monkeypatch.setattr(readiness_module, "from_env", docker_probe)
    candidates = frozenset(
        {
            JobType.ADVANCE_WORKFLOW,
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.REVIEW_CANDIDATE_PATCH,
        }
    )

    result = await assess_worker_readiness(Settings(_env_file=None), candidates)

    assert result.permitted_job_types == {JobType.ADVANCE_WORKFLOW}
    assert len(result.blockers) == 1
    blocker = result.blockers[0]
    assert blocker.code == "restricted_executor_unconfigured"
    assert blocker.capability == "container_execution"
    assert "restricted-local-docker" in blocker.next_action
    docker_probe.assert_not_called()


@pytest.mark.asyncio
async def test_approved_provider_still_blocks_unavailable_docker_without_host_socket_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> object:
        raise DockerException("not configured")

    monkeypatch.setattr(readiness_module, "from_env", unavailable)
    candidates = frozenset(
        {
            JobType.ADVANCE_WORKFLOW,
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.REVIEW_CANDIDATE_PATCH,
        }
    )

    result = await assess_worker_readiness(
        Settings(execution_container_provider="restricted-local-docker", _env_file=None),
        candidates,
    )

    assert result.permitted_job_types == {JobType.ADVANCE_WORKFLOW}
    assert len(result.blockers) == 1
    blocker = result.blockers[0]
    assert blocker.code == "docker_runtime_unavailable"
    assert "do not expose an unrestricted host Docker socket" in blocker.next_action


@pytest.mark.asyncio
async def test_approved_provider_requires_configured_immutable_image_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.ping.return_value = None
    monkeypatch.setattr(readiness_module, "from_env", MagicMock(return_value=client))
    candidates = frozenset(
        {
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.REVIEW_CANDIDATE_PATCH,
        }
    )

    result = await assess_worker_readiness(
        Settings(execution_container_provider="restricted-local-docker", _env_file=None),
        candidates,
    )

    assert result.permitted_job_types == frozenset()
    assert {blocker.code for blocker in result.blockers} == {
        "execute_work_package_image_id_unconfigured",
        "review_candidate_patch_image_id_unconfigured",
    }
    client.images.get.assert_not_called()


@pytest.mark.asyncio
async def test_approved_provider_requires_images_to_match_immutable_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_id = "sha256:" + "a" * 64
    review_id = "sha256:" + "b" * 64
    client = MagicMock()
    client.ping.return_value = None
    client.images.get.side_effect = [
        MagicMock(id=execution_id, attrs={"Id": execution_id}),
        MagicMock(id="sha256:" + "c" * 64, attrs={"Id": "sha256:" + "c" * 64}),
    ]
    monkeypatch.setattr(readiness_module, "from_env", MagicMock(return_value=client))
    candidates = frozenset(
        {
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.REVIEW_CANDIDATE_PATCH,
        }
    )

    result = await assess_worker_readiness(
        Settings(
            execution_container_provider="restricted-local-docker",
            execution_image_id=execution_id,
            review_image_id=review_id,
            _env_file=None,
        ),
        candidates,
    )

    assert result.permitted_job_types == {JobType.EXECUTE_WORK_PACKAGE}
    assert [blocker.code for blocker in result.blockers] == ["review_image_id_mismatch"]


@pytest.mark.asyncio
async def test_approved_provider_blocks_until_dispatch_is_wired_even_when_images_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution_id = "sha256:" + "a" * 64
    review_id = "sha256:" + "b" * 64
    client = MagicMock()
    client.ping.return_value = None
    client.images.get.side_effect = [
        MagicMock(id=execution_id, attrs={"Id": execution_id}),
        MagicMock(id=review_id, attrs={"Id": review_id}),
    ]
    monkeypatch.setattr(readiness_module, "from_env", MagicMock(return_value=client))
    candidates = frozenset(
        {
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.REVIEW_CANDIDATE_PATCH,
        }
    )

    result = await assess_worker_readiness(
        Settings(
            execution_container_provider="restricted-local-docker",
            execution_image_id=execution_id,
            review_image_id=review_id,
            _env_file=None,
        ),
        candidates,
    )

    assert result.permitted_job_types == frozenset()
    assert [blocker.code for blocker in result.blockers] == [
        "restricted_executor_dispatch_unwired"
    ]
    assert "durable restricted broker runner" in result.blockers[0].next_action


@pytest.mark.asyncio
async def test_setup_blocker_evidence_preserves_queue_and_attempt_history() -> None:
    session = AsyncMock()
    blocked_job = JobModel(
        job_type=JobType.EXECUTE_WORK_PACKAGE,
        status=JobStatus.RETRY_WAIT,
        payload={},
        attempt_count=2,
        retry_count=1,
        last_error="Docker API connection failed during the previous attempt.",
        last_failure_class="infrastructure",
    )
    ready_job = JobModel(
        job_type=JobType.ADVANCE_WORKFLOW,
        status=JobStatus.QUEUED,
        payload={},
        attempt_count=0,
        retry_count=0,
        last_error="Setup blocker [old] capability=model_provider.",
        last_failure_class="configuration",
    )
    result = MagicMock()
    result.all.return_value = [blocked_job, ready_job]
    session.scalars.return_value = result

    await JobRepository(session).record_setup_blockers(
        candidate_job_types={
            JobType.EXECUTE_WORK_PACKAGE,
            JobType.ADVANCE_WORKFLOW,
        },
        blockers={
            JobType.EXECUTE_WORK_PACKAGE: (
                "Setup blocker [docker_runtime_unavailable] capability=container_execution."
            )
        },
    )

    assert blocked_job.status == JobStatus.RETRY_WAIT
    assert blocked_job.attempt_count == 2
    assert blocked_job.retry_count == 1
    assert blocked_job.last_error.startswith("Docker API connection failed")
    assert "docker_runtime_unavailable" in blocked_job.last_error
    assert blocked_job.last_failure_class == "infrastructure"
    assert ready_job.status == JobStatus.QUEUED
    assert ready_job.last_error is None
    assert ready_job.last_failure_class is None
    session.flush.assert_awaited_once()


def test_setup_blocker_logging_reports_only_state_changes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reported: set[str] = set()
    blocker = "Setup blocker [docker_runtime_unavailable] capability=container_execution."

    with caplog.at_level(logging.INFO, logger="ai_enterprise.worker"):
        _report_setup_blocker_changes({blocker}, reported)
        _report_setup_blocker_changes({blocker}, reported)
        _report_setup_blocker_changes(set(), reported)

    messages = [record.getMessage() for record in caplog.records]
    assert messages.count(f"Worker {blocker}") == 1
    assert messages.count(f"Worker setup blocker cleared: {blocker}") == 1
    assert reported == set()


@pytest.mark.asyncio
async def test_readiness_cache_bounds_provider_preflight_frequency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = MagicMock(side_effect=[100.0, 101.0, 131.0])
    preflight = AsyncMock(
        return_value=readiness_module.WorkerReadiness(
            permitted_job_types=frozenset({JobType.ADVANCE_WORKFLOW}), blockers=()
        )
    )
    monkeypatch.setattr(readiness_module, "assess_worker_readiness", preflight)
    cache = WorkerReadinessCache(interval_seconds=30.0, clock=clock)
    settings = Settings(_env_file=None)
    candidates = frozenset({JobType.ADVANCE_WORKFLOW})

    first = await cache.get(settings, candidates)
    second = await cache.get(settings, candidates)
    third = await cache.get(settings, candidates)

    assert first is second
    assert third is first
    assert preflight.await_count == 2
