import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from ai_enterprise.agent_runtime_worker import AgentRuntimeWorker
from ai_enterprise.api.agent_runtime_schemas import ModelHealthRequest
from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.agent_runtime import (
    get_context,
    get_model_invocations,
    get_runtime_session,
    get_skill,
    get_tool,
    get_tool_invocations,
    get_validation,
    list_model_deployments,
    router,
    update_model_health,
)
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
    ModelDeploymentModel,
    ModelInvocationModel,
    SkillModel,
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


class RuntimeReadSession:
    def __init__(self, runtime_session: AgentRuntimeSessionModel) -> None:
        self.runtime_session = runtime_session

    async def get(self, model: type, identity: uuid.UUID) -> object | None:
        if model is AgentRuntimeSessionModel and identity == self.runtime_session.id:
            return self.runtime_session
        return None

    async def scalars(self, statement: object) -> list[object]:
        return []


class RuntimeListSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows

    async def scalars(self, statement: object) -> "RuntimeListSession":
        return self


class RuntimeRegistrySession(RuntimeListSession):
    def __init__(self, rows: list[object], gets: dict[object, object] | None = None) -> None:
        super().__init__(rows)
        self.gets = gets or {}

    async def get(self, model: type, identity: object) -> object | None:
        return self.gets.get((model, identity))


def runtime_session(scope_id: uuid.UUID | None = None) -> AgentRuntimeSessionModel:
    return AgentRuntimeSessionModel(
        id=uuid.uuid4(),
        workflow_type="project_delivery",
        workflow_run_id=uuid.uuid4(),
        scope_type="project",
        scope_id=scope_id or uuid.uuid4(),
        agent_profile_id=uuid.uuid4(),
        agent_profile_version_id=uuid.uuid4(),
        assignment_id=uuid.uuid4(),
        role_version_id=uuid.uuid4(),
        runtime_specification_id=uuid.uuid4(),
        runtime_specification_hash="a" * 64,
        context_manifest_hash="b" * 64,
        selected_model_deployment_id=None,
        status="running",
        attempt_number=1,
        counters={},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_runtime_read_requires_matching_capability_scope() -> None:
    row = runtime_session()
    session = RuntimeReadSession(row)

    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"project:{uuid.uuid4()}"}),
    )
    with pytest.raises(HTTPException) as exc:
        await get_runtime_session(row.id, session, denied)  # type: ignore[arg-type]
    assert exc.value.status_code == 403

    allowed = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"project:{row.scope_id}"}),
    )
    response = await get_runtime_session(row.id, session, allowed)  # type: ignore[arg-type]
    assert response.id == row.id
    assert response.status_label == "Work is running"
    assert response.status_meaning is not None
    assert response.status_meaning["operator_action"]


@pytest.mark.asyncio
async def test_model_deployment_list_exposes_friendly_status_labels() -> None:
    deployment = ModelDeploymentModel(
        id=uuid.uuid4(),
        organization_id=None,
        provider_key="local",
        model_reference="gemma3:12b",
        deployment_class="local",
        context_window=8192,
        supports_tools=True,
        supports_structured_output=True,
        maximum_data_classification="internal",
        status="unavailable",
        metadata_document={},
        health_document={"available": False},
    )

    actor = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({"global"}),
    )

    response = await list_model_deployments(
        RuntimeListSession([deployment]),  # type: ignore[arg-type]
        actor,
    )

    assert response[0].status == "unavailable"
    assert response[0].status_label == "Source unavailable"
    assert response[0].status_meaning is not None
    assert response[0].status_meaning["severity"] == "bad"


@pytest.mark.asyncio
async def test_runtime_lineage_accepts_runtime_session_scope() -> None:
    row = runtime_session()
    actor = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"runtime_session:{row.id}"}),
    )

    response = await get_tool_invocations(
        row.id,
        RuntimeReadSession(row),  # type: ignore[arg-type]
        actor,
    )

    assert response == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    [get_context, get_tool_invocations, get_model_invocations, get_validation],
)
async def test_runtime_lineage_rejects_wrong_actor_scope(route) -> None:
    row = runtime_session()
    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"runtime_session:{uuid.uuid4()}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await route(
            row.id,
            RuntimeReadSession(row),  # type: ignore[arg-type]
            denied,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_runtime_registry_lists_require_global_read_scope() -> None:
    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"organization:{uuid.uuid4()}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await list_model_deployments(
            RuntimeListSession([]),  # type: ignore[arg-type]
            denied,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_runtime_registry_object_reads_accept_only_matching_scope() -> None:
    organization_id = uuid.uuid4()
    skill = SkillModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        skill_key="requirements-analysis-v1",
        name="Requirements Analysis",
        status="active",
    )
    session = RuntimeRegistrySession([], {(SkillModel, skill.id): skill})
    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"organization:{uuid.uuid4()}"}),
    )
    allowed = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"organization:{organization_id}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await get_skill(skill.id, session, denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403
    assert (await get_skill(skill.id, session, allowed)).id == skill.id  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_tool_registry_reads_require_global_scope() -> None:
    denied = Actor(
        "reader",
        "human",
        "operator",
        frozenset({"runtime.read"}),
        scopes=frozenset({f"organization:{uuid.uuid4()}"}),
    )

    with pytest.raises(HTTPException) as exc:
        await get_tool(
            "repository.read",
            "1",
            RuntimeRegistrySession([]),  # type: ignore[arg-type]
            denied,
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_tool_registration_requires_runtime_admin_capability() -> None:
    service = AgentRuntimePersistenceService(session=object())  # type: ignore[arg-type]
    with pytest.raises(AgentRuntimePersistenceError, match="administrator capability") as denied:
        await service.register_tool(
            "repository.read",
            "1",
            {},
            Actor("platform-admin", "human", "platform-admin"),
        )
    assert denied.value.status_code == 403

    with pytest.raises(AgentRuntimePersistenceError, match="administrator capability") as denied:
        await service.register_tool(
            "repository.read",
            "1",
            {},
            Actor(
                "platform-admin",
                "human",
                "platform-admin",
                frozenset({"runtime.admin"}),
                scopes=frozenset({f"organization:{uuid.uuid4()}"}),
            ),
        )
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_model_health_update_requires_runtime_admin_capability() -> None:
    with pytest.raises(HTTPException) as exc:
        await update_model_health(
            uuid.uuid4(),
            ModelHealthRequest(available=True, latency_ms=10, error_rate=0.0),
            RuntimeRegistrySession([]),  # type: ignore[arg-type]
            Actor("platform-admin", "human", "platform-admin"),
        )

    assert exc.value.status_code == 403


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
