import uuid

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.integration_schemas import (
    IntegrationApprovalRequest,
    IntegrationApprovalResponse,
    IntegrationAttemptResponse,
    IntegrationEligibilityResponse,
)
from ai_enterprise.application.integration.service import (
    ControlledIntegrationService,
    IntegrationNotFoundError,
)
from ai_enterprise.application.workflow.service import WorkflowService
from ai_enterprise.config import get_settings
from ai_enterprise.domain.integration.exceptions import IntegrationError
from ai_enterprise.infrastructure.database.models import IntegrationAttemptModel

router = APIRouter(tags=["controlled-integration"])


def _require_integration_attempt_create(actor: Actor) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Integration operator authority is required")
    try:
        require_capability(actor, "integration.attempt.create", "global")
    except HTTPException as exc:
        raise HTTPException(
            status_code=403, detail="Integration operator authority is required"
        ) from exc


def _require_integration_read(actor: Actor, project_id: uuid.UUID) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Human integration authority is required")
    require_capability(actor, "integration.read", f"project:{project_id}")


@router.get(
    "/patches/{execution_run_id}/integration-eligibility",
    response_model=IntegrationEligibilityResponse,
)
async def get_eligibility(
    execution_run_id: uuid.UUID, session: SessionDependency
) -> IntegrationEligibilityResponse:
    try:
        value = await ControlledIntegrationService(session).evaluate_eligibility(execution_run_id)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return IntegrationEligibilityResponse.model_validate(value)


@router.post(
    "/patches/{execution_run_id}/integration-approvals",
    response_model=IntegrationApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def approve_integration(
    execution_run_id: uuid.UUID,
    request: IntegrationApprovalRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> IntegrationApprovalResponse:
    try:
        value = await ControlledIntegrationService(session).approve(
            execution_run_id=execution_run_id,
            actor_subject=actor.subject,
            actor_type=actor.actor_type,
            actor_role=actor.role,
            target_branch=request.target_branch,
            reason=request.reason,
        )
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrationError as exc:
        code = 403 if exc.code == "HUMAN_APPROVAL_REQUIRED" else 409
        raise HTTPException(
            status_code=code, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    return IntegrationApprovalResponse.model_validate(value)


@router.post(
    "/integration-approvals/{approval_id}/attempts",
    response_model=IntegrationAttemptResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_integration_attempt(
    approval_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> IntegrationAttemptResponse:
    _require_integration_attempt_create(actor)
    try:
        value = await ControlledIntegrationService(session).create_attempt(approval_id)
    except IntegrationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    await WorkflowService(session, get_settings()).notify(value.project_id)
    return IntegrationAttemptResponse.model_validate(value)


@router.get("/integration-attempts/{attempt_id}", response_model=IntegrationAttemptResponse)
async def get_integration_attempt(
    attempt_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> IntegrationAttemptResponse:
    value = await session.get(IntegrationAttemptModel, attempt_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Integration attempt not found")
    _require_integration_read(actor, value.project_id)
    return IntegrationAttemptResponse.model_validate(value)
