import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.knowledge_schemas import (
    CandidateResponse,
    ExtractKnowledgeRequest,
    ItemResponse,
    ResolveContradictionRequest,
    RetrieveKnowledgeRequest,
    ReviewCandidateRequest,
    SourceResponse,
    SupersedeRequest,
    WithdrawRequest,
)
from ai_enterprise.application.knowledge_service import KnowledgeError, KnowledgeService
from ai_enterprise.application.organization_persistence_service import canonical_hash
from ai_enterprise.infrastructure.database.models import AuditEventModel
from ai_enterprise.infrastructure.knowledge.models import (
    KnowledgeCandidateModel,
    KnowledgeContradictionModel,
    KnowledgeIndexVersionModel,
    KnowledgeItemModel,
    KnowledgeRetrievalManifestModel,
    KnowledgeRetrievalResultModel,
    KnowledgeRetrievalSessionModel,
    KnowledgeSourceModel,
    KnowledgeSupersessionModel,
)
from ai_enterprise.infrastructure.organization.models import AgentAssignmentModel

router = APIRouter(tags=["organizational-knowledge"])


def _error(exc: KnowledgeError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


@router.get("/knowledge-sources/{source_id}", response_model=SourceResponse)
async def get_source(source_id: uuid.UUID, session: SessionDependency) -> SourceResponse:
    row = await session.get(KnowledgeSourceModel, source_id)
    if row is None:
        raise HTTPException(404, "Knowledge source not found")
    return SourceResponse.model_validate(row)


@router.get("/projects/{project_id}/knowledge-sources", response_model=list[SourceResponse])
async def list_project_sources(
    project_id: uuid.UUID, session: SessionDependency
) -> list[SourceResponse]:
    rows = (
        await session.scalars(
            select(KnowledgeSourceModel)
            .where(KnowledgeSourceModel.project_id == project_id)
            .order_by(KnowledgeSourceModel.registered_at)
        )
    ).all()
    return [SourceResponse.model_validate(row) for row in rows]


@router.post(
    "/knowledge-candidates/extractions", response_model=list[CandidateResponse], status_code=201
)
async def extract_candidates(
    request: ExtractKnowledgeRequest, session: SessionDependency
) -> list[CandidateResponse]:
    source = await session.get(KnowledgeSourceModel, request.source_id)
    if source is None:
        raise HTTPException(404, "KNOW-001 SOURCE_NOT_FOUND")
    try:
        rows = await KnowledgeService(session).extract(
            source,
            request.source_hash,
            request.runtime_session_id,
            request.extraction_skill_version_id,
            [candidate.model_dump() for candidate in request.candidates],
        )
    except KnowledgeError as exc:
        raise _error(exc) from exc
    return [CandidateResponse.model_validate(row) for row in rows]


@router.get("/knowledge-candidates/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: uuid.UUID, session: SessionDependency) -> CandidateResponse:
    row = await session.get(KnowledgeCandidateModel, candidate_id)
    if row is None:
        raise HTTPException(404, "Knowledge candidate not found")
    return CandidateResponse.model_validate(row)


@router.post("/knowledge-candidates/{candidate_id}/reviews")
async def review_candidate(
    candidate_id: uuid.UUID,
    request: ReviewCandidateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str | None]:
    if actor.actor_type == "agent" and actor.subject == str(request.reviewer_id):
        raise HTTPException(403, "Agent cannot self-promote knowledge")
    candidate = await session.get(KnowledgeCandidateModel, candidate_id)
    if candidate is None:
        raise HTTPException(404, "Knowledge candidate not found")
    try:
        item = await KnowledgeService(session).review_and_promote(candidate, request.model_dump())
    except KnowledgeError as exc:
        raise _error(exc) from exc
    return {
        "candidate_id": str(candidate.id),
        "status": candidate.status,
        "knowledge_item_id": str(item.id) if item else None,
    }


@router.get("/knowledge-items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: uuid.UUID, session: SessionDependency) -> ItemResponse:
    row = await session.get(KnowledgeItemModel, item_id)
    if row is None:
        raise HTTPException(404, "Knowledge item not found")
    return ItemResponse.model_validate(row)


@router.get("/knowledge-items", response_model=list[ItemResponse])
async def list_items(
    session: SessionDependency, scope_type: str | None = None, scope_id: uuid.UUID | None = None
) -> list[ItemResponse]:
    query = select(KnowledgeItemModel)
    if scope_type:
        query = query.where(KnowledgeItemModel.scope_type == scope_type)
    if scope_id:
        query = query.where(KnowledgeItemModel.scope_id == scope_id)
    rows = (
        await session.scalars(
            query.order_by(KnowledgeItemModel.knowledge_key, KnowledgeItemModel.version_number)
        )
    ).all()
    return [ItemResponse.model_validate(row) for row in rows]


@router.post("/knowledge-items/{item_id}/supersede", response_model=ItemResponse)
async def supersede_item(
    item_id: uuid.UUID, request: SupersedeRequest, session: SessionDependency
) -> ItemResponse:
    old, new = (
        await session.get(KnowledgeItemModel, item_id),
        await session.get(KnowledgeItemModel, request.superseding_item_id),
    )
    if old is None or new is None or old.id == new.id:
        raise HTTPException(409, "Valid distinct knowledge items required")
    old.temporal_status = "superseded"
    session.add(
        KnowledgeSupersessionModel(
            superseded_item_id=old.id, superseding_item_id=new.id, reason=request.reason
        )
    )
    await session.commit()
    return ItemResponse.model_validate(old)


@router.post("/knowledge-items/{item_id}/withdraw", response_model=ItemResponse)
async def withdraw_item(
    item_id: uuid.UUID, request: WithdrawRequest, session: SessionDependency, actor: ActorDependency
) -> ItemResponse:
    if actor.role not in {"knowledge-curator", "platform-admin", "platform_administrator"}:
        raise HTTPException(403, "Knowledge curator role required")
    row = await session.get(KnowledgeItemModel, item_id)
    if row is None:
        raise HTTPException(404, "Knowledge item not found")
    row.temporal_status, row.valid_until = "withdrawn", datetime.now(UTC)
    session.add(
        AuditEventModel(
            project_id=row.scope_id if row.scope_type == "project" else None,
            event_type="KnowledgeItemWithdrawn",
            actor_type=actor.actor_type,
            actor_id=actor.subject,
            payload={"knowledge_item_id": str(row.id), "reason": request.reason},
        )
    )
    await session.commit()
    return ItemResponse.model_validate(row)


@router.get("/knowledge-contradictions")
async def list_contradictions(
    session: SessionDependency, status: str | None = Query(default=None)
) -> list[dict]:
    query = select(KnowledgeContradictionModel)
    if status:
        query = query.where(KnowledgeContradictionModel.status == status)
    rows = (await session.scalars(query.order_by(KnowledgeContradictionModel.detected_at))).all()
    return [
        {column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows
    ]


@router.post("/knowledge-contradictions/{contradiction_id}/resolve")
async def resolve_contradiction(
    contradiction_id: uuid.UUID, request: ResolveContradictionRequest, session: SessionDependency
) -> dict[str, str]:
    row = await session.get(KnowledgeContradictionModel, contradiction_id)
    if row is None:
        raise HTTPException(404, "Knowledge contradiction not found")
    row.status, row.resolved_at = "resolved", datetime.now(UTC)
    row.resolution_document = request.model_dump()
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@router.post("/knowledge/retrieve")
async def retrieve(
    request: RetrieveKnowledgeRequest, session: SessionDependency
) -> dict[str, object]:
    assignment = await session.get(AgentAssignmentModel, request.assignment_id)
    if (
        assignment is None
        or assignment.status != "active"
        or assignment.agent_profile_id != request.actor_id
    ):
        raise HTTPException(403, "Active matching assignment required")
    allowed_scope = [KnowledgeItemModel.scope_type == "organization"]
    if (
        request.project_id
        and assignment.scope_type == "project"
        and assignment.scope_id == request.project_id
    ):
        allowed_scope.append(
            (KnowledgeItemModel.scope_type == "project")
            & (KnowledgeItemModel.scope_id == request.project_id)
        )
    temporal = ["current"] + (["stale"] if request.include_stale else [])
    if request.include_disputed:
        temporal.append("disputed")
    query = select(KnowledgeItemModel).where(
        or_(*allowed_scope),
        KnowledgeItemModel.temporal_status.in_(temporal),
        KnowledgeItemModel.classification.in_(
            [
                key
                for key, rank in {
                    "public": 0,
                    "internal": 1,
                    "confidential": 2,
                    "restricted": 3,
                }.items()
                if rank
                <= {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}[
                    request.maximum_classification
                ]
            ]
        ),
    )
    if request.requested_item_types:
        query = query.where(KnowledgeItemModel.item_type.in_(request.requested_item_types))
    # Relational authorization filters execute before deterministic lexical ranking.
    authorized = list((await session.scalars(query)).all())
    terms = set(request.query_text.lower().split())
    ranked = sorted(
        authorized,
        key=lambda item: (
            -len(terms & set(f"{item.title} {item.statement}".lower().split())),
            item.knowledge_key,
            -item.version_number,
        ),
    )[: request.maximum_results]
    index = await session.scalar(
        select(KnowledgeIndexVersionModel)
        .where(
            KnowledgeIndexVersionModel.organization_id == request.organization_id,
            KnowledgeIndexVersionModel.status == "active",
        )
        .order_by(KnowledgeIndexVersionModel.created_at.desc())
    )
    if index is None:
        raise HTTPException(409, "Active knowledge index required")
    request_document = request.model_dump(mode="json")
    retrieval = KnowledgeRetrievalSessionModel(
        id=uuid.uuid4(),
        runtime_session_id=request.runtime_session_id,
        actor_id=request.actor_id,
        assignment_id=request.assignment_id,
        request_document=request_document,
        request_hash=canonical_hash(request_document),
        policy_version="knowledge-retrieval-v1",
        index_version_id=index.id,
    )
    session.add(retrieval)
    results: list[dict[str, object]] = []
    for rank, item in enumerate(ranked, 1):
        document = {
            "item_id": str(item.id),
            "rank": rank,
            "knowledge_hash": item.knowledge_hash,
            "evidence_manifest_hash": item.evidence_manifest_hash,
            "temporal_status": item.temporal_status,
            "classification": item.classification,
        }
        session.add(
            KnowledgeRetrievalResultModel(
                retrieval_session_id=retrieval.id,
                knowledge_item_id=item.id,
                rank=rank,
                lexical_score=str(
                    len(terms & set(f"{item.title} {item.statement}".lower().split()))
                ),
                result_document=document,
                provenance_hash=canonical_hash(document),
            )
        )
        results.append(document)
    manifest_document = {
        "retrieval_session_id": str(retrieval.id),
        "index_version_id": str(index.id),
        "results": results,
    }
    manifest = KnowledgeRetrievalManifestModel(
        id=uuid.uuid4(),
        retrieval_session_id=retrieval.id,
        manifest_document=manifest_document,
        manifest_hash=canonical_hash(manifest_document),
    )
    session.add(manifest)
    await session.commit()
    return {
        "retrieval_session_id": str(retrieval.id),
        "index_version": index.index_hash,
        "manifest_hash": manifest.manifest_hash,
        "results": results,
    }
