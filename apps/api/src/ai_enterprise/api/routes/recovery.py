import uuid

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.recovery_schemas import (
    RecoveryAssessmentResponse,
    RecoveryAttemptRequest,
    RecoveryAttemptResponse,
    RecoveryIncidentRequest,
    RecoveryIncidentResponse,
    RollbackApprovalRequest,
    RollbackApprovalResponse,
)
from ai_enterprise.application.recovery.service import (
    RecoveryControlPlaneService,
    RecoveryNotFoundError,
)
from ai_enterprise.domain.recovery.exceptions import RecoveryError
from ai_enterprise.infrastructure.database.models import (
    RecoveryAssessmentModel,
    RecoveryAttemptModel,
    RecoveryIncidentModel,
)

router = APIRouter(tags=["governed-recovery"])


def _error(exc: RecoveryError) -> HTTPException:
    status_code = {
        "ROLLBACK_RECORD_NOT_FOUND": 404,
        "ROLLBACK_APPROVAL_HUMAN_REQUIRED": 403,
        "RECOVERY_ASSESSMENT_STALE": 409,
        "ROLLBACK_APPROVAL_NOT_ACTIVE": 409,
    }.get(exc.code, 409)
    return HTTPException(status_code=status_code, detail={"code": exc.code, "message": str(exc)})


def _require_recovery_read(actor: Actor, project_id: uuid.UUID) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Human recovery authority is required")
    require_capability(actor, "recovery.read", f"project:{project_id}")


def _require_recovery_action(actor: Actor, action: str) -> None:
    if actor.actor_type != "human":
        raise HTTPException(status_code=403, detail="Human recovery authority is required")
    try:
        require_capability(actor, f"recovery.{action}", "global")
    except HTTPException as exc:
        raise HTTPException(status_code=403, detail="Recovery authority is required") from exc


@router.post(
    "/integration-attempts/{attempt_id}/recovery-incidents",
    response_model=RecoveryIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    attempt_id: uuid.UUID,
    request: RecoveryIncidentRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RecoveryIncidentResponse:
    _require_recovery_action(actor, "incident.create")
    try:
        value = await RecoveryControlPlaneService(session).create_incident(
            integration_attempt_id=attempt_id,
            actor_subject=actor.subject,
            actor_type=actor.actor_type,
            actor_role=actor.role,
            **request.model_dump(),
        )
    except RecoveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecoveryError as exc:
        raise _error(exc) from exc
    return RecoveryIncidentResponse.model_validate(value)


@router.post(
    "/recovery-incidents/{incident_id}/assessments",
    response_model=RecoveryAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assess_recovery(
    incident_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> RecoveryAssessmentResponse:
    _require_recovery_action(actor, "assessment.create")
    try:
        value = await RecoveryControlPlaneService(session).assess_from_trusted_checkout(
            incident_id=incident_id,
            actor_subject=actor.subject,
            actor_type=actor.actor_type,
            actor_role=actor.role,
        )
    except RecoveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecoveryError as exc:
        raise _error(exc) from exc
    return RecoveryAssessmentResponse.model_validate(value)


@router.post(
    "/recovery-assessments/{assessment_id}/approvals",
    response_model=RollbackApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def approve_rollback(
    assessment_id: uuid.UUID,
    request: RollbackApprovalRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RollbackApprovalResponse:
    _require_recovery_action(actor, "approval.create")
    try:
        value = await RecoveryControlPlaneService(session).approve(
            assessment_id=assessment_id,
            actor_subject=actor.subject,
            actor_type=actor.actor_type,
            actor_role=actor.role,
            reason=request.reason,
        )
    except RecoveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecoveryError as exc:
        raise _error(exc) from exc
    return RollbackApprovalResponse.model_validate(value)


@router.post(
    "/rollback-approvals/{approval_id}/attempts",
    response_model=RecoveryAttemptResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_recovery_attempt(
    approval_id: uuid.UUID,
    request: RecoveryAttemptRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> RecoveryAttemptResponse:
    del request
    _require_recovery_action(actor, "attempt.create")
    try:
        value = await RecoveryControlPlaneService(session).create_attempt(
            approval_id=approval_id,
            actor_subject=actor.subject,
            actor_type=actor.actor_type,
            actor_role=actor.role,
        )
    except RecoveryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RecoveryError as exc:
        raise _error(exc) from exc
    return RecoveryAttemptResponse.model_validate(value)


@router.get("/recovery-incidents/{incident_id}", response_model=RecoveryIncidentResponse)
async def get_incident(
    incident_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> RecoveryIncidentResponse:
    value = await session.get(RecoveryIncidentModel, incident_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Recovery incident not found")
    _require_recovery_read(actor, value.project_id)
    return RecoveryIncidentResponse.model_validate(value)


@router.get("/recovery-assessments/{assessment_id}", response_model=RecoveryAssessmentResponse)
async def get_assessment(
    assessment_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> RecoveryAssessmentResponse:
    value = await session.get(RecoveryAssessmentModel, assessment_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Recovery assessment not found")
    incident = await session.get(RecoveryIncidentModel, value.incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Recovery incident not found")
    _require_recovery_read(actor, incident.project_id)
    return RecoveryAssessmentResponse.model_validate(value)


@router.get("/recovery-attempts/{attempt_id}", response_model=RecoveryAttemptResponse)
async def get_attempt(
    attempt_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> RecoveryAttemptResponse:
    value = await session.get(RecoveryAttemptModel, attempt_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Recovery attempt not found")
    _require_recovery_read(actor, value.project_id)
    return RecoveryAttemptResponse.model_validate(value)
