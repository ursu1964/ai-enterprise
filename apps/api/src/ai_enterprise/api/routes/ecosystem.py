from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ai_enterprise.api.dependencies import Actor, ActorDependency, SessionDependency
from ai_enterprise.api.ecosystem_schemas import (
    ApprovalRequest,
    AssetRequest,
    EdgeRequest,
    EntityRequest,
    InvocationRequest,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.ecosystem_service import (
    ASSET_TYPES,
    EcosystemError,
    EcosystemService,
)
from ai_enterprise.infrastructure.ecosystem.models import (
    EcosystemAssetModel,
    EcosystemEdgeModel,
    EcosystemEntityModel,
)

router = APIRouter(prefix="/ecosystem", tags=["governed-ecosystem"])
ADMINS = {"platform-admin", "platform_administrator"}


def _authority(actor: Actor, organization_id: uuid.UUID, action: str) -> None:
    if (
        actor.role not in ADMINS
        and f"ecosystem.{action}:{organization_id}" not in actor.capabilities
    ):
        raise HTTPException(403, "Organization-scoped ecosystem authority required")


def _human(actor: Actor) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit human approval required")


def _error(exc: EcosystemError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


async def _audit_read(
    session: SessionDependency, actor: Actor, organization_id: uuid.UUID, resource: str
) -> None:
    await AuditWriter(session).append_event(
        stream_id=f"ecosystem:{organization_id}",
        project_id=None,
        event_type="EcosystemRegistryRead",
        actor_type=actor.actor_type,
        actor_id=actor.subject,
        payload={"organization_id": str(organization_id), "resource": resource},
    )
    await session.commit()


@router.post("/entities", status_code=201)
async def register_entity(
    request: EntityRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "write")
    try:
        row = await EcosystemService(session).register_entity(
            **request.model_dump(), created_by=actor.subject
        )
    except EcosystemError as exc:
        raise _error(exc) from exc
    return {"entity_id": str(row.id), "entity_hash": row.entity_hash}


@router.post("/assets", status_code=201)
async def register_asset(
    request: AssetRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "write")
    try:
        row = await EcosystemService(session).register_asset(
            **request.model_dump(), created_by=actor.subject
        )
    except EcosystemError as exc:
        raise _error(exc) from exc
    return {"asset_id": str(row.id), "asset_type": row.asset_type, "asset_hash": row.asset_hash}


@router.post("/assets/{asset_id}/decision", status_code=201)
async def approve(
    asset_id: uuid.UUID,
    request: ApprovalRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    _human(actor)
    asset = await session.get(EcosystemAssetModel, asset_id)
    if asset is None:
        raise HTTPException(404, "Ecosystem asset not found")
    _authority(actor, asset.organization_id, "approve")
    try:
        row = await EcosystemService(session).approve(
            asset, **request.model_dump(), decided_by=actor.subject, board_role=actor.role
        )
    except EcosystemError as exc:
        raise _error(exc) from exc
    return {"approval_id": str(row.id), "decision": row.decision, "asset_hash": row.asset_hash}


@router.post("/gateway/invocations", status_code=201)
async def invoke(
    request: InvocationRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "invoke")
    try:
        row = await EcosystemService(session).record_invocation(
            **request.model_dump(), actor=actor.subject
        )
    except EcosystemError as exc:
        raise _error(exc) from exc
    return {
        "invocation_id": str(row.id),
        "invocation_hash": row.invocation_hash,
        "status": row.status,
    }


@router.post("/graph/edges", status_code=201)
async def add_edge(
    request: EdgeRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    source = await session.get(EcosystemEntityModel, request.source_entity_id)
    target = await session.get(EcosystemEntityModel, request.target_entity_id)
    if source is None or target is None:
        raise HTTPException(404, "Ecosystem entity not found")
    _authority(actor, source.organization_id, "write")
    try:
        row = await EcosystemService(session).add_edge(
            source,
            target,
            relationship=request.relationship,
            document=request.document,
            actor=actor.subject,
        )
    except EcosystemError as exc:
        raise _error(exc) from exc
    return {"edge_id": str(row.id), "edge_hash": row.edge_hash}


@router.get("/assets")
async def list_assets(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    asset_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[dict[str, str]]:
    _authority(actor, organization_id, "read")
    query = select(EcosystemAssetModel).where(
        EcosystemAssetModel.organization_id == organization_id
    )
    if asset_type:
        if asset_type not in ASSET_TYPES:
            raise HTTPException(422, "Unknown ecosystem asset type")
        query = query.where(EcosystemAssetModel.asset_type == asset_type)
    rows = list(
        (
            await session.scalars(
                query.order_by(EcosystemAssetModel.created_at).limit(limit).offset(offset)
            )
        ).all()
    )
    await _audit_read(session, actor, organization_id, "assets")
    return [
        {
            "id": str(row.id),
            "type": row.asset_type,
            "key": row.asset_key,
            "version": row.version,
            "hash": row.asset_hash,
        }
        for row in rows
    ]


def _view(asset_type: str):
    async def view(
        session: SessionDependency,
        actor: ActorDependency,
        organization_id: uuid.UUID,
        limit: int = Query(default=100, ge=1, le=200),
    ) -> list[dict[str, str]]:
        return await list_assets(session, actor, organization_id, asset_type, limit, 0)

    return view


for path, kind in {
    "connectors": "connector",
    "contracts": "external_contract",
    "federations": "federation_agreement",
    "trust": "trust_assessment",
    "identities": "identity_mapping",
    "capabilities": "capability_offer",
    "supply-chain": "dependency",
    "vendor-risks": "vendor_risk",
    "data-exchanges": "data_exchange",
    "regulations": "regulatory_policy",
    "cloud-bindings": "cloud_binding",
    "event-bindings": "event_binding",
    "federation-protocols": "federation_protocol",
}.items():
    router.add_api_route(f"/{path}", _view(kind), methods=["GET"], name=f"list_{kind}")


@router.get("/graph")
async def graph(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    _authority(actor, organization_id, "read")
    entities = list(
        (
            await session.scalars(
                select(EcosystemEntityModel)
                .where(EcosystemEntityModel.organization_id == organization_id)
                .limit(limit)
            )
        ).all()
    )
    ids = [row.id for row in entities]
    edges = list(
        (
            await session.scalars(
                select(EcosystemEdgeModel)
                .where(
                    EcosystemEdgeModel.organization_id == organization_id,
                    EcosystemEdgeModel.source_entity_id.in_(ids),
                    EcosystemEdgeModel.target_entity_id.in_(ids),
                )
                .limit(limit)
            )
        ).all()
    )
    await _audit_read(session, actor, organization_id, "graph")
    return {
        "entities": [
            {
                "id": str(row.id),
                "type": row.entity_type,
                "name": row.display_name,
                "hash": row.entity_hash,
            }
            for row in entities
        ],
        "edges": [
            {
                "source": str(row.source_entity_id),
                "target": str(row.target_entity_id),
                "relationship": row.relationship,
                "hash": row.edge_hash,
            }
            for row in edges
        ],
    }
