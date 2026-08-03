import json
import os
from uuid import uuid4

import httpx
import pytest
from fastapi.routing import APIRoute

from ai_enterprise.api.routes.requirements_revisions import router
from ai_enterprise.config import Settings
from ai_enterprise.domain.requirements_revision.models import (
    RequirementsArtifactDocument,
    RequirementsReviewDecision,
)
from ai_enterprise.domain.requirements_revision.policies import RevisionFeedbackPolicy
from ai_enterprise.infrastructure.crews.requirements_crew import RequirementsCrewRunner
from ai_enterprise.infrastructure.jobs.models import JobExecutionAttemptModel
from ai_enterprise.infrastructure.requirements_llm.adapter import (
    RequirementsExecutionInput,
    RequirementsOutputError,
    StructuredRequirementsAdapter,
    build_revision_prompt,
)
from ai_enterprise.infrastructure.requirements_llm.crewai_executor import (
    CrewAIRequirementsExecutor,
)
from ai_enterprise.infrastructure.requirements_llm.parser import RequirementsArtifactParser
from ai_enterprise.infrastructure.requirements_llm.provider import (
    RequirementsProviderConfig,
    RequirementsProviderError,
    create_requirements_provider,
)
from ai_enterprise.infrastructure.requirements_revision.models import (
    RequirementsArtifactLineageModel,
    RequirementsRevisionCycleModel,
    RequirementsRevisionRequestModel,
)


def _payload(summary: str = "Auditable workflow") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "title": "Requirements",
        "executive_summary": summary,
        "functional_requirements": [
            {
                "id": "REQ-001",
                "statement": "The service shall persist immutable decisions.",
                "acceptance_criteria": ["A prior decision cannot be overwritten."],
            }
        ],
        "non_functional_requirements": [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
    }


def _decision() -> RequirementsReviewDecision:
    return RequirementsReviewDecision.model_validate(
        {
            "decision": "changes_requested",
            "summary": "Recovery criteria are incomplete.",
            "findings": [
                {
                    "requirement_id": "REQ-001",
                    "category": "missing",
                    "severity": "high",
                    "description": "Worker crash recovery is unspecified.",
                    "requested_change": "Add acceptance criteria for expired lease recovery.",
                }
            ],
        }
    )


def test_changes_requested_requires_structured_actionable_findings() -> None:
    with pytest.raises(ValueError, match="actionable"):
        RequirementsReviewDecision(
            decision="changes_requested", summary="Please improve this", findings=()
        )
    decision = _decision()
    artifact_id = uuid4()
    first = RevisionFeedbackPolicy().create(
        artifact_id=artifact_id, artifact_hash="a" * 64, decision=decision
    )
    second = RevisionFeedbackPolicy().create(
        artifact_id=artifact_id, artifact_hash="a" * 64, decision=decision
    )
    assert first.feedback_hash == second.feedback_hash


def test_parser_accepts_only_one_json_object_and_bounds_diagnostics() -> None:
    parser = RequirementsArtifactParser()
    raw = json.dumps(_payload())
    assert parser.parse(raw).functional_requirements[0].id == "REQ-001"
    assert parser.parse(f"```json\n{raw}\n```").title == "Requirements"
    with pytest.raises(json.JSONDecodeError):
        parser.parse(raw + "\nThis is the result.")
    failure = parser.failure("{", pytest.raises)
    assert len(failure.errors) <= parser.MAX_ERRORS


@pytest.mark.asyncio
async def test_repair_is_called_exactly_once_and_evidence_is_bounded() -> None:
    calls: list[str] = []

    async def invalid(_prompt: str) -> str:
        return "not-json"

    async def repair(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(_payload("Repaired artifact"))

    result = await StructuredRequirementsAdapter(invalid, repair=repair).run(
        RequirementsExecutionInput("Project", "Objective", {}, {})
    )
    assert result.repair_attempted and result.repair_succeeded and len(calls) == 1
    assert result.raw_output_hash and result.validation_errors

    async def still_invalid(_prompt: str) -> str:
        calls.append("second")
        return "still-invalid"

    before = len(calls)
    with pytest.raises(RequirementsOutputError, match="after one repair"):
        await StructuredRequirementsAdapter(invalid, repair=still_invalid).run(
            RequirementsExecutionInput("Project", "Objective", {}, {})
        )
    assert len(calls) == before + 1


def test_revision_prompt_contains_previous_artifact_and_exact_feedback_hash() -> None:
    prompt = build_revision_prompt(
        RequirementsExecutionInput(
            "Project",
            "Objective",
            {},
            {},
            previous_artifact=_payload(),
            revision_cycle_number=2,
            revision_feedback=({"requested_change": "Add recovery"},),
            revision_feedback_hash="b" * 64,
        )
    )
    assert '"revision_cycle_number":2' in prompt
    assert "b" * 64 in prompt
    assert "Add recovery" in prompt


def test_deterministic_revision_promotes_feedback_into_requirement_entries() -> None:
    result = RequirementsCrewRunner(Settings(requirements_crew_adapter="deterministic")).run(
        project_name="Restaurant",
        project_description="Build ordering",
        manifest_hash="a" * 64,
        previous_artifact="FR-001",
        revision_cycle_number=1,
        revision_feedback_summary="Menu scope is missing",
        revision_feedback=[{"requested_change": "Add bilingual menu management."}],
        revision_feedback_hash="b" * 64,
    )
    assert "FR-002: Add bilingual menu management." in result.markdown
    assert "verifiable coverage" in result.markdown


@pytest.mark.asyncio
async def test_provider_factory_and_preflight_are_fail_closed() -> None:
    with pytest.raises(RequirementsProviderError, match="Unsupported"):
        create_requirements_provider(RequirementsProviderConfig(provider="unknown"))
    with pytest.raises(RequirementsProviderError, match="forbidden"):
        create_requirements_provider(RequirementsProviderConfig(app_env="production"))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://ollama.local:11434/api/tags")
        return httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})

    provider = create_requirements_provider(
        RequirementsProviderConfig(model="ollama/gemma4:12b", base_url="http://ollama.local:11434"),
        transport=httpx.MockTransport(handler),
    )
    await provider.preflight()

    missing = create_requirements_provider(
        RequirementsProviderConfig(
            model="ollama/missing:latest", base_url="http://ollama.local:11434"
        ),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RequirementsProviderError, match="not installed"):
        await missing.preflight()


def test_lineage_schema_preserves_existing_runs_artifacts_and_attempts() -> None:
    assert RequirementsRevisionRequestModel.__tablename__ == "requirements_revision_requests"
    assert RequirementsRevisionCycleModel.__tablename__ == "requirements_revision_cycles"
    assert RequirementsArtifactLineageModel.__tablename__ == "requirements_artifact_lineage"
    assert "revision_cycle_id" in JobExecutionAttemptModel.__table__.columns
    assert RequirementsRevisionCycleModel.__table__.columns.get("execution_attempt_id") is None


def test_revision_api_exposes_history_without_artifact_mutation_route() -> None:
    paths = {route.path for route in router.routes if isinstance(route, APIRoute)}
    assert "/requirements-runs/{run_id}/revisions" in paths
    assert "/requirements-runs/{run_id}/artifacts" in paths
    assert all("overwrite" not in path and "update" not in path for path in paths)


@pytest.mark.asyncio
async def test_model_provider_smoke_returns_valid_artifact() -> None:
    if os.getenv("RUN_LOCAL_LLM_SMOKE") == "1":
        config = RequirementsProviderConfig(
            model=os.getenv("REQUIREMENTS_LLM_MODEL", "ollama/gemma3:12b"),
            base_url=os.getenv("REQUIREMENTS_LLM_BASE_URL", "http://localhost:11434"),
        )
        provider = create_requirements_provider(config)
        await provider.preflight()
        executor = CrewAIRequirementsExecutor(provider)
    else:
        config = RequirementsProviderConfig(
            model="ollama/gemma4:12b", base_url="http://ollama.local:11434"
        )

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == httpx.URL("http://ollama.local:11434/api/tags")
            return httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})

        provider = create_requirements_provider(config, transport=httpx.MockTransport(handler))
        await provider.preflight()

        async def executor(_prompt: str) -> str:
            return json.dumps(_payload("Deterministic provider smoke artifact"))

    adapter = StructuredRequirementsAdapter(executor)
    result = await adapter.run(
        RequirementsExecutionInput(
            "Smoke Project", "Create an auditable issue tracking API", {}, {}
        )
    )
    assert isinstance(result.artifact, RequirementsArtifactDocument)
