import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.agent_runtime_schemas import (
    CompiledPromptResponse,
    CreatePromptRequest,
    CreatePromptVersionRequest,
    CreateRuntimeSessionRequest,
    CreateSkillRequest,
    CreateSkillVersionRequest,
    ModelDeploymentResponse,
    ModelHealthRequest,
    PromptResponse,
    PromptVersionResponse,
    RegisterModelDeploymentRequest,
    RegisterToolRequest,
    RuntimeSessionResponse,
    SkillResponse,
    SkillVersionResponse,
    ToolResponse,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.agent_runtime_persistence_service import (
    AgentRuntimePersistenceError,
    AgentRuntimePersistenceService,
)
from ai_enterprise.infrastructure.agent_runtime.models import (
    AgentOutputValidationModel,
    AgentRuntimeSessionModel,
    ContextManifestModel,
    ModelDeploymentModel,
    ModelInvocationModel,
    PromptRegistryModel,
    PromptVersionModel,
    SkillModel,
    SkillVersionModel,
    ToolDefinitionModel,
    ToolInvocationModel,
)

router = APIRouter(tags=["governed-agent-runtime"])


def _error(exc: AgentRuntimePersistenceError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.post(
    "/organizations/{organization_id}/skills", response_model=SkillResponse, status_code=201
)
async def create_skill(
    organization_id: uuid.UUID,
    request: CreateSkillRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> SkillResponse:
    try:
        row = await AgentRuntimePersistenceService(session).create_skill(
            organization_id, request.skill_key, request.name, request.skill_document, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return SkillResponse.model_validate(row)


@router.post("/skills/{skill_id}/versions", response_model=SkillVersionResponse, status_code=201)
async def create_skill_version(
    skill_id: uuid.UUID,
    request: CreateSkillVersionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> SkillVersionResponse:
    skill = await session.get(SkillModel, skill_id)
    if skill is None:
        raise HTTPException(404, "Skill not found")
    try:
        row = await AgentRuntimePersistenceService(session).create_skill_version(
            skill, request.skill_document, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return SkillVersionResponse.model_validate(row)


@router.post("/skill-versions/{version_id}/approve", response_model=SkillVersionResponse)
async def approve_skill_version(
    version_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> SkillVersionResponse:
    version = await session.get(SkillVersionModel, version_id)
    if version is None:
        raise HTTPException(404, "Skill version not found")
    try:
        row = await AgentRuntimePersistenceService(session).approve_skill_version(version, actor)
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return SkillVersionResponse.model_validate(row)


@router.get("/skills/{skill_id}", response_model=SkillResponse)
async def get_skill(skill_id: uuid.UUID, session: SessionDependency) -> SkillResponse:
    row = await session.get(SkillModel, skill_id)
    if row is None:
        raise HTTPException(404, "Skill not found")
    return SkillResponse.model_validate(row)


@router.post("/tools", response_model=ToolResponse, status_code=201)
async def register_tool(
    request: RegisterToolRequest, session: SessionDependency, actor: ActorDependency
) -> ToolResponse:
    try:
        row = await AgentRuntimePersistenceService(session).register_tool(
            request.tool_key, request.version, request.tool_document, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return ToolResponse.model_validate(row)


@router.get("/tools", response_model=list[ToolResponse])
async def list_tools(session: SessionDependency) -> list[ToolResponse]:
    rows = (
        await session.scalars(
            select(ToolDefinitionModel).order_by(
                ToolDefinitionModel.tool_key, ToolDefinitionModel.version
            )
        )
    ).all()
    return [ToolResponse.model_validate(row) for row in rows]


@router.get("/tools/{tool_key}/versions/{version}", response_model=ToolResponse)
async def get_tool(tool_key: str, version: str, session: SessionDependency) -> ToolResponse:
    row = await session.get(ToolDefinitionModel, (tool_key, version))
    if row is None:
        raise HTTPException(404, "Tool version not found")
    return ToolResponse.model_validate(row)


@router.post("/model-deployments", response_model=ModelDeploymentResponse, status_code=201)
async def register_model_deployment(
    request: RegisterModelDeploymentRequest, session: SessionDependency, actor: ActorDependency
) -> ModelDeploymentResponse:
    values = request.model_dump(exclude={"correlation_id", "idempotency_key"})
    try:
        row = await AgentRuntimePersistenceService(session).register_deployment(values, actor)
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return ModelDeploymentResponse.model_validate(row)


@router.get("/model-deployments", response_model=list[ModelDeploymentResponse])
async def list_model_deployments(session: SessionDependency) -> list[ModelDeploymentResponse]:
    rows = (
        await session.scalars(
            select(ModelDeploymentModel).order_by(
                ModelDeploymentModel.provider_key, ModelDeploymentModel.model_reference
            )
        )
    ).all()
    return [ModelDeploymentResponse.model_validate(row) for row in rows]


@router.post("/model-deployments/{deployment_id}/health", response_model=ModelDeploymentResponse)
async def update_model_health(
    deployment_id: uuid.UUID,
    request: ModelHealthRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ModelDeploymentResponse:
    if actor.role not in {"platform-admin", "platform_administrator"}:
        raise HTTPException(403, "Platform administrator role required")
    row = await session.get(ModelDeploymentModel, deployment_id)
    if row is None:
        raise HTTPException(404, "Model deployment not found")
    row.health_document = request.model_dump()
    row.status = "active" if request.available else "unavailable"
    await session.commit()
    return ModelDeploymentResponse.model_validate(row)


@router.post("/prompts", response_model=PromptResponse, status_code=201)
async def create_prompt(
    request: CreatePromptRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PromptResponse:
    values = request.model_dump(exclude={"correlation_id", "idempotency_key"})
    try:
        row = await AgentRuntimePersistenceService(session).create_prompt(values, actor)
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return PromptResponse.model_validate(row)


@router.get("/prompts", response_model=list[PromptResponse])
async def list_prompts(session: SessionDependency) -> list[PromptResponse]:
    rows = (
        await session.scalars(
            select(PromptRegistryModel).order_by(
                PromptRegistryModel.organization_id, PromptRegistryModel.prompt_key
            )
        )
    ).all()
    return [PromptResponse.model_validate(row) for row in rows]


@router.post("/prompts/{prompt_id}/versions", response_model=PromptVersionResponse, status_code=201)
async def create_prompt_version(
    prompt_id: uuid.UUID,
    request: CreatePromptVersionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> PromptVersionResponse:
    prompt = await session.get(PromptRegistryModel, prompt_id)
    if prompt is None:
        raise HTTPException(404, "Prompt not found")
    values = request.model_dump(exclude={"correlation_id", "idempotency_key"})
    try:
        row = await AgentRuntimePersistenceService(session).create_prompt_version(
            prompt, values, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return PromptVersionResponse.model_validate(row)


@router.post("/prompt-versions/{version_id}/approve", response_model=PromptVersionResponse)
async def approve_prompt_version(
    version_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> PromptVersionResponse:
    version = await session.get(PromptVersionModel, version_id)
    if version is None:
        raise HTTPException(404, "Prompt version not found")
    try:
        row = await AgentRuntimePersistenceService(session).approve_prompt_version(
            version, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return PromptVersionResponse.model_validate(row)


@router.post("/prompts/{prompt_id}/rollback/{version_id}", response_model=PromptResponse)
async def rollback_prompt(
    prompt_id: uuid.UUID,
    version_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> PromptResponse:
    prompt = await session.get(PromptRegistryModel, prompt_id)
    version = await session.get(PromptVersionModel, version_id)
    if prompt is None or version is None:
        raise HTTPException(404, "Prompt or prompt version not found")
    try:
        row = await AgentRuntimePersistenceService(session).rollback_prompt(
            prompt, version, actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return PromptResponse.model_validate(row)


@router.get("/prompts/{prompt_id}/compiled", response_model=CompiledPromptResponse)
async def get_compiled_prompt(
    prompt_id: uuid.UUID,
    session: SessionDependency,
) -> CompiledPromptResponse:
    prompt = await session.get(PromptRegistryModel, prompt_id)
    if prompt is None or prompt.current_version_id is None:
        raise HTTPException(404, "Active prompt version not found")
    version = await session.get(PromptVersionModel, prompt.current_version_id)
    if version is None:
        raise HTTPException(404, "Active prompt version not found")
    compiled_layers = [
        {"name": key, "content": value} for key, value in version.prompt_layers.items()
    ]
    return CompiledPromptResponse(
        prompt_id=prompt.id,
        prompt_key=prompt.prompt_key,
        version_id=version.id,
        version_number=version.version_number,
        prompt_hash=version.prompt_hash,
        approval_status=version.approval_status,
        compiled_layers=compiled_layers,
        output_schema=version.output_schema,
        policy_document=version.policy_document,
    )


@router.post("/agent-runtime-sessions", response_model=RuntimeSessionResponse, status_code=201)
async def start_runtime_session(
    request: CreateRuntimeSessionRequest, session: SessionDependency, actor: ActorDependency
) -> RuntimeSessionResponse:
    values = request.model_dump(exclude={"correlation_id", "idempotency_key"})
    try:
        row = await AgentRuntimePersistenceService(session).start_session(values, actor)
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return RuntimeSessionResponse.model_validate(row)


async def _session(session_id: uuid.UUID, session: SessionDependency) -> AgentRuntimeSessionModel:
    row = await session.get(AgentRuntimeSessionModel, session_id)
    if row is None:
        raise HTTPException(404, "Runtime session not found")
    return row


@router.get("/agent-runtime-sessions/{session_id}", response_model=RuntimeSessionResponse)
async def get_runtime_session(
    session_id: uuid.UUID, session: SessionDependency
) -> RuntimeSessionResponse:
    return RuntimeSessionResponse.model_validate(await _session(session_id, session))


@router.post("/agent-runtime-sessions/{session_id}/cancel", response_model=RuntimeSessionResponse)
async def cancel_runtime_session(
    session_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> RuntimeSessionResponse:
    try:
        row = await AgentRuntimePersistenceService(session).cancel_session(
            await _session(session_id, session), actor
        )
    except AgentRuntimePersistenceError as exc:
        raise _error(exc) from exc
    return RuntimeSessionResponse.model_validate(row)


async def _lineage(model: Any, session_id: uuid.UUID, session: SessionDependency) -> list[dict]:
    rows: list[Any] = list(
        await session.scalars(select(model).where(model.runtime_session_id == session_id))
    )
    return [
        {column.name: getattr(row, column.name) for column in model.__table__.columns}
        for row in rows
    ]


@router.get("/agent-runtime-sessions/{session_id}/context")
async def get_context(session_id: uuid.UUID, session: SessionDependency) -> list[dict]:
    return await _lineage(ContextManifestModel, session_id, session)


@router.get("/agent-runtime-sessions/{session_id}/tool-invocations")
async def get_tool_invocations(session_id: uuid.UUID, session: SessionDependency) -> list[dict]:
    return await _lineage(ToolInvocationModel, session_id, session)


@router.get("/agent-runtime-sessions/{session_id}/model-invocations")
async def get_model_invocations(session_id: uuid.UUID, session: SessionDependency) -> list[dict]:
    return await _lineage(ModelInvocationModel, session_id, session)


@router.get("/agent-runtime-sessions/{session_id}/validation")
async def get_validation(session_id: uuid.UUID, session: SessionDependency) -> list[dict]:
    return await _lineage(AgentOutputValidationModel, session_id, session)
