from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.cognitive_schemas import (
    CognitiveDecisionRequest,
    CognitiveLinkRequest,
    CognitiveRecordRequest,
)
from ai_enterprise.api.dependencies import Actor, ActorDependency, SessionDependency
from ai_enterprise.application.cognitive_service import (
    RECORD_TYPES,
    CognitiveError,
    CognitiveService,
)
from ai_enterprise.infrastructure.cognitive.models import CognitiveRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel

router = APIRouter(prefix="/cognitive", tags=["strategic-intelligence"])
ADMINS = {"platform-admin", "platform_administrator"}


def _authority(actor: Actor, organization_id: uuid.UUID, action: str) -> None:
    if (
        actor.role not in ADMINS
        and f"cognitive.{action}:{organization_id}" not in actor.capabilities
    ):
        raise HTTPException(403, "Organization-scoped cognitive authority required")


def _error(exc: CognitiveError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.post("/records", status_code=201)
async def register(
    request: CognitiveRecordRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "write")
    try:
        row = await CognitiveService(session).register(
            **request.model_dump(), created_by=actor.subject
        )
    except CognitiveError as exc:
        raise _error(exc) from exc
    return {
        "record_id": str(row.id),
        "record_type": row.record_type,
        "record_hash": row.record_hash,
    }


@router.post("/records/{record_id}/decision", status_code=201)
async def decide(
    record_id: uuid.UUID,
    request: CognitiveDecisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit human decision required")
    record = await session.get(CognitiveRecordModel, record_id)
    if record is None:
        raise HTTPException(404, "Cognitive record not found")
    _authority(actor, record.organization_id, "decide")
    try:
        row = await CognitiveService(session).decide(
            record, **request.model_dump(), decided_by=actor.subject
        )
    except CognitiveError as exc:
        raise _error(exc) from exc
    return {"decision_id": str(row.id), "decision": row.decision, "record_hash": row.record_hash}


@router.post("/links", status_code=201)
async def link(
    request: CognitiveLinkRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    source = await session.get(CognitiveRecordModel, request.source_record_id)
    target = await session.get(CognitiveRecordModel, request.target_record_id)
    if source is None or target is None:
        raise HTTPException(404, "Cognitive record not found")
    _authority(actor, source.organization_id, "write")
    try:
        row = await CognitiveService(session).link(
            source, target, relationship=request.relationship, actor=actor.subject
        )
    except CognitiveError as exc:
        raise _error(exc) from exc
    return {"link_id": str(row.id), "link_hash": row.link_hash}


@router.get("/records")
async def records(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    record_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, object]]:
    _authority(actor, organization_id, "read")
    query = select(CognitiveRecordModel).where(
        CognitiveRecordModel.organization_id == organization_id
    )
    classified = actor.role in ADMINS or (
        f"cognitive.classified.read:{organization_id}" in actor.capabilities
    )
    if not classified:
        query = query.where(CognitiveRecordModel.classification.in_(("public", "internal")))
    if record_type:
        if record_type not in RECORD_TYPES:
            raise HTTPException(422, "Unknown cognitive record type")
        query = query.where(CognitiveRecordModel.record_type == record_type)
    rows = list(
        (
            await session.scalars(
                query.order_by(CognitiveRecordModel.created_at).limit(limit).offset(offset)
            )
        ).all()
    )
    session.add(
        AuditEventModel(
            project_id=None,
            event_type="CognitiveRegistryRead",
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            payload={"organization_id": str(organization_id), "record_type": record_type},
        )
    )
    await session.commit()
    return [
        {
            "id": str(row.id),
            "type": row.record_type,
            "key": row.record_key,
            "version": row.version,
            "hash": row.record_hash,
            "confidence": row.confidence,
            "classification": row.classification,
        }
        for row in rows
    ]


def _view(record_type: str):
    async def view(
        session: SessionDependency,
        actor: ActorDependency,
        organization_id: uuid.UUID,
        limit: int = Query(default=100, ge=1, le=200),
    ):
        return await records(session, actor, organization_id, record_type, limit, 0)

    return view


for path, kind in {
    "semantics": "semantic_object",
    "ontologies": "ontology",
    "reasoning": "reasoning",
    "questions": "executive_question",
    "scenarios": "scenario",
    "simulations": "simulation",
    "digital-twins": "digital_twin",
    "memory": "cognitive_memory",
    "syntheses": "synthesis",
    "recommendations": "recommendation",
    "objectives": "strategic_objective",
    "dashboard": "dashboard_snapshot",
    "cross-domain": "cross_domain_reasoning",
    "strategic-memory": "strategic_memory",
    "governance": "cognitive_policy",
    "intelligence": "strategic_intelligence",
}.items():
    router.add_api_route(f"/{path}", _view(kind), methods=["GET"], name=f"list_{kind}")
