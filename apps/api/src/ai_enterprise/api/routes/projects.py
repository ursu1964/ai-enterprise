import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.dependencies import SessionDependency, SettingsDependency
from ai_enterprise.api.schemas import (
    ApprovalRequest,
    ArtifactResponse,
    CreateProjectRequest,
    ProjectResponse,
    RunResponse,
    WorkPackageApprovalRequest,
    WorkPackageResponse,
)
from ai_enterprise.application.project_workflow import (
    ArtifactNotFoundError,
    InvalidProjectStateError,
    ProjectNotFoundError,
    ProjectWorkflowService,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    WorkPackageModel,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    request: CreateProjectRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    project = await service.create_project(
        name=request.name,
        description=request.description,
        repository_path=request.repository_path,
        repository_url=request.repository_url,
        default_branch=request.default_branch,
        actor_id="local-user",
    )

    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/requirements-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_requirements_run(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_requirements_run(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RunResponse.model_validate(run)


@router.get(
    "/{project_id}/artifacts",
    response_model=list[ArtifactResponse],
)
async def list_artifacts(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[ArtifactResponse]:
    result = await session.execute(
        select(ArtifactModel)
        .where(ArtifactModel.project_id == project_id)
        .order_by(ArtifactModel.created_at)
    )

    return [
        ArtifactResponse.model_validate(artifact)
        for artifact in result.scalars().all()
    ]


@router.post(
    "/{project_id}/artifacts/{artifact_id}/approval",
    response_model=ProjectResponse,
)
async def approve_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: ApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        project = await service.approve_requirements(
            project_id=project_id,
            artifact_id=artifact_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/architecture-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_architecture_run(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_architecture_run(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RunResponse.model_validate(run)


@router.post(
    "/{project_id}/architecture-artifacts/"
    "{artifact_id}/approval",
    response_model=ProjectResponse,
)
async def approve_architecture_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: ApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ProjectResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        project = await service.approve_architecture(
            project_id=project_id,
            artifact_id=artifact_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Artifact not found",
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ProjectResponse.model_validate(project)


@router.post(
    "/{project_id}/work-package-runs",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_work_package_planning(
    project_id: uuid.UUID,
    session: SessionDependency,
    settings: SettingsDependency,
) -> RunResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.queue_work_package_planning(
            project_id=project_id,
            actor_id="local-user",
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return RunResponse.model_validate(run)


@router.get(
    "/{project_id}/work-packages",
    response_model=list[WorkPackageResponse],
)
async def list_work_packages(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[WorkPackageResponse]:
    result = await session.execute(
        select(WorkPackageModel)
        .where(WorkPackageModel.project_id == project_id)
        .order_by(WorkPackageModel.created_at)
    )

    return [
        WorkPackageResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.post(
    "/{project_id}/work-packages/{work_package_id}/approval",
    response_model=WorkPackageResponse,
)
async def approve_work_package(
    project_id: uuid.UUID,
    work_package_id: uuid.UUID,
    request: WorkPackageApprovalRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> WorkPackageResponse:
    service = ProjectWorkflowService(
        session=session,
        settings=settings,
    )

    try:
        work_package = await service.approve_work_package(
            project_id=project_id,
            work_package_id=work_package_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comment=request.comment,
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Project not found",
        ) from exc
    except ArtifactNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Work package not found",
        ) from exc
    except InvalidProjectStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return WorkPackageResponse.model_validate(work_package)
