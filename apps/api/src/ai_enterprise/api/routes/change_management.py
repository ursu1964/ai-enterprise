import uuid
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from ai_enterprise.api.change_management_authority import governed_change_actor
from ai_enterprise.api.change_management_schemas import (
    ChangeDecisionResponse,
    ChangeObservationResponse,
    ChangeOutcomeResponse,
    ChangeProposalResponse,
    ChangeSetResponse,
    ChangeTimelineResponse,
    ImpactAssessmentResponse,
    ValidationPlanResponse,
)
from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.application.change_management.dto import (
    CreateChangeProposal,
    CreateChangeSet,
    CreateValidationPlan,
    RecordChangeDecision,
    RecordChangeObservation,
    RecordChangeOutcome,
    RecordImpactAssessment,
)
from ai_enterprise.application.change_management.service import (
    GovernedChangeNotFound,
    GovernedChangeService,
)
from ai_enterprise.domain.change_management.exceptions import GovernedChangeError
from ai_enterprise.infrastructure.change_management.repository import (
    SqlAlchemyChangeAuditSink,
    SqlAlchemyGovernedChangeRepository,
)

router = APIRouter(prefix="/change-proposals", tags=["governed-change"])


def _service(session: SessionDependency) -> GovernedChangeService:
    return GovernedChangeService(
        SqlAlchemyGovernedChangeRepository(session),
        SqlAlchemyChangeAuditSink(session),
    )


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, GovernedChangeNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, GovernedChangeError):
        return HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": str(exc)},
        )
    return HTTPException(status_code=500, detail="Governed change operation failed")


@router.post("", response_model=ChangeProposalResponse, status_code=status.HTTP_201_CREATED)
async def create_proposal(
    request: CreateChangeProposal,
    session: SessionDependency,
    actor: ActorDependency,
) -> ChangeProposalResponse:
    try:
        value = await _service(session).create_proposal(
            request, governed_change_actor(actor, "change.create")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeProposalResponse.model_validate(value)


@router.get("/{proposal_id}", response_model=ChangeProposalResponse)
async def get_proposal(
    proposal_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> ChangeProposalResponse:
    governed_change_actor(actor, "change.read")
    value = await SqlAlchemyGovernedChangeRepository(session).get_proposal(proposal_id)
    if value is None:
        raise HTTPException(status_code=404, detail="Change proposal not found")
    return ChangeProposalResponse.model_validate(value)


@router.post(
    "/{proposal_id}/change-sets",
    response_model=ChangeSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_change_set(
    proposal_id: uuid.UUID,
    request: CreateChangeSet,
    session: SessionDependency,
    actor: ActorDependency,
) -> ChangeSetResponse:
    try:
        value = await _service(session).add_change_set(
            proposal_id, request, governed_change_actor(actor, "change.create")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeSetResponse.model_validate(asdict(value))


@router.post("/{proposal_id}/submit", response_model=ChangeProposalResponse)
async def submit_proposal(
    proposal_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> ChangeProposalResponse:
    try:
        value = await _service(session).submit(
            proposal_id, governed_change_actor(actor, "change.submit")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeProposalResponse.model_validate(value)


@router.post(
    "/{proposal_id}/impact-assessments",
    response_model=ImpactAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assess_impact(
    proposal_id: uuid.UUID,
    request: RecordImpactAssessment,
    session: SessionDependency,
    actor: ActorDependency,
) -> ImpactAssessmentResponse:
    try:
        value = await _service(session).assess_impact(
            proposal_id, request, governed_change_actor(actor, "change.assess")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ImpactAssessmentResponse.model_validate(
        asdict(value) | {"has_unknown_impact": value.has_unknown_impact}
    )


@router.post(
    "/{proposal_id}/validation-plans",
    response_model=ValidationPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_validation_plan(
    proposal_id: uuid.UUID,
    request: CreateValidationPlan,
    session: SessionDependency,
    actor: ActorDependency,
) -> ValidationPlanResponse:
    try:
        value = await _service(session).create_validation_plan(
            proposal_id, request, governed_change_actor(actor, "change.validate")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ValidationPlanResponse.model_validate(asdict(value))


@router.post(
    "/{proposal_id}/decisions",
    response_model=ChangeDecisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def decide(
    proposal_id: uuid.UUID,
    request: RecordChangeDecision,
    session: SessionDependency,
    actor: ActorDependency,
) -> ChangeDecisionResponse:
    try:
        value = await _service(session).decide(
            proposal_id, request, governed_change_actor(actor, "change.decide")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeDecisionResponse.model_validate(value)


@router.post(
    "/{proposal_id}/observations",
    response_model=ChangeObservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_observation(
    proposal_id: uuid.UUID,
    request: RecordChangeObservation,
    session: SessionDependency,
    actor: ActorDependency,
) -> ChangeObservationResponse:
    try:
        value = await _service(session).record_observation(
            proposal_id, request, governed_change_actor(actor, "change.observe")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeObservationResponse.model_validate(value)


@router.post(
    "/{proposal_id}/outcomes",
    response_model=ChangeOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_outcome(
    proposal_id: uuid.UUID,
    request: RecordChangeOutcome,
    session: SessionDependency,
    actor: ActorDependency,
) -> ChangeOutcomeResponse:
    try:
        value = await _service(session).record_outcome(
            proposal_id, request, governed_change_actor(actor, "change.outcome")
        )
    except (GovernedChangeError, GovernedChangeNotFound) as exc:
        raise _translate(exc) from exc
    return ChangeOutcomeResponse.model_validate(value)


@router.get("/{proposal_id}/timeline", response_model=ChangeTimelineResponse)
async def timeline(
    proposal_id: uuid.UUID, session: SessionDependency, actor: ActorDependency
) -> ChangeTimelineResponse:
    governed_change_actor(actor, "change.read")
    repository = SqlAlchemyGovernedChangeRepository(session)
    records = await repository.timeline(proposal_id)
    if not records:
        raise HTTPException(status_code=404, detail="Change proposal not found")
    return ChangeTimelineResponse(proposal_id=proposal_id, records=records)
