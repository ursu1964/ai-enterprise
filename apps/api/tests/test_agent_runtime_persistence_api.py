import uuid

import pytest

from ai_enterprise.agent_runtime_worker import AgentRuntimeWorker
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.agent_runtime import router
from ai_enterprise.application.agent_runtime.workflow_binding import (
    GovernedWorkflowRuntimeBinding,
    require_governed_runtime,
)
from ai_enterprise.application.agent_runtime_commands import ExecuteAgentRuntime, InvokeAgentTool
from ai_enterprise.application.agent_runtime_persistence_service import (
    AgentRuntimePersistenceError,
    AgentRuntimePersistenceService,
)
from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentEscalationModel,
    AgentOutputValidationModel,
    AgentRuntimeSessionModel,
    AgentRuntimeSpecificationModel,
    CapabilitySkillBindingModel,
    ContextManifestModel,
    ModelInvocationModel,
    SkillVersionModel,
    ToolDefinitionModel,
    ToolInvocationModel,
)
from ai_enterprise.infrastructure.agent_runtime.seed import INITIAL_SKILLS, initial_skill_document


def test_runtime_persistence_preserves_complete_immutable_lineage() -> None:
    assert AgentRuntimeSpecificationModel.__table__.c.configuration_hash.unique is True
    assert ContextManifestModel.__table__.c.manifest_hash.unique is True
    assert SkillVersionModel.__table__.c.skill_hash.nullable is False
    assert CapabilitySkillBindingModel.__table__.primary_key is not None
    assert ToolDefinitionModel.__table__.primary_key is not None
    for model in (
        ToolInvocationModel,
        ModelInvocationModel,
        AgentOutputValidationModel,
        AgentEscalationModel,
    ):
        assert "runtime_session_id" in model.__table__.c
    session_columns = AgentRuntimeSessionModel.__table__.c
    for identity in (
        "agent_profile_id",
        "agent_profile_version_id",
        "assignment_id",
        "role_version_id",
        "runtime_specification_hash",
    ):
        assert session_columns[identity].nullable is False


def test_required_runtime_api_surface_is_registered() -> None:
    paths = {f"/api/v1{route.path}" for route in router.routes}
    assert {
        "/api/v1/organizations/{organization_id}/skills",
        "/api/v1/skills/{skill_id}/versions",
        "/api/v1/skill-versions/{version_id}/approve",
        "/api/v1/tools",
        "/api/v1/tools/{tool_key}/versions/{version}",
        "/api/v1/model-deployments",
        "/api/v1/model-deployments/{deployment_id}/health",
        "/api/v1/agent-runtime-sessions",
        "/api/v1/agent-runtime-sessions/{session_id}/context",
        "/api/v1/agent-runtime-sessions/{session_id}/tool-invocations",
        "/api/v1/agent-runtime-sessions/{session_id}/model-invocations",
        "/api/v1/agent-runtime-sessions/{session_id}/validation",
    } <= paths


@pytest.mark.asyncio
async def test_tool_registration_is_restricted_to_platform_administrators() -> None:
    service = AgentRuntimePersistenceService(session=object())  # type: ignore[arg-type]
    with pytest.raises(AgentRuntimePersistenceError, match="administrator") as denied:
        await service.register_tool(
            "repository.read",
            "1",
            {},
            Actor("agent", "agent", "engineer"),
        )
    assert denied.value.status_code == 403


def test_initial_seed_is_complete_and_structured() -> None:
    assert len(INITIAL_SKILLS) == 10
    assert {item[0] for item in INITIAL_SKILLS} == {
        "requirements-analysis-v1",
        "requirements-review-v1",
        "architecture-analysis-v1",
        "interface-design-v1",
        "threat-analysis-v1",
        "failure-analysis-v1",
        "work-package-decomposition-v1",
        "python-implementation-v1",
        "test-evidence-analysis-v1",
        "patch-review-v1",
    }
    document = initial_skill_document("patch-review-v1", "patch.review")
    assert document["required_capabilities"] == ["patch.review"]
    assert isinstance(document["procedure"], dict)


def test_internal_commands_bind_runtime_identity_and_governed_tool_requests() -> None:
    session_id = uuid.uuid4()
    metadata = {"correlation_id": uuid.uuid4(), "idempotency_key": "runtime-1"}
    execute = ExecuteAgentRuntime(
        **metadata,
        session_id=session_id,
        requested_capability="patch.review",
        workflow_input={"project_id": str(uuid.uuid4())},
    )
    invoke = InvokeAgentTool(
        **metadata,
        session_id=session_id,
        tool_key="repository.read",
        arguments={"path": "src/main.py"},
    )
    assert execute.session_id == invoke.session_id
    assert invoke.arguments == {"path": "src/main.py"}


def test_model_backed_workflows_fail_closed_without_runtime_lineage() -> None:
    with pytest.raises(PermissionError, match="SESSION-REQUIRED"):
        require_governed_runtime("architecture", None)
    binding = GovernedWorkflowRuntimeBinding(
        workflow_type="architecture",
        workflow_run_id=uuid.uuid4(),
        runtime_session_id=uuid.uuid4(),
        runtime_specification_hash="a" * 64,
        context_manifest_hash="b" * 64,
    )
    assert require_governed_runtime("architecture", binding) is binding


@pytest.mark.asyncio
async def test_worker_accepts_only_explicit_runtime_session_identity() -> None:
    seen: list[uuid.UUID] = []

    class Processor:
        async def execute(self, session_id: uuid.UUID) -> None:
            seen.append(session_id)

    worker = AgentRuntimeWorker(Processor())
    with pytest.raises(ValueError, match="required"):
        await worker.process({})
    session_id = uuid.uuid4()
    await worker.process({"runtime_session_id": str(session_id)})
    assert seen == [session_id]
