from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.performance_schemas import (
    CertificationDecisionRequest,
    CertificationResponse,
    EvidenceCollectRequest,
    EvidenceResponse,
    LearningProposalRequest,
    LearningProposalResponse,
    LearningReviewRequest,
    MetricDeriveRequest,
    MetricResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.performance_integration_service import (
    PerformanceGovernanceError,
    PerformanceIntegrationService,
)
from ai_enterprise.infrastructure.performance.models import (
    AssignmentQualityModel,
    CapabilityCertificationModel,
    CapabilityRecommendationModel,
    LearningProposalModel,
    PerformanceEvidenceModel,
    PerformanceMetricModel,
    PerformanceTrendModel,
)

router = APIRouter(prefix="/performance", tags=["performance-governance"])


def _error(exc: PerformanceGovernanceError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


def _require_human(actor: Actor) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit authorized human governance decision required")


def _require_org(actor: Actor, organization_id: uuid.UUID, action: str) -> None:
    try:
        require_capability(actor, f"performance.{action}", f"organization:{organization_id}")
    except HTTPException as exc:
        raise HTTPException(
            403, "Organization-scoped performance authority required"
        ) from exc


async def _audit_read(
    session: SessionDependency,
    actor: Actor,
    resource: str,
    filters: dict[str, Any],
) -> None:
    await AuditWriter(session).append_event(
        stream_id="performance:reads",
        project_id=None,
        event_type="PerformanceDataRead",
        actor_type=actor.actor_type,
        actor_id=actor.subject,
        payload={"resource": resource, "filters": filters},
    )
    await session.commit()


@router.post("/evidence", response_model=EvidenceResponse, status_code=201)
async def collect_evidence(
    request: EvidenceCollectRequest, session: SessionDependency, actor: ActorDependency
) -> EvidenceResponse:
    _require_org(actor, request.organization_id, "write")
    try:
        row = await PerformanceIntegrationService(session).collect_evidence(**request.model_dump())
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return EvidenceResponse.model_validate(row)


@router.get("/evidence", response_model=list[EvidenceResponse])
async def list_evidence(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    workflow_type: str | None = None,
    agent_profile_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[EvidenceResponse]:
    _require_org(actor, organization_id, "read")
    query = select(PerformanceEvidenceModel).where(
        PerformanceEvidenceModel.organization_id == organization_id
    )
    if workflow_type:
        query = query.where(PerformanceEvidenceModel.workflow_type == workflow_type)
    if agent_profile_id:
        query = query.where(PerformanceEvidenceModel.agent_profile_id == agent_profile_id)
    rows = list(
        (
            await session.scalars(
                query.order_by(PerformanceEvidenceModel.observed_at).limit(limit).offset(offset)
            )
        ).all()
    )
    await _audit_read(
        session,
        actor,
        "evidence",
        {"organization_id": str(organization_id), "workflow_type": workflow_type},
    )
    return [EvidenceResponse.model_validate(row) for row in rows]


@router.post("/metrics", response_model=MetricResponse, status_code=201)
async def derive_metric(
    request: MetricDeriveRequest, session: SessionDependency, actor: ActorDependency
) -> MetricResponse:
    _require_org(actor, request.organization_id, "write")
    try:
        row = await PerformanceIntegrationService(session).derive_metric(
            **request.model_dump(), actor_id=actor.subject, now=datetime.now(UTC)
        )
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return MetricResponse.model_validate(row)


@router.get("/metrics", response_model=list[MetricResponse])
async def list_metrics(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    scope_type: str | None = None,
    scope_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[MetricResponse]:
    _require_org(actor, organization_id, "read")
    query = select(PerformanceMetricModel).where(
        PerformanceMetricModel.organization_id == organization_id
    )
    if scope_type:
        query = query.where(PerformanceMetricModel.scope_type == scope_type)
    if scope_id:
        query = query.where(PerformanceMetricModel.scope_id == scope_id)
    rows = list(
        (
            await session.scalars(
                query.order_by(PerformanceMetricModel.calculated_at).limit(limit).offset(offset)
            )
        ).all()
    )
    await _audit_read(session, actor, "metrics", {"organization_id": str(organization_id)})
    return [MetricResponse.model_validate(row) for row in rows]


@router.get("/agents", response_model=list[MetricResponse])
async def agent_metrics(
    session: SessionDependency, actor: ActorDependency, organization_id: uuid.UUID
) -> list[MetricResponse]:
    return await list_metrics(session, actor, organization_id, "agent", None, 100, 0)


@router.get("/crews", response_model=list[MetricResponse])
async def crew_metrics(
    session: SessionDependency, actor: ActorDependency, organization_id: uuid.UUID
) -> list[MetricResponse]:
    return await list_metrics(session, actor, organization_id, "crew", None, 100, 0)


@router.get("/assignments")
async def assignment_quality(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, Any]]:
    _require_org(actor, organization_id, "read")
    rows = list(
        (
            await session.scalars(
                select(AssignmentQualityModel)
                .where(AssignmentQualityModel.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _audit_read(
        session, actor, "assignment-quality", {"organization_id": str(organization_id)}
    )
    return [
        {
            "id": str(row.id),
            "assignment_id": str(row.assignment_id),
            "quality_band": row.quality_band,
            "report_document": row.report_document,
            "evidence_ids": row.evidence_ids,
            "evidence_set_hash": row.evidence_set_hash,
        }
        for row in rows
    ]


@router.get("/trends")
async def list_trends(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    window_days: int = Query(default=90, ge=1, le=3660),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, Any]]:
    _require_org(actor, organization_id, "read")
    rows = list(
        (
            await session.scalars(
                select(PerformanceTrendModel)
                .where(
                    PerformanceTrendModel.organization_id == organization_id,
                    PerformanceTrendModel.window_days == window_days,
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _audit_read(
        session,
        actor,
        "trends",
        {"organization_id": str(organization_id), "window_days": window_days},
    )
    return [
        {
            "id": str(row.id),
            "scope_type": row.scope_type,
            "scope_id": str(row.scope_id),
            "metric_key": row.metric_key,
            "direction": row.trend_direction,
            "trend_document": row.trend_document,
            "trend_hash": row.trend_hash,
        }
        for row in rows
    ]


@router.post(
    "/capabilities/recommendations", response_model=RecommendationResponse, status_code=201
)
async def recommend_capability(
    request: RecommendationRequest, session: SessionDependency, actor: ActorDependency
) -> RecommendationResponse:
    _require_org(actor, request.organization_id, "write")
    try:
        row = await PerformanceIntegrationService(session).create_recommendation(
            **request.model_dump(), actor_id=actor.subject, now=datetime.now(UTC)
        )
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return RecommendationResponse.model_validate(row)


@router.post(
    "/capabilities/recommendations/{recommendation_id}/decision",
    response_model=CertificationResponse | None,
)
async def decide_capability(
    recommendation_id: uuid.UUID,
    request: CertificationDecisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> CertificationResponse | None:
    _require_human(actor)
    recommendation = await session.scalar(
        select(CapabilityRecommendationModel)
        .where(CapabilityRecommendationModel.id == recommendation_id)
        .with_for_update()
    )
    if recommendation is None:
        raise HTTPException(404, "Certification recommendation not found")
    _require_org(actor, recommendation.organization_id, "certify")
    try:
        _, certificate = await PerformanceIntegrationService(session).decide_certification(
            recommendation,
            **request.model_dump(),
            decided_by=actor.subject,
            board_role=actor.role,
            now=datetime.now(UTC),
        )
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return CertificationResponse.model_validate(certificate) if certificate else None


@router.get("/capabilities", response_model=list[CertificationResponse])
@router.get("/certifications", response_model=list[CertificationResponse])
async def list_certifications(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    agent_profile_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[CertificationResponse]:
    _require_org(actor, organization_id, "read")
    query = select(CapabilityCertificationModel).where(
        CapabilityCertificationModel.organization_id == organization_id
    )
    if agent_profile_id:
        query = query.where(CapabilityCertificationModel.agent_profile_id == agent_profile_id)
    rows = list(
        (
            await session.scalars(
                query.order_by(CapabilityCertificationModel.granted_at).limit(limit).offset(offset)
            )
        ).all()
    )
    await _audit_read(session, actor, "certifications", {"organization_id": str(organization_id)})
    return [CertificationResponse.model_validate(row) for row in rows]


@router.post("/learning-proposals", response_model=LearningProposalResponse, status_code=201)
async def create_learning_proposal(
    request: LearningProposalRequest, session: SessionDependency, actor: ActorDependency
) -> LearningProposalResponse:
    _require_org(actor, request.organization_id, "write")
    try:
        row = await PerformanceIntegrationService(session).create_learning_proposal(
            **request.model_dump(), proposed_by=actor.subject, now=datetime.now(UTC)
        )
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return LearningProposalResponse.model_validate(row)


@router.post("/learning-proposals/{proposal_id}/review", response_model=LearningProposalResponse)
async def review_learning_proposal(
    proposal_id: uuid.UUID,
    request: LearningReviewRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> LearningProposalResponse:
    _require_human(actor)
    proposal = await session.scalar(
        select(LearningProposalModel)
        .where(LearningProposalModel.id == proposal_id)
        .with_for_update()
    )
    if proposal is None:
        raise HTTPException(404, "Learning proposal not found")
    _require_org(actor, proposal.organization_id, "govern")
    try:
        row = await PerformanceIntegrationService(session).review_learning_proposal(
            proposal,
            **request.model_dump(),
            reviewer=actor.subject,
            now=datetime.now(UTC),
        )
    except PerformanceGovernanceError as exc:
        raise _error(exc) from exc
    return LearningProposalResponse.model_validate(row)


@router.get("/learning-proposals", response_model=list[LearningProposalResponse])
async def list_learning_proposals(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[LearningProposalResponse]:
    _require_org(actor, organization_id, "read")
    rows = list(
        (
            await session.scalars(
                select(LearningProposalModel)
                .where(LearningProposalModel.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _audit_read(
        session, actor, "learning-proposals", {"organization_id": str(organization_id)}
    )
    return [LearningProposalResponse.model_validate(row) for row in rows]


@router.get("/reports")
async def reports(
    session: SessionDependency, actor: ActorDependency, organization_id: uuid.UUID
) -> dict[str, int | str]:
    _require_org(actor, organization_id, "read")
    evidence = list(
        (
            await session.scalars(
                select(PerformanceEvidenceModel.id).where(
                    PerformanceEvidenceModel.organization_id == organization_id
                )
            )
        ).all()
    )
    metrics = list(
        (
            await session.scalars(
                select(PerformanceMetricModel.id).where(
                    PerformanceMetricModel.organization_id == organization_id
                )
            )
        ).all()
    )
    await _audit_read(session, actor, "reports", {"organization_id": str(organization_id)})
    return {
        "organization_id": str(organization_id),
        "evidence_count": len(evidence),
        "metric_count": len(metrics),
    }
