import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.dependencies import SessionDependency
from ai_enterprise.api.requirements_revision_schemas import (
    RequestRequirementsChanges,
    RequirementsArtifactLineageResponse,
    RequirementsRevisionCycleResponse,
)
from ai_enterprise.application.requirements_revision.service import (
    RequirementsRevisionService,
)
from ai_enterprise.domain.requirements_revision.models import RequirementsReviewDecision
from ai_enterprise.domain.requirements_revision.policies import RequirementsRevisionError

router = APIRouter(prefix="/requirements-runs", tags=["requirements-revisions"])


@router.post(
    "/{run_id}/artifacts/{artifact_id}/changes",
    response_model=RequirementsRevisionCycleResponse,
)
async def request_requirements_changes(
    run_id: uuid.UUID,
    artifact_id: uuid.UUID,
    request: RequestRequirementsChanges,
    session: SessionDependency,
) -> RequirementsRevisionCycleResponse:
    try:
        cycle = await RequirementsRevisionService(session).request_changes(
            project_id=(await _project_id(session, run_id)),
            requirements_run_id=run_id,
            artifact_id=artifact_id,
            reviewer=request.reviewer,
            decision=RequirementsReviewDecision(
                decision="changes_requested",
                summary=request.summary,
                findings=request.findings,
            ),
        )
    except RequirementsRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RequirementsRevisionCycleResponse.model_validate(cycle)


@router.get("/{run_id}/revisions", response_model=list[RequirementsRevisionCycleResponse])
async def list_requirements_revisions(
    run_id: uuid.UUID, session: SessionDependency
) -> list[RequirementsRevisionCycleResponse]:
    values = await RequirementsRevisionService(session).list_revisions(run_id)
    return [RequirementsRevisionCycleResponse.model_validate(item) for item in values]


@router.get("/{run_id}/artifacts", response_model=list[RequirementsArtifactLineageResponse])
async def list_requirements_artifact_history(
    run_id: uuid.UUID, session: SessionDependency
) -> list[RequirementsArtifactLineageResponse]:
    values = await RequirementsRevisionService(session).list_artifact_history(run_id)
    return [RequirementsArtifactLineageResponse.model_validate(item) for item in values]


async def _project_id(session: AsyncSession, run_id: uuid.UUID) -> uuid.UUID:
    from ai_enterprise.infrastructure.database.models import CrewRunModel

    run = await session.get(CrewRunModel, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Requirements run not found")
    return run.project_id
