from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import ActorDependency
from ai_enterprise.api.evolution_schemas import (
    ConstitutionalAssessmentRequest,
    EvolutionAssessmentResponse,
    ExceptionAssessmentRequest,
    PrerequisiteAssessmentRequest,
    ShadowCommandAssessmentRequest,
)
from ai_enterprise.application.evolution.service import EvolutionGovernanceService
from ai_enterprise.domain.evolution.entities import (
    ConstitutionalAmendment,
    ConstitutionalApproval,
    PolicyException,
    ShadowCommand,
)
from ai_enterprise.domain.evolution.exceptions import EvolutionError

router = APIRouter(prefix="/evolution-assessments", tags=["governed-evolution"])


def _require_governor(actor_type: str, role: str) -> None:
    if actor_type != "human" or role != "evolution_governor":
        raise HTTPException(status_code=403, detail="Human evolution_governor required")


def _failure(exc: EvolutionError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": exc.code, "message": str(exc)},
    )


@router.post("/prerequisites", response_model=EvolutionAssessmentResponse)
async def assess_prerequisites(
    request: PrerequisiteAssessmentRequest, actor: ActorDependency
) -> EvolutionAssessmentResponse:
    _require_governor(actor.actor_type, actor.role)
    try:
        EvolutionGovernanceService().require_platform_prerequisites(request.available_prerequisites)
    except EvolutionError as exc:
        raise _failure(exc) from exc
    return EvolutionAssessmentResponse(
        eligible=True, assessment_type="prerequisites", message="Prerequisites satisfied"
    )


@router.post("/shadow-commands", response_model=EvolutionAssessmentResponse)
async def assess_shadow_command(
    request: ShadowCommandAssessmentRequest, actor: ActorDependency
) -> EvolutionAssessmentResponse:
    _require_governor(actor.actor_type, actor.role)
    try:
        EvolutionGovernanceService().assess_shadow_command(ShadowCommand(**request.model_dump()))
    except EvolutionError as exc:
        raise _failure(exc) from exc
    return EvolutionAssessmentResponse(
        eligible=True, assessment_type="shadow_command", message="Command is side-effect free"
    )


@router.post("/policy-exceptions", response_model=EvolutionAssessmentResponse)
async def assess_policy_exception(
    request: ExceptionAssessmentRequest, actor: ActorDependency
) -> EvolutionAssessmentResponse:
    _require_governor(actor.actor_type, actor.role)
    try:
        EvolutionGovernanceService().assess_exception(
            PolicyException(
                id=request.exception_id,
                policy_id=request.policy_id,
                owner_id=request.owner_id,
                reason=request.reason,
                scope_hash=request.scope_hash,
                compensating_control_ids=request.compensating_control_ids,
                removal_plan_hash=request.removal_plan_hash,
                expires_at=request.expires_at,
            ),
            datetime.now(UTC),
        )
    except EvolutionError as exc:
        raise _failure(exc) from exc
    return EvolutionAssessmentResponse(
        eligible=True, assessment_type="policy_exception", message="Exception is bounded"
    )


@router.post("/constitutional-amendments", response_model=EvolutionAssessmentResponse)
async def assess_constitutional_amendment(
    request: ConstitutionalAssessmentRequest, actor: ActorDependency
) -> EvolutionAssessmentResponse:
    _require_governor(actor.actor_type, actor.role)
    amendment = ConstitutionalAmendment(
        id=request.amendment_id,
        change_proposal_id=request.change_proposal_id,
        constitutional_policy_id=request.constitutional_policy_id,
        proposed_by=request.proposed_by,
        candidate_hash=request.candidate_hash,
        required_roles=request.required_roles,
        minimum_approval_count=request.minimum_approval_count,
        cooling_off_until=request.cooling_off_until,
        approvals=tuple(ConstitutionalApproval(**item.model_dump()) for item in request.approvals),
    )
    try:
        EvolutionGovernanceService().assess_constitutional_activation(amendment, datetime.now(UTC))
    except EvolutionError as exc:
        raise _failure(exc) from exc
    return EvolutionAssessmentResponse(
        eligible=True,
        assessment_type="constitutional_amendment",
        message="Governance prerequisites satisfied; no activation performed",
    )
