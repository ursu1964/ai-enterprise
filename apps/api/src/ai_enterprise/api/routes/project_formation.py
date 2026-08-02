import uuid

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.project_formation_schemas import (
    FormationRequest,
    FormationResponse,
    MockFactoryStartResponse,
)
from ai_enterprise.application.mock_factory_autonomy import MockEnterpriseAutonomyService
from ai_enterprise.application.project_formation_service import (
    ProjectFormationError,
    ProjectFormationService,
)

router = APIRouter(prefix="/project-formation", tags=["project-formation"])


def _require_human(actor: ActorDependency) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Human project-formation authority is required")


@router.post("/packs", response_model=FormationResponse, status_code=201)
async def create_formation_pack(
    request: FormationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormationResponse:
    _require_human(actor)
    try:
        return await ProjectFormationService(session).create_formation_pack(
            request, actor_id=actor.subject
        )
    except ProjectFormationError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/mock-factory/start", response_model=MockFactoryStartResponse, status_code=202)
async def start_mock_factory(
    session: SessionDependency,
    settings: SettingsDependency,
    actor: ActorDependency,
) -> MockFactoryStartResponse:
    _require_human(actor)
    return await MockEnterpriseAutonomyService(session, settings).start_mock_factory(
        actor_id=actor.subject
    )


@router.post("/projects/{project_id}/packs", response_model=FormationResponse, status_code=201)
async def create_project_formation_pack(
    project_id: uuid.UUID,
    request: FormationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FormationResponse:
    _require_human(actor)
    if request.project_id != project_id:
        raise HTTPException(400, "Path project_id must match request project_id")
    try:
        return await ProjectFormationService(session).create_formation_pack(
            request, actor_id=actor.subject
        )
    except ProjectFormationError as exc:
        raise HTTPException(404, str(exc)) from exc
