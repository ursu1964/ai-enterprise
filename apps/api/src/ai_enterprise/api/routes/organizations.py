import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.organization_schemas import (
    AgentResponse,
    AgentVersionResponse,
    AssignmentResponse,
    AuthorityEvaluationRequest,
    AuthorityEvaluationResponse,
    ComposeCrewRequest,
    CreateAgentRequest,
    CreateAssignmentRequest,
    CreateOrganizationRequest,
    CreateRoleRequest,
    CreateUnitRequest,
    CreateVersionRequest,
    CrewManifestResponse,
    OrganizationResponse,
    RoleResponse,
    RoleVersionResponse,
    TransitionRequest,
    UnitResponse,
)
from ai_enterprise.application.organization_persistence_service import (
    OrganizationPersistenceError,
    OrganizationPersistenceService,
)
from ai_enterprise.infrastructure.organization.models import (
    AgentAssignmentModel,
    AgentProfileModel,
    AgentProfileVersionModel,
    OrganizationalUnitModel,
    OrganizationModel,
    RoleModel,
    RoleVersionModel,
)

router = APIRouter(tags=["organizational-governance"])


def _error(exc: OrganizationPersistenceError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


async def _required(
    session: SessionDependency, model: type[Any], identifier: uuid.UUID, label: str
) -> Any:
    row = await session.get(model, identifier)
    if row is None:
        raise HTTPException(404, f"{label} not found")
    return row


@router.post(
    "/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED
)
async def create_organization(
    request: CreateOrganizationRequest, session: SessionDependency, actor: ActorDependency
) -> OrganizationResponse:
    try:
        row = await OrganizationPersistenceService(session).create_organization(
            request.organization_key,
            request.name,
            request.policy_set_id,
            actor,
            request.correlation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return OrganizationResponse.model_validate(row)


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID, session: SessionDependency
) -> OrganizationResponse:
    return OrganizationResponse.model_validate(
        await _required(session, OrganizationModel, organization_id, "Organization")
    )


@router.post("/organizations/{organization_id}/activate", response_model=OrganizationResponse)
async def activate_organization(
    organization_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> OrganizationResponse:
    row = await _required(session, OrganizationModel, organization_id, "Organization")
    try:
        row = await OrganizationPersistenceService(session).activate_organization(
            row, request.expected_version, actor, request.correlation_id, request.causation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return OrganizationResponse.model_validate(row)


@router.post("/organizations/{organization_id}/units", response_model=UnitResponse, status_code=201)
async def create_unit(
    organization_id: uuid.UUID,
    request: CreateUnitRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> UnitResponse:
    try:
        row = await OrganizationPersistenceService(session).create_unit(
            organization_id,
            request.model_dump(include={"unit_key", "name", "purpose", "parent_unit_id"}),
            actor,
            request.correlation_id,
            request.causation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return UnitResponse.model_validate(row)


@router.get("/organizations/{organization_id}/units", response_model=list[UnitResponse])
async def list_units(organization_id: uuid.UUID, session: SessionDependency) -> list[UnitResponse]:
    rows = (
        await session.scalars(
            select(OrganizationalUnitModel)
            .where(OrganizationalUnitModel.organization_id == organization_id)
            .order_by(OrganizationalUnitModel.unit_key)
        )
    ).all()
    return [UnitResponse.model_validate(row) for row in rows]


@router.post("/organizations/{organization_id}/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    organization_id: uuid.UUID,
    request: CreateRoleRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RoleResponse:
    try:
        row = await OrganizationPersistenceService(session).create_role(
            organization_id,
            request.role_key,
            request.name,
            request.role_document,
            actor,
            request.correlation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return RoleResponse.model_validate(row)


@router.post("/roles/{role_id}/versions", response_model=RoleVersionResponse, status_code=201)
async def create_role_version(
    role_id: uuid.UUID,
    request: CreateVersionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RoleVersionResponse:
    role = await _required(session, RoleModel, role_id, "Role")
    try:
        row = await OrganizationPersistenceService(session).create_role_version(
            role, request.document, actor, request.correlation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return RoleVersionResponse.model_validate(row)


@router.post("/role-versions/{version_id}/activate", response_model=RoleVersionResponse)
async def activate_role_version(
    version_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RoleVersionResponse:
    version = await _required(session, RoleVersionModel, version_id, "Role version")
    try:
        row = await OrganizationPersistenceService(session).activate_role_version(
            version, actor, request.correlation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return RoleVersionResponse.model_validate(row)


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(role_id: uuid.UUID, session: SessionDependency) -> RoleResponse:
    return RoleResponse.model_validate(await _required(session, RoleModel, role_id, "Role"))


@router.post(
    "/organizations/{organization_id}/agents", response_model=AgentResponse, status_code=201
)
async def create_agent(
    organization_id: uuid.UUID,
    request: CreateAgentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AgentResponse:
    try:
        row = await OrganizationPersistenceService(session).create_agent(
            organization_id,
            request.home_unit_id,
            request.agent_key,
            request.display_name,
            actor,
            request.correlation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AgentResponse.model_validate(row)


@router.post("/agents/{agent_id}/versions", response_model=AgentVersionResponse, status_code=201)
async def create_agent_version(
    agent_id: uuid.UUID,
    request: CreateVersionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AgentVersionResponse:
    profile = await _required(session, AgentProfileModel, agent_id, "Agent")
    try:
        row = await OrganizationPersistenceService(session).create_agent_version(
            profile, request.document, actor, request.correlation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AgentVersionResponse.model_validate(row)


@router.post("/agent-versions/{version_id}/approve", response_model=AgentVersionResponse)
async def approve_agent_version(
    version_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AgentVersionResponse:
    version = await _required(session, AgentProfileVersionModel, version_id, "Agent version")
    try:
        row = await OrganizationPersistenceService(session).approve_agent_version(
            version, actor, request.correlation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AgentVersionResponse.model_validate(row)


async def _transition_agent(
    agent_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
    target: str,
) -> AgentResponse:
    profile = await _required(session, AgentProfileModel, agent_id, "Agent")
    try:
        row = await OrganizationPersistenceService(session).transition_agent(
            profile, target, actor, request.correlation_id, request.reason
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AgentResponse.model_validate(row)


@router.post("/agents/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent(
    agent_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AgentResponse:
    return await _transition_agent(agent_id, request, session, actor, "active")


@router.post("/agents/{agent_id}/suspend", response_model=AgentResponse)
async def suspend_agent(
    agent_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AgentResponse:
    return await _transition_agent(agent_id, request, session, actor, "suspended")


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, session: SessionDependency) -> AgentResponse:
    return AgentResponse.model_validate(
        await _required(session, AgentProfileModel, agent_id, "Agent")
    )


@router.post("/agents/{agent_id}/assignments", response_model=AssignmentResponse, status_code=201)
async def create_assignment(
    agent_id: uuid.UUID,
    request: CreateAssignmentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AssignmentResponse:
    profile = await _required(session, AgentProfileModel, agent_id, "Agent")
    try:
        row = await OrganizationPersistenceService(session).create_assignment(
            profile,
            request.model_dump(
                include={
                    "agent_profile_version_id",
                    "role_version_id",
                    "scope_type",
                    "scope_id",
                    "granted_capabilities",
                    "denied_capabilities",
                    "valid_from",
                    "valid_until",
                    "assignment_document",
                }
            ),
            actor,
            request.correlation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AssignmentResponse.model_validate(row)


async def _transition_assignment(
    assignment_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
    target: str,
) -> AssignmentResponse:
    assignment = await _required(session, AgentAssignmentModel, assignment_id, "Assignment")
    try:
        row = await OrganizationPersistenceService(session).transition_assignment(
            assignment, target, actor, request.correlation_id
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return AssignmentResponse.model_validate(row)


@router.post("/assignments/{assignment_id}/activate", response_model=AssignmentResponse)
async def activate_assignment(
    assignment_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AssignmentResponse:
    return await _transition_assignment(assignment_id, request, session, actor, "active")


@router.post("/assignments/{assignment_id}/revoke", response_model=AssignmentResponse)
async def revoke_assignment(
    assignment_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> AssignmentResponse:
    return await _transition_assignment(assignment_id, request, session, actor, "revoked")


@router.get("/agents/{agent_id}/assignments", response_model=list[AssignmentResponse])
async def list_assignments(
    agent_id: uuid.UUID, session: SessionDependency
) -> list[AssignmentResponse]:
    rows = (
        await session.scalars(
            select(AgentAssignmentModel)
            .where(AgentAssignmentModel.agent_profile_id == agent_id)
            .order_by(AgentAssignmentModel.created_at, AgentAssignmentModel.id)
        )
    ).all()
    return [AssignmentResponse.model_validate(row) for row in rows]


@router.post("/authority/evaluate", response_model=AuthorityEvaluationResponse)
async def evaluate_authority(
    request: AuthorityEvaluationRequest, session: SessionDependency, actor: ActorDependency
) -> AuthorityEvaluationResponse:
    value = await OrganizationPersistenceService(session).evaluate(
        request.actor_id,
        request.capability,
        request.scope_type,
        request.scope_id,
        actor,
        request.correlation_id,
    )
    return AuthorityEvaluationResponse.model_validate(value)


@router.post("/crews/compose", response_model=CrewManifestResponse, status_code=201)
async def compose_crew(
    request: ComposeCrewRequest, session: SessionDependency, actor: ActorDependency
) -> CrewManifestResponse:
    try:
        row = await OrganizationPersistenceService(session).compose_crew(
            request.workflow_type,
            request.project_id,
            request.artifact_id,
            request.policy_version,
            request.organization_id,
            actor,
            request.correlation_id,
        )
    except OrganizationPersistenceError as exc:
        raise _error(exc) from exc
    return CrewManifestResponse.model_validate(row)
