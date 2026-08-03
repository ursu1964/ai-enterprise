import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    architecture_provider_ready,
)
from ai_enterprise.infrastructure.crews.architecture_crew import ArchitectureCrewRunner
from ai_enterprise.infrastructure.crews.work_package_crew import WorkPackageCrewRunner
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
    assert await architecture_provider_ready(ArchitectureProviderConfig(provider="scripted"))
    assert not await architecture_provider_ready(ArchitectureProviderConfig(provider="unsupported"))


def test_scripted_architecture_runner_produces_offline_evidence() -> None:
    result = ArchitectureCrewRunner(Settings(architecture_provider="scripted")).run(
        project_name="Factory Demo",
        project_description="Create governed project proof.",
        project_manifest_hash="m" * 64,
        requirements_markdown="# Requirements\n\n- FR-001: Preserve evidence.",
        requirements_artifact_hash="r" * 64,
    )

    assert "Architecture - Factory Demo" in result.markdown
    assert "FR-001" in result.markdown


def test_scripted_architecture_revision_preserves_feedback_and_traceability() -> None:
    result = ArchitectureCrewRunner(Settings(architecture_provider="scripted")).run(
        project_name="Restaurant",
        project_description="Bilingual restaurant platform",
        project_manifest_hash="m" * 64,
        requirements_markdown="- FR-001: Evidence\n- FR-002: Menu\n- FR-010: Accessibility",
        requirements_artifact_hash="r" * 64,
        revision_feedback="Cover payments, kitchen, inventory, security and deployment.",
    )

    assert "## Revision response" in result.markdown
    assert "Cover payments, kitchen, inventory, security and deployment." in result.markdown
    assert "- FR-001 ->" in result.markdown
    assert "- FR-002 ->" in result.markdown
    assert "- FR-010 ->" in result.markdown
    assert "Stripe, Netopia" in result.markdown
    assert "KDS tickets" in result.markdown


def test_scripted_work_package_runner_produces_valid_contract_json() -> None:
    result = WorkPackageCrewRunner(Settings(architecture_provider="scripted")).run(
        project_id=str(uuid.uuid4()),
        project_name="Factory Demo",
        project_description="Create governed project proof.",
        base_commit_sha="a" * 40,
        requirements_artifact_id=str(uuid.uuid4()),
        requirements_hash="r" * 64,
        requirements_markdown="# Requirements",
        architecture_artifact_id=str(uuid.uuid4()),
        architecture_hash="c" * 64,
        architecture_markdown="# Architecture",
        tracked_files=[".ai-enterprise-initialized"],
    )

    assert "Build bilingual menu storefront foundation" in result.raw_json
    assert "src/index.html" in result.raw_json
    assert "tests/menu.test.js" in result.raw_json
    assert '"allowed_directories": [".", "src", "tests"]' in result.raw_json


def test_scripted_work_package_revision_creates_real_vertical_slice() -> None:
    result = WorkPackageCrewRunner(Settings(architecture_provider="scripted")).run(
        project_id=str(uuid.uuid4()),
        project_name="Restaurant",
        project_description="Bilingual restaurant platform",
        base_commit_sha="a" * 40,
        requirements_artifact_id=str(uuid.uuid4()),
        requirements_hash="r" * 64,
        requirements_markdown="- FR-002: Menu\n- FR-010: Accessibility",
        architecture_artifact_id=str(uuid.uuid4()),
        architecture_hash="c" * 64,
        architecture_markdown="# Architecture",
        tracked_files=[".ai-enterprise-initialized"],
        revision_feedback="Replace the marker-only package with customer-visible implementation.",
    )

    assert ".ai-enterprise-initialized" not in result.raw_json
    assert "FR-002" in result.raw_json
    assert "npm" in result.raw_json
