import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.project_formation_schemas import (
    ClientBlueprintClarificationAnswerRequest,
    ClientBlueprintImportRequest,
    ClientBlueprintResponse,
    ClientBlueprintReviewRequest,
    FormationRequest,
    FormationResponse,
    FoundryWorkspaceRequest,
    FoundryWorkspaceResponse,
    MockFactoryPreviewResponse,
    MockFactoryStartResponse,
)
from ai_enterprise.application.mock_factory_autonomy import MockEnterpriseAutonomyService
from ai_enterprise.application.project_formation_service import (
    ProjectFormationError,
    ProjectFormationService,
)
from ai_enterprise.application.project_foundry_workspace import (
    ProjectFoundryWorkspaceError,
    ProjectFoundryWorkspaceService,
)

router = APIRouter(prefix="/project-formation", tags=["project-formation"])


def _require_human(actor: ActorDependency) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Human project-formation authority is required")


def _formation_error(exc: ProjectFormationError) -> HTTPException:
    message = str(exc)
    if message == "Project not found":
        return HTTPException(404, message)
    if "validation" in message or "AEPM" in message or "Clarification" in message:
        return HTTPException(422, message)
    return HTTPException(400, message)


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
        raise _formation_error(exc) from exc


@router.post("/client-blueprints/import", response_model=ClientBlueprintResponse, status_code=201)
async def import_client_blueprint_manifest(
    request: ClientBlueprintImportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ClientBlueprintResponse:
    _require_human(actor)
    try:
        return await ProjectFormationService(session).import_client_blueprint_manifest(
            request, actor_id=actor.subject
        )
    except ProjectFormationError as exc:
        raise _formation_error(exc) from exc


@router.post(
    "/client-blueprints/{project_id}/review",
    response_model=ClientBlueprintResponse,
)
async def review_client_blueprint(
    project_id: uuid.UUID,
    request: ClientBlueprintReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ClientBlueprintResponse:
    _require_human(actor)
    try:
        return await ProjectFormationService(session).review_client_blueprint(
            project_id, request, actor_id=actor.subject
        )
    except ProjectFormationError as exc:
        raise _formation_error(exc) from exc


@router.post(
    "/client-blueprints/{project_id}/clarifications/answers",
    response_model=ClientBlueprintResponse,
)
async def answer_client_blueprint_clarifications(
    project_id: uuid.UUID,
    request: ClientBlueprintClarificationAnswerRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ClientBlueprintResponse:
    _require_human(actor)
    try:
        return await ProjectFormationService(session).answer_client_blueprint_clarifications(
            project_id, request, actor_id=actor.subject
        )
    except ProjectFormationError as exc:
        raise _formation_error(exc) from exc


@router.get(
    "/client-blueprints/{project_id}/download",
    response_class=PlainTextResponse,
)
async def download_client_blueprint(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    artifact_id: uuid.UUID | None = None,
) -> PlainTextResponse:
    _require_human(actor)
    try:
        markdown = await ProjectFormationService(session).get_client_blueprint_markdown(
            project_id, artifact_id
        )
    except ProjectFormationError as exc:
        raise _formation_error(exc) from exc
    return PlainTextResponse(
        markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="client-project-blueprint.md"'},
    )


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


@router.get("/mock-factory/preview", response_model=MockFactoryPreviewResponse)
async def preview_mock_factory(
    session: SessionDependency,
    settings: SettingsDependency,
    actor: ActorDependency,
) -> MockFactoryPreviewResponse:
    _require_human(actor)
    return await MockEnterpriseAutonomyService(session, settings).preview_mock_factory()


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
        raise _formation_error(exc) from exc


@router.post(
    "/projects/{project_id}/foundry-workspace",
    response_model=FoundryWorkspaceResponse,
    status_code=201,
)
async def create_project_foundry_workspace(
    project_id: uuid.UUID,
    request: FoundryWorkspaceRequest,
    session: SessionDependency,
    settings: SettingsDependency,
    actor: ActorDependency,
) -> FoundryWorkspaceResponse:
    _require_human(actor)
    try:
        return await ProjectFoundryWorkspaceService(session, settings).generate_workspace(
            project_id,
            request,
            actor_id=actor.subject,
        )
    except ProjectFoundryWorkspaceError as exc:
        status_code = 422 if exc.missing_information else 404
        raise HTTPException(
            status_code,
            {
                "message": str(exc),
                "missing_information": exc.missing_information,
                "next_action": (
                    "Complete the missing Foundry intake sections, then generate the workspace "
                    "again."
                    if exc.missing_information
                    else "Confirm the project exists and retry workspace generation."
                ),
            },
        ) from exc
