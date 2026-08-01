import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.decomposition_schemas import (
    ArtifactResponse,
    FindingResponse,
    ReviewDecompositionRequest,
    ReviewResponse,
    RevisionDecompositionRequest,
    RunResponse,
    StartDecompositionRequest,
    WorkPackageResponse,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.decomposition_service import DecompositionError, DecompositionService
from ai_enterprise.infrastructure.decomposition.models import (
    DecompositionArtifactModel,
    DecompositionRunModel,
    ValidationFindingModel,
    WorkPackageModel,
)

router = APIRouter(tags=["work-package-decomposition"])


def _error(exc: DecompositionError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.post(
    "/projects/{project_id}/work-package-decompositions",
    response_model=RunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start(
    project_id: uuid.UUID,
    request: StartDecompositionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RunResponse:
    try:
        value = await DecompositionService(session).start(
            project_id,
            request.architecture_artifact_id,
            request.repository_uri,
            request.base_commit_sha,
            actor,
        )
    except DecompositionError as exc:
        raise _error(exc) from exc
    return RunResponse.model_validate(value)


@router.get("/work-package-decompositions/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, session: SessionDependency) -> RunResponse:
    value = await session.get(DecompositionRunModel, run_id)
    if value is None:
        raise HTTPException(404, "Decomposition run not found")
    return RunResponse.model_validate(value)


async def _artifact(run_id: uuid.UUID, session: SessionDependency) -> DecompositionArtifactModel:
    value = await session.scalar(
        select(DecompositionArtifactModel).where(
            DecompositionArtifactModel.decomposition_run_id == run_id
        )
    )
    if value is None:
        raise HTTPException(404, "Decomposition artifact not found")
    return value


@router.get("/work-package-decompositions/{run_id}/artifact", response_model=ArtifactResponse)
async def get_artifact(run_id: uuid.UUID, session: SessionDependency) -> ArtifactResponse:
    return ArtifactResponse.model_validate(await _artifact(run_id, session))


@router.get(
    "/work-package-decompositions/{run_id}/validation-findings",
    response_model=list[FindingResponse],
)
async def findings(run_id: uuid.UUID, session: SessionDependency) -> list[FindingResponse]:
    artifact = await _artifact(run_id, session)
    rows = list(
        (
            await session.scalars(
                select(ValidationFindingModel)
                .where(ValidationFindingModel.decomposition_artifact_id == artifact.id)
                .order_by(
                    ValidationFindingModel.severity,
                    ValidationFindingModel.validator_code,
                    ValidationFindingModel.package_key,
                    ValidationFindingModel.path,
                )
            )
        ).all()
    )
    return [FindingResponse.model_validate(row) for row in rows]


@router.get("/work-package-decompositions/{run_id}/graph")
async def graph(run_id: uuid.UUID, session: SessionDependency) -> dict[str, object]:
    artifact = await _artifact(run_id, session)
    return artifact.artifact_document["graph"]


@router.post(
    "/work-package-decomposition-artifacts/{artifact_id}/reviews",
    response_model=ReviewResponse,
    status_code=201,
)
async def review(
    artifact_id: uuid.UUID,
    request: ReviewDecompositionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> ReviewResponse:
    try:
        value = await DecompositionService(session).review(
            artifact_id, request.decision, request.artifact_hash, request.comments, actor
        )
    except DecompositionError as exc:
        raise _error(exc) from exc
    return ReviewResponse.model_validate(value)


@router.post(
    "/work-package-decomposition-artifacts/{artifact_id}/revision",
    response_model=RunResponse,
    status_code=202,
)
async def revision(
    artifact_id: uuid.UUID,
    request: RevisionDecompositionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RunResponse:
    try:
        value = await DecompositionService(session).revision(
            artifact_id, request.artifact_hash, request.comments, actor
        )
    except DecompositionError as exc:
        raise _error(exc) from exc
    return RunResponse.model_validate(value)


@router.get(
    "/work-package-decomposition-artifacts/{artifact_id}/work-packages",
    response_model=list[WorkPackageResponse],
)
async def packages(artifact_id: uuid.UUID, session: SessionDependency) -> list[WorkPackageResponse]:
    artifact = await session.get(DecompositionArtifactModel, artifact_id)
    if artifact is None:
        raise HTTPException(404, "Decomposition artifact not found")
    if artifact.status != "approved":
        raise HTTPException(409, "Work packages are not executable before artifact approval")
    rows = list(
        (
            await session.scalars(
                select(WorkPackageModel)
                .where(WorkPackageModel.decomposition_artifact_id == artifact_id)
                .order_by(WorkPackageModel.sequence_number)
            )
        ).all()
    )
    return [WorkPackageResponse.model_validate(row) for row in rows]
