import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.api.integration_schemas import RevisionAttemptRequest, RevisionAttemptResponse
from ai_enterprise.api.schemas import (
    CreatePatchReviewRequest,
    PatchReviewCheckResponse,
    PatchReviewEventResponse,
    PatchReviewFindingResponse,
    PatchReviewResponse,
)
from ai_enterprise.application.execution_workflow import (
    ExecutionNotFoundError,
    InvalidExecutionStateError,
)
from ai_enterprise.application.review.service import (
    ReviewCandidatePatchService,
    ReviewNotFoundError,
)
from ai_enterprise.application.revision_service import RevisionAttemptService
from ai_enterprise.domain.integration.exceptions import RevisionLineageError
from ai_enterprise.domain.review.exceptions import PatchReviewError
from ai_enterprise.infrastructure.database.models import (
    PatchReviewCheckModel,
    PatchReviewEventModel,
    PatchReviewFindingModel,
    PatchReviewRunModel,
)

router = APIRouter(prefix="/projects", tags=["patch-reviews"])


@router.post(
    "/{project_id}/patch-reviews/{review_id}/revision-attempts",
    response_model=RevisionAttemptResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_revision_attempt(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    request: RevisionAttemptRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RevisionAttemptResponse:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="A human actor is required")
    review = await session.get(PatchReviewRunModel, review_id)
    if review is None or review.project_id != project_id:
        raise HTTPException(status_code=404, detail="Patch review not found")
    try:
        run = await RevisionAttemptService(session).create(
            review_id=review_id, idempotency_key=request.idempotency_key, actor_id=actor.subject
        )
    except RevisionLineageError as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    return RevisionAttemptResponse.model_validate(run)


@router.post(
    "/{project_id}/executions/{execution_id}/reviews",
    response_model=PatchReviewResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_patch_review(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    request: CreatePatchReviewRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> PatchReviewResponse:
    service = ReviewCandidatePatchService(
        session=session,
        settings=settings,
    )

    try:
        review = await service.request_review(
            project_id=project_id,
            execution_id=execution_id,
            idempotency_key=request.idempotency_key,
            actor_id="local-user",
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except (InvalidExecutionStateError, PatchReviewError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return PatchReviewResponse.model_validate(review)


@router.get(
    "/{project_id}/patch-reviews",
    response_model=list[PatchReviewResponse],
)
async def list_patch_reviews(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[PatchReviewResponse]:
    result = await session.execute(
        select(PatchReviewRunModel)
        .where(PatchReviewRunModel.project_id == project_id)
        .order_by(PatchReviewRunModel.created_at)
    )

    return [PatchReviewResponse.model_validate(review) for review in result.scalars().all()]


@router.get(
    "/{project_id}/patch-reviews/{review_id}",
    response_model=PatchReviewResponse,
)
async def get_patch_review(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    session: SessionDependency,
) -> PatchReviewResponse:
    review = await session.get(PatchReviewRunModel, review_id)

    if review is None or review.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Patch review not found",
        )

    return PatchReviewResponse.model_validate(review)


@router.get(
    "/{project_id}/patch-reviews/{review_id}/findings",
    response_model=list[PatchReviewFindingResponse],
)
async def list_patch_review_findings(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    session: SessionDependency,
) -> list[PatchReviewFindingResponse]:
    review = await session.get(PatchReviewRunModel, review_id)

    if review is None or review.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Patch review not found",
        )

    result = await session.execute(
        select(PatchReviewFindingModel)
        .where(PatchReviewFindingModel.patch_review_run_id == review_id)
        .order_by(
            PatchReviewFindingModel.blocking.desc(),
            PatchReviewFindingModel.created_at,
        )
    )

    return [
        PatchReviewFindingResponse.model_validate(finding) for finding in result.scalars().all()
    ]


@router.get(
    "/{project_id}/patch-reviews/{review_id}/checks",
    response_model=list[PatchReviewCheckResponse],
)
async def list_patch_review_checks(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    session: SessionDependency,
) -> list[PatchReviewCheckResponse]:
    review = await session.get(PatchReviewRunModel, review_id)

    if review is None or review.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Patch review not found",
        )

    result = await session.execute(
        select(PatchReviewCheckModel)
        .where(PatchReviewCheckModel.patch_review_run_id == review_id)
        .order_by(PatchReviewCheckModel.sequence)
    )

    return [PatchReviewCheckResponse.model_validate(check) for check in result.scalars().all()]


@router.get(
    "/{project_id}/patch-reviews/{review_id}/events",
    response_model=list[PatchReviewEventResponse],
)
async def list_patch_review_events(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    session: SessionDependency,
) -> list[PatchReviewEventResponse]:
    review = await session.get(PatchReviewRunModel, review_id)

    if review is None or review.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Patch review not found",
        )

    result = await session.execute(
        select(PatchReviewEventModel)
        .where(PatchReviewEventModel.patch_review_run_id == review_id)
        .order_by(PatchReviewEventModel.occurred_at)
    )

    return [PatchReviewEventResponse.model_validate(event) for event in result.scalars().all()]
