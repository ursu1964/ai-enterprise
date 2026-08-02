from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import Actor, ActorDependency, SessionDependency
from ai_enterprise.api.enterprise_evolution_schemas import (
    ArtifactRequest,
    EvolutionDecisionRequest,
    ImprovementRequest,
    TransitionRequest,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.enterprise_evolution_service import (
    ARTIFACT_TYPES,
    EnterpriseEvolutionError,
    EnterpriseEvolutionService,
)
from ai_enterprise.infrastructure.enterprise_evolution.models import (
    EnterpriseEvolutionArtifactModel,
    EnterpriseImprovementModel,
    EnterpriseImprovementTransitionModel,
)

router = APIRouter(prefix="/enterprise-evolution", tags=["enterprise-evolution"])
ADMINS = {"platform-admin", "platform_administrator"}


def _authority(actor: Actor, organization_id: uuid.UUID, action: str) -> None:
    if actor.role in ADMINS:
        return
    if f"enterprise_evolution.{action}:{organization_id}" not in actor.capabilities:
        raise HTTPException(403, "Organization-scoped evolution authority required")


def _human(actor: Actor) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit human governance decision required")


def _error(exc: EnterpriseEvolutionError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


async def _read_audit(
    session: SessionDependency, actor: Actor, organization_id: uuid.UUID, resource: str
) -> None:
    await AuditWriter(session).append_event(
        stream_id=f"enterprise_evolution:{organization_id}",
        project_id=None,
        event_type="EnterpriseEvolutionRead",
        actor_type=actor.actor_type,
        actor_id=actor.subject,
        payload={"organization_id": str(organization_id), "resource": resource},
    )
    await session.commit()


@router.post("/improvements", status_code=201)
async def propose_improvement(
    request: ImprovementRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "propose")
    try:
        row = await EnterpriseEvolutionService(session).propose(
            **request.model_dump(), proposed_by=actor.subject
        )
    except EnterpriseEvolutionError as exc:
        raise _error(exc) from exc
    return {"improvement_id": str(row.id), "proposal_hash": row.proposal_hash, "state": "proposed"}


@router.get("/improvements")
async def list_improvements(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, object]]:
    _authority(actor, organization_id, "read")
    rows = list(
        (
            await session.scalars(
                select(EnterpriseImprovementModel)
                .where(EnterpriseImprovementModel.organization_id == organization_id)
                .order_by(EnterpriseImprovementModel.proposed_at)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _read_audit(session, actor, organization_id, "improvements")
    return [
        {
            "id": str(row.id),
            "key": row.improvement_key,
            "category": row.category,
            "title": row.title,
            "proposal_hash": row.proposal_hash,
            "evidence_set_hash": row.evidence_set_hash,
        }
        for row in rows
    ]


@router.post("/artifacts", status_code=201)
async def record_artifact(
    request: ArtifactRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "analyze")
    try:
        row = await EnterpriseEvolutionService(session).record_artifact(
            **request.model_dump(), created_by=actor.subject
        )
    except EnterpriseEvolutionError as exc:
        raise _error(exc) from exc
    return {
        "artifact_id": str(row.id),
        "artifact_type": row.artifact_type,
        "artifact_hash": row.artifact_hash,
    }


@router.get("/artifacts")
async def list_artifacts(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    artifact_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, object]]:
    _authority(actor, organization_id, "read")
    query = select(EnterpriseEvolutionArtifactModel).where(
        EnterpriseEvolutionArtifactModel.organization_id == organization_id
    )
    if artifact_type:
        if artifact_type not in ARTIFACT_TYPES:
            raise HTTPException(422, "Unknown evolution artifact type")
        query = query.where(EnterpriseEvolutionArtifactModel.artifact_type == artifact_type)
    rows = list(
        (
            await session.scalars(
                query.order_by(EnterpriseEvolutionArtifactModel.created_at)
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _read_audit(session, actor, organization_id, "artifacts")
    return [
        {
            "id": str(row.id),
            "type": row.artifact_type,
            "key": row.artifact_key,
            "version": row.version,
            "artifact_hash": row.artifact_hash,
            "evidence_set_hash": row.evidence_set_hash,
        }
        for row in rows
    ]


@router.post("/decisions", status_code=201)
async def decide(
    request: EvolutionDecisionRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _human(actor)
    _authority(actor, request.organization_id, "approve")
    try:
        row = await EnterpriseEvolutionService(session).decide(
            **request.model_dump(), decided_by=actor.subject, board_role=actor.role
        )
    except EnterpriseEvolutionError as exc:
        raise _error(exc) from exc
    return {"decision_id": str(row.id), "decision": row.decision, "target_hash": row.target_hash}


@router.post("/improvements/{improvement_id}/transitions", status_code=201)
async def transition(
    improvement_id: uuid.UUID,
    request: TransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    improvement = await session.get(EnterpriseImprovementModel, improvement_id)
    if improvement is None:
        raise HTTPException(404, "Improvement not found")
    _authority(actor, improvement.organization_id, "transition")
    if request.to_state in {"approved", "accepted", "archived"}:
        _human(actor)
    try:
        row = await EnterpriseEvolutionService(session).transition(
            improvement, **request.model_dump(), transitioned_by=actor.subject
        )
    except EnterpriseEvolutionError as exc:
        raise _error(exc) from exc
    return {
        "transition_id": str(row.id),
        "sequence": row.sequence,
        "from_state": row.from_state,
        "to_state": row.to_state,
        "evidence_set_hash": row.evidence_set_hash,
    }


@router.get("/improvements/{improvement_id}/transitions")
async def list_transitions(
    improvement_id: uuid.UUID,
    organization_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, object]]:
    _authority(actor, organization_id, "read")
    improvement = await session.get(EnterpriseImprovementModel, improvement_id)
    if improvement is None or improvement.organization_id != organization_id:
        raise HTTPException(404, "Improvement not found")
    rows = list(
        (
            await session.scalars(
                select(EnterpriseImprovementTransitionModel)
                .where(EnterpriseImprovementTransitionModel.improvement_id == improvement_id)
                .order_by(EnterpriseImprovementTransitionModel.sequence)
                .limit(limit)
            )
        ).all()
    )
    await _read_audit(session, actor, organization_id, "transitions")
    return [
        {
            "sequence": row.sequence,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "evidence_set_hash": row.evidence_set_hash,
            "decision_id": str(row.decision_id) if row.decision_id else None,
        }
        for row in rows
    ]


def _artifact_view(artifact_type: str):
    async def view(
        session: SessionDependency,
        actor: ActorDependency,
        organization_id: uuid.UUID,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> list[dict[str, object]]:
        return await list_artifacts(session, actor, organization_id, artifact_type, limit, 0)

    return view


# Explicit M2-M16 registry views over the immutable typed artifact store.
for _path, _type in {
    "learning": "learning_hypothesis",
    "patterns": "pattern",
    "anti-patterns": "anti_pattern",
    "recommendations": "recommendation",
    "simulations": "simulation",
    "experiments": "experiment",
    "generator-evolution": "generator_evolution",
    "policy-evolution": "policy_evolution",
    "workforce-evolution": "ai_workforce_evolution",
    "capability-evolution": "capability_evolution",
    "maturity": "maturity_assessment",
    "benchmarks": "benchmark",
    "roadmaps": "roadmap",
    "refactoring": "refactoring_plan",
    "self-reflections": "self_reflection",
}.items():
    router.add_api_route(f"/{_path}", _artifact_view(_type), methods=["GET"], name=f"list_{_type}")
