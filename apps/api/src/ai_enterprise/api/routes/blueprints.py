from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ai_enterprise.api.blueprint_schemas import (
    BlueprintCreateRequest,
    BlueprintDecisionResponse,
    BlueprintResponse,
    BlueprintTransitionRequest,
)
from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.domain.blueprints import (
    BlueprintLifecycleError,
    require_blueprint_transition,
    require_reuse_evidence,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    BlueprintAssetModel,
    BlueprintDecisionModel,
    ProjectModel,
)

router = APIRouter(prefix="/blueprints", tags=["blueprint-lifecycle"])


def _require_human(actor: Actor, capability: str, organization_id: uuid.UUID) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit human blueprint governance is required")
    require_capability(actor, capability, f"organization:{organization_id}")


def _require_source_project(actor: Actor, project_id: uuid.UUID) -> None:
    require_capability(actor, "project.read", f"project:{project_id}")


@router.post("", response_model=BlueprintResponse, status_code=201)
async def propose_blueprint(
    request: BlueprintCreateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> BlueprintResponse:
    _require_human(actor, "blueprint.write", request.organization_id)
    _require_source_project(actor, request.source_project_id)
    if await session.get(ProjectModel, request.source_project_id) is None:
        raise HTTPException(404, "Source project not found")
    if request.source_artifact_id is not None:
        artifact = await session.get(ArtifactModel, request.source_artifact_id)
        if artifact is None or artifact.project_id != request.source_project_id:
            raise HTTPException(400, "Source artifact must belong to the source project")
    if request.supersedes_id is not None:
        superseded = await session.get(BlueprintAssetModel, request.supersedes_id)
        if superseded is None:
            raise HTTPException(404, "Superseded blueprint not found")
        if superseded.organization_id != request.organization_id:
            raise HTTPException(404, "Superseded blueprint not found")
        if superseded.blueprint_key != request.blueprint_key:
            raise HTTPException(409, "A blueprint can only supersede the same blueprint key")
        if request.version <= superseded.version:
            raise HTTPException(409, "A superseding blueprint version must increase monotonically")
    row = BlueprintAssetModel(
        id=uuid.uuid4(),
        lifecycle="proposed",
        created_by=actor.subject,
        reuse_count=0,
        **request.model_dump(),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Blueprint key and version already exist") from exc
    await session.refresh(row)
    return BlueprintResponse.model_validate(row)


@router.get("", response_model=list[BlueprintResponse])
async def list_blueprints(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID | None = None,
    lifecycle: str | None = None,
    source_project_id: uuid.UUID | None = None,
    include_deprecated: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[BlueprintResponse]:
    if organization_id is None:
        if actor.actor_type != "human":
            raise HTTPException(403, "Explicit human blueprint governance is required")
        require_capability(actor, "blueprint.read", "global")
    else:
        _require_human(actor, "blueprint.read", organization_id)
    query = select(BlueprintAssetModel)
    if organization_id is not None:
        query = query.where(BlueprintAssetModel.organization_id == organization_id)
    if lifecycle:
        query = query.where(BlueprintAssetModel.lifecycle == lifecycle)
    elif not include_deprecated:
        query = query.where(BlueprintAssetModel.lifecycle != "deprecated")
    if source_project_id:
        query = query.where(BlueprintAssetModel.source_project_id == source_project_id)
    rows = (
        await session.scalars(query.order_by(BlueprintAssetModel.updated_at.desc()).limit(limit))
    ).all()
    return [BlueprintResponse.model_validate(row) for row in rows]


@router.post("/{blueprint_id}/transitions", response_model=BlueprintDecisionResponse)
async def transition_blueprint(
    blueprint_id: uuid.UUID,
    request: BlueprintTransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> BlueprintDecisionResponse:
    row = await session.get(BlueprintAssetModel, blueprint_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Blueprint not found")
    _require_human(actor, "blueprint.review", row.organization_id)
    try:
        require_blueprint_transition(row.lifecycle, request.lifecycle)
    except BlueprintLifecycleError as exc:
        raise HTTPException(409, str(exc)) from exc
    if request.lifecycle == "reusable":
        try:
            require_reuse_evidence(request.evidence)
        except BlueprintLifecycleError as exc:
            raise HTTPException(400, str(exc)) from exc
    previous = row.lifecycle
    row.lifecycle = request.lifecycle
    decision = BlueprintDecisionModel(
        id=uuid.uuid4(),
        blueprint_id=row.id,
        previous_lifecycle=previous,
        lifecycle=request.lifecycle,
        reviewer=actor.subject,
        rationale=request.rationale,
        evidence=request.evidence,
    )
    session.add(decision)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Blueprint changed concurrently; reload and retry") from exc
    await session.refresh(decision)
    return BlueprintDecisionResponse.model_validate(decision)


@router.get("/{blueprint_id}/history", response_model=list[BlueprintDecisionResponse])
async def blueprint_history(
    blueprint_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[BlueprintDecisionResponse]:
    blueprint = await session.get(BlueprintAssetModel, blueprint_id)
    if blueprint is None:
        raise HTTPException(404, "Blueprint not found")
    _require_human(actor, "blueprint.read", blueprint.organization_id)
    rows = (
        await session.scalars(
            select(BlueprintDecisionModel)
            .where(BlueprintDecisionModel.blueprint_id == blueprint_id)
            .order_by(BlueprintDecisionModel.created_at)
        )
    ).all()
    return [BlueprintDecisionResponse.model_validate(row) for row in rows]
