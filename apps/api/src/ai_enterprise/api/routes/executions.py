import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ai_enterprise.api.dependencies import SessionDependency, SettingsDependency
from ai_enterprise.api.schemas import (
    ExecutionEventResponse,
    ExecutionRunResponse,
    ExecutionTestResultResponse,
    RequestExecutionRequest,
)
from ai_enterprise.application.execution_workflow import (
    ExecutionApplicationService,
    ExecutionNotFoundError,
    InvalidExecutionStateError,
)
from ai_enterprise.domain.execution.exceptions import (
    IdempotencyConflictError,
)
from ai_enterprise.infrastructure.database.models import (
    ExecutionEventModel,
    ExecutionRunModel,
    ExecutionTestResultModel,
)

router = APIRouter(prefix="/projects", tags=["executions"])


@router.post(
    "/{project_id}/executions",
    response_model=ExecutionRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_execution(
    project_id: uuid.UUID,
    request: RequestExecutionRequest,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ExecutionRunResponse:
    service = ExecutionApplicationService(
        session=session,
        settings=settings,
    )

    try:
        run = await service.request_execution(
            project_id=project_id,
            work_package_id=request.work_package_id,
            idempotency_key=request.idempotency_key,
            actor_id="local-user",
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except InvalidExecutionStateError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return ExecutionRunResponse.model_validate(run)


@router.get(
    "/{project_id}/executions",
    response_model=list[ExecutionRunResponse],
)
async def list_executions(
    project_id: uuid.UUID,
    session: SessionDependency,
) -> list[ExecutionRunResponse]:
    result = await session.execute(
        select(ExecutionRunModel)
        .where(ExecutionRunModel.project_id == project_id)
        .order_by(ExecutionRunModel.created_at)
    )

    return [
        ExecutionRunResponse.model_validate(run)
        for run in result.scalars().all()
    ]


@router.get(
    "/{project_id}/executions/{execution_id}",
    response_model=ExecutionRunResponse,
)
async def get_execution(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    session: SessionDependency,
) -> ExecutionRunResponse:
    run = await session.get(ExecutionRunModel, execution_id)

    if run is None or run.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Execution not found",
        )

    return ExecutionRunResponse.model_validate(run)


@router.get(
    "/{project_id}/executions/{execution_id}/test-results",
    response_model=list[ExecutionTestResultResponse],
)
async def list_test_results(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    session: SessionDependency,
) -> list[ExecutionTestResultResponse]:
    run = await session.get(ExecutionRunModel, execution_id)

    if run is None or run.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Execution not found",
        )

    result = await session.execute(
        select(ExecutionTestResultModel)
        .where(ExecutionTestResultModel.execution_run_id == execution_id)
        .order_by(ExecutionTestResultModel.sequence)
    )

    return [
        ExecutionTestResultResponse.model_validate(item)
        for item in result.scalars().all()
    ]


@router.get(
    "/{project_id}/executions/{execution_id}/events",
    response_model=list[ExecutionEventResponse],
)
async def list_execution_events(
    project_id: uuid.UUID,
    execution_id: uuid.UUID,
    session: SessionDependency,
) -> list[ExecutionEventResponse]:
    run = await session.get(ExecutionRunModel, execution_id)

    if run is None or run.project_id != project_id:
        raise HTTPException(
            status_code=404,
            detail="Execution not found",
        )

    result = await session.execute(
        select(ExecutionEventModel)
        .where(ExecutionEventModel.execution_run_id == execution_id)
        .order_by(ExecutionEventModel.occurred_at)
    )

    return [
        ExecutionEventResponse.model_validate(event)
        for event in result.scalars().all()
    ]
