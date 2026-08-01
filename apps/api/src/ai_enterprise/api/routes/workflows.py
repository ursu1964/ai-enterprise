import uuid

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.dependencies import SessionDependency
from ai_enterprise.api.workflow_schemas import (
    CancelWorkflowRequest,
    StartWorkflowRequest,
    WorkflowResponse,
    WorkflowTransitionResponse,
)
from ai_enterprise.application.workflow.repository import WorkflowNotFoundError
from ai_enterprise.application.workflow.service import WorkflowConflictError, WorkflowService

router = APIRouter(tags=["workflows"])


@router.post(
    "/projects/{project_id}/workflow",
    response_model=WorkflowResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_workflow(
    project_id: uuid.UUID, request: StartWorkflowRequest, session: SessionDependency
) -> WorkflowResponse:
    try:
        workflow = await WorkflowService(session).start(
            project_id=project_id, actor_id=request.actor_id
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return WorkflowResponse.model_validate(workflow)


@router.get("/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: uuid.UUID, session: SessionDependency) -> WorkflowResponse:
    try:
        workflow = await WorkflowService(session).repository.get(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    return WorkflowResponse.model_validate(workflow)


@router.get("/workflows/{workflow_id}/history", response_model=list[WorkflowTransitionResponse])
async def workflow_history(
    workflow_id: uuid.UUID, session: SessionDependency
) -> list[WorkflowTransitionResponse]:
    try:
        rows = await WorkflowService(session).history(workflow_id)
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    return [WorkflowTransitionResponse.model_validate(row) for row in rows]


@router.post("/workflows/{workflow_id}/cancel", response_model=WorkflowResponse)
async def cancel_workflow(
    workflow_id: uuid.UUID, request: CancelWorkflowRequest, session: SessionDependency
) -> WorkflowResponse:
    try:
        workflow = await WorkflowService(session).cancel(
            workflow_id=workflow_id, actor_id=request.actor_id, reason=request.reason
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Workflow not found") from exc
    except WorkflowConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return WorkflowResponse.model_validate(workflow)
