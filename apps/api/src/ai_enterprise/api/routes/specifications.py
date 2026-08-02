from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from ai_enterprise.api.dependencies import (
    Actor,
    ActorDependency,
    SessionDependency,
    require_capability,
)
from ai_enterprise.api.specification_schemas import (
    DecisionRequest,
    DriftRunRequest,
    EvidenceEdgeRequest,
    EvidenceNodeRequest,
    GenerationRequest,
    SpecificationCreateRequest,
    SpecificationResponse,
    ValidationRequest,
)
from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.specification_platform_service import (
    SpecificationPlatformError,
    SpecificationPlatformService,
)
from ai_enterprise.infrastructure.specification.models import (
    DriftDetectionRunModel,
    DriftFindingModel,
    EngineeringEvidenceEdgeModel,
    EngineeringEvidenceNodeModel,
    EngineeringSpecificationModel,
)

router = APIRouter(prefix="/specifications", tags=["specification-engineering"])


def _error(exc: SpecificationPlatformError) -> HTTPException:
    return HTTPException(exc.status_code, str(exc))


def _authority(actor: Actor, organization_id: uuid.UUID, action: str) -> None:
    try:
        require_capability(actor, f"specification.{action}", f"organization:{organization_id}")
    except HTTPException as exc:
        raise HTTPException(
            403, "Organization-scoped specification authority required"
        ) from exc


def _human(actor: Actor) -> None:
    if actor.actor_type != "human":
        raise HTTPException(403, "Explicit human decision required")


async def _audit_read(
    session: SessionDependency,
    actor: Actor,
    project_id: uuid.UUID,
    resource: str,
    filters: dict[str, str],
) -> None:
    await AuditWriter(session).append_project_event(
        project_id=project_id,
        event_type="SpecificationPlatformRead",
        actor_type=actor.actor_type,
        actor_id=actor.subject,
        payload={"resource": resource, "filters": filters},
    )
    await session.commit()


@router.post("", response_model=SpecificationResponse, status_code=201)
async def create_specification(
    request: SpecificationCreateRequest, session: SessionDependency, actor: ActorDependency
) -> SpecificationResponse:
    _authority(actor, request.organization_id, "write")
    try:
        row = await SpecificationPlatformService(session).create_specification(
            **request.model_dump(), created_by=actor.subject
        )
    except (SpecificationPlatformError, ValueError) as exc:
        if isinstance(exc, SpecificationPlatformError):
            raise _error(exc) from exc
        raise HTTPException(422, str(exc)) from exc
    return SpecificationResponse.model_validate(row)


@router.get("", response_model=list[SpecificationResponse])
async def list_specifications(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
) -> list[SpecificationResponse]:
    _authority(actor, organization_id, "read")
    rows = list(
        (
            await session.scalars(
                select(EngineeringSpecificationModel)
                .where(
                    EngineeringSpecificationModel.organization_id == organization_id,
                    EngineeringSpecificationModel.project_id == project_id,
                )
                .order_by(
                    EngineeringSpecificationModel.specification_key,
                    EngineeringSpecificationModel.version,
                )
                .limit(limit)
                .offset(offset)
            )
        ).all()
    )
    await _audit_read(
        session, actor, project_id, "specifications", {"organization_id": str(organization_id)}
    )
    return [SpecificationResponse.model_validate(row) for row in rows]


@router.post("/{specification_id}/decision")
async def decide_specification(
    specification_id: uuid.UUID,
    request: DecisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    _human(actor)
    specification = await session.get(EngineeringSpecificationModel, specification_id)
    if specification is None:
        raise HTTPException(404, "Specification not found")
    _authority(actor, specification.organization_id, "approve")
    try:
        row = await SpecificationPlatformService(session).approve(
            specification,
            specification_hash=request.bound_hash,
            decision=request.decision,
            decided_by=actor.subject,
            rationale=request.rationale,
        )
    except SpecificationPlatformError as exc:
        raise _error(exc) from exc
    return {"decision_id": str(row.id), "decision": row.decision}


@router.post("/{specification_id}/validations", status_code=201)
async def validate_specification(
    specification_id: uuid.UUID,
    request: ValidationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    specification = await session.get(EngineeringSpecificationModel, specification_id)
    if specification is None:
        raise HTTPException(404, "Specification not found")
    _authority(actor, specification.organization_id, "validate")
    row = await SpecificationPlatformService(session).validate(
        specification, **request.model_dump(), actor=actor.subject
    )
    return {"validation_id": str(row.id), "status": row.status, "evidence_hash": row.evidence_hash}


@router.post("/evidence/nodes", status_code=201)
async def add_evidence_node(
    request: EvidenceNodeRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    _authority(actor, request.organization_id, "evidence")
    row = await SpecificationPlatformService(session).add_evidence_node(
        **request.model_dump(), actor=actor.subject
    )
    return {"node_id": str(row.id), "node_hash": row.node_hash}


@router.post("/evidence/edges", status_code=201)
async def add_evidence_edge(
    request: EvidenceEdgeRequest, session: SessionDependency, actor: ActorDependency
) -> dict[str, str]:
    source = await session.get(EngineeringEvidenceNodeModel, request.source_node_id)
    target = await session.get(EngineeringEvidenceNodeModel, request.target_node_id)
    if source is None or target is None:
        raise HTTPException(404, "Evidence node not found")
    _authority(actor, source.organization_id, "evidence")
    try:
        row = await SpecificationPlatformService(session).add_evidence_edge(
            source,
            target,
            relationship=request.relationship,
            document=request.document,
            actor=actor.subject,
        )
    except SpecificationPlatformError as exc:
        raise _error(exc) from exc
    return {"edge_id": str(row.id), "edge_hash": row.edge_hash}


@router.get("/evidence/graph")
async def evidence_graph(
    session: SessionDependency,
    actor: ActorDependency,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    reference_id: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, object]:
    _authority(actor, organization_id, "read")
    query = select(EngineeringEvidenceNodeModel).where(
        EngineeringEvidenceNodeModel.organization_id == organization_id,
        EngineeringEvidenceNodeModel.project_id == project_id,
    )
    if reference_id:
        query = query.where(EngineeringEvidenceNodeModel.reference_id == reference_id)
    nodes = list((await session.scalars(query.limit(limit))).all())
    node_ids = [row.id for row in nodes]
    edges = list(
        (
            await session.scalars(
                select(EngineeringEvidenceEdgeModel)
                .where(
                    or_(
                        EngineeringEvidenceEdgeModel.source_node_id.in_(node_ids),
                        EngineeringEvidenceEdgeModel.target_node_id.in_(node_ids),
                    )
                )
                .limit(limit)
            )
        ).all()
    )
    await _audit_read(
        session,
        actor,
        project_id,
        "engineering-evidence-graph",
        {
            "organization_id": str(organization_id),
            "reference_id": str(reference_id) if reference_id else "",
        },
    )
    return {
        "nodes": [
            {
                "id": str(row.id),
                "type": row.node_type,
                "reference_id": str(row.reference_id),
                "hash": row.node_hash,
            }
            for row in nodes
        ],
        "edges": [
            {
                "id": str(row.id),
                "source": str(row.source_node_id),
                "target": str(row.target_node_id),
                "relationship": row.relationship,
                "hash": row.edge_hash,
            }
            for row in edges
        ],
    }


@router.post("/{specification_id}/generation-runs", status_code=202)
async def request_generation(
    specification_id: uuid.UUID,
    request: GenerationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    specification = await session.get(EngineeringSpecificationModel, specification_id)
    if specification is None:
        raise HTTPException(404, "Specification not found")
    _authority(actor, specification.organization_id, "generate")
    try:
        row = await SpecificationPlatformService(session).request_generation(
            specification, **request.model_dump(), actor=actor.subject
        )
    except SpecificationPlatformError as exc:
        raise _error(exc) from exc
    return {"generation_run_id": str(row.id), "status": row.status, "input_hash": row.input_hash}


@router.post("/{specification_id}/drift-runs", status_code=201)
async def detect_drift(
    specification_id: uuid.UUID,
    request: DriftRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    specification = await session.get(EngineeringSpecificationModel, specification_id)
    if specification is None:
        raise HTTPException(404, "Specification not found")
    _authority(actor, specification.organization_id, "drift")
    try:
        run, findings = await SpecificationPlatformService(session).detect_drift(
            specification,
            repository_commit_hash=request.repository_commit_hash,
            runtime_deployment_hash=request.runtime_deployment_hash,
            detector_version=request.detector_version,
            observations=[item.model_dump() for item in request.observations],
            actor=actor.subject,
        )
    except SpecificationPlatformError as exc:
        raise _error(exc) from exc
    return {
        "drift_run_id": str(run.id),
        "comparison_hash": run.comparison_hash,
        "promotion_blocked": any(row.promotion_blocking for row in findings),
        "finding_ids": [str(row.id) for row in findings],
    }


@router.post("/drift-findings/{finding_id}/decision")
async def decide_drift(
    finding_id: uuid.UUID,
    request: DecisionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, str]:
    _human(actor)
    finding = await session.get(DriftFindingModel, finding_id)
    if finding is None:
        raise HTTPException(404, "Drift finding not found")
    run = await session.get(DriftDetectionRunModel, finding.drift_run_id)
    if run is None:
        raise HTTPException(409, "Drift run not found")
    _authority(actor, run.organization_id, "approve_drift")
    try:
        row = await SpecificationPlatformService(session).decide_drift(
            finding,
            finding_hash=request.bound_hash,
            decision=request.decision,
            decided_by=actor.subject,
            rationale=request.rationale,
            expires_at=request.expires_at,
        )
    except SpecificationPlatformError as exc:
        raise _error(exc) from exc
    return {"decision_id": str(row.id), "decision": row.decision}


@router.get("/projects/{project_id}/promotion-eligibility")
async def promotion_eligibility(
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    _authority(actor, organization_id, "read")
    eligible, blockers = await SpecificationPlatformService(session).promotion_eligibility(
        organization_id=organization_id, project_id=project_id, now=datetime.now(UTC)
    )
    await _audit_read(
        session,
        actor,
        project_id,
        "promotion-eligibility",
        {"organization_id": str(organization_id)},
    )
    return {"eligible": eligible, "blocking_finding_ids": [str(item) for item in blockers]}
