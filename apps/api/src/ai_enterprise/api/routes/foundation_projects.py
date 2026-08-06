from __future__ import annotations

import copy
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.foundation_project_schemas import (
    FoundationFindingResolutionRequest,
    FoundationImportResponse,
    FoundationManifestImportRequest,
    FoundationObjectUpdateRequest,
    FoundationProjectStateResponse,
    FoundationSnapshotRequest,
    FoundationSnapshotResponse,
)
from ai_enterprise.api.project_formation_schemas import ClientBlueprintImportRequest
from ai_enterprise.application.project_formation_service import (
    ProjectFormationError,
    ProjectFormationService,
)
from ai_enterprise.domain.aeir import AeirProjectModel, compile_project_snapshot
from ai_enterprise.domain.aepm_validation import AepmValidationEngine
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.aeir_repository import build_aeir_snapshot_write_set
from ai_enterprise.infrastructure.knowledge.models import (
    AeirChangeEventModel,
    AeirDecisionModel,
    AeirModelVersionModel,
    AeirObjectModel,
    AeirObjectVersionModel,
    AeirProjectSnapshotModel,
    AeirRelationshipModel,
    AeirValidationFindingModel,
)

router = APIRouter(prefix="/projects", tags=["r3-foundation-projects"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human project authority is required")


@router.post("/import", response_model=FoundationImportResponse)
async def import_foundation_project(
    request: FoundationManifestImportRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FoundationImportResponse:
    _require_human(actor)
    try:
        response = await ProjectFormationService(session).import_client_blueprint_manifest(
            ClientBlueprintImportRequest(
                manifest=request.manifest,
                manifest_text=request.manifest_text,
                content_type=request.content_type,
            ),
            actor_id=actor.subject,
        )
    except ProjectFormationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return FoundationImportResponse(
        project_id=response.project_id,
        status=response.status,
        review_state=response.review_state,
        validation_report=response.validation_report,
        canonical_model_sha256=response.canonical_model["model_sha256"],
        canonical_object_count=response.canonical_object_count,
        relationship_count=response.relationship_count,
        snapshot_id=response.proof["project_snapshot_id"],
        snapshot_status=response.proof["project_snapshot_status"],
        source_manifest_sha256=response.source_manifest_sha256,
        traceability=response.traceability,
    )


@router.get("/{project_id}/foundation", response_model=FoundationProjectStateResponse)
async def get_foundation_project(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> FoundationProjectStateResponse:
    _require_human(actor)
    project = await _project(session, project_id)
    latest_model = await _latest_model_version(session, project_id)
    latest_snapshot = await _latest_snapshot(session, project_id)
    return FoundationProjectStateResponse(
        project_id=project_id,
        project_name=project.name,
        status=project.status,
        latest_model_sha256=None if latest_model is None else latest_model.model_sha256,
        latest_snapshot_id=None if latest_snapshot is None else latest_snapshot.snapshot_id,
        latest_snapshot_status=None if latest_snapshot is None else latest_snapshot.status,
    )


@router.get("/{project_id}/objects")
async def list_foundation_objects(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
    type: str | None = None,
    lifecycle_status: str | None = None,
    truth_status: str | None = None,
    approval_status: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    _require_human(actor)
    model_version = await _required_latest_model_version(session, project_id)
    statement = select(AeirObjectModel).where(
        AeirObjectModel.model_version_id == model_version.id
    )
    if type is not None:
        statement = statement.where(AeirObjectModel.object_type == type)
    if lifecycle_status is not None:
        statement = statement.where(AeirObjectModel.lifecycle_status == lifecycle_status)
    if truth_status is not None:
        statement = statement.where(AeirObjectModel.truth_status == truth_status)
    if approval_status is not None:
        statement = statement.where(AeirObjectModel.approval_status == approval_status)
    rows = (await session.scalars(statement.order_by(AeirObjectModel.object_id))).all()
    if source is not None:
        rows = [row for row in rows if source in row.source_refs]
    return [_object_payload(row) for row in rows]


@router.get("/{project_id}/objects/{object_id}")
async def get_foundation_object(
    project_id: uuid.UUID,
    object_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    model_version = await _required_latest_model_version(session, project_id)
    row = await session.scalar(
        select(AeirObjectModel).where(
            AeirObjectModel.model_version_id == model_version.id,
            AeirObjectModel.object_id == object_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    return _object_payload(row)


@router.put("/{project_id}/objects/{object_id}")
async def update_foundation_object(
    project_id: uuid.UUID,
    object_id: str,
    request: FoundationObjectUpdateRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    model_version = await _required_latest_model_version(session, project_id)
    row = await session.scalar(
        select(AeirObjectModel).where(
            AeirObjectModel.model_version_id == model_version.id,
            AeirObjectModel.object_id == object_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Object not found")
    document = _object_payload(row)
    for field in ("name", "description", "lifecycle_status", "truth_status", "approval_status"):
        value = getattr(request, field)
        if value is not None:
            document[field] = value
    if request.attributes is not None:
        document["attributes"] = request.attributes
    version_number = await _next_object_version(session, row.id)
    version_row = AeirObjectVersionModel(
        id=uuid.uuid4(),
        object_row_id=row.id,
        model_version_id=model_version.id,
        object_id=row.object_id,
        version_number=version_number,
        version_document={
            "schema_version": "aeir-object-version-0.1",
            "object_id": row.object_id,
            "model_version_id": str(model_version.id),
            "object": document,
            "reason": request.reason,
        },
        object_version_hash=hash_json(
            {
                "project_id": str(project_id),
                "model_version_id": str(model_version.id),
                "object_id": row.object_id,
                "version_number": version_number,
                "object": document,
            }
        ),
        created_by=actor.subject,
    )
    event = await _event(
        session,
        project_id=project_id,
        model_version_id=model_version.id,
        actor_id=actor.subject,
        event_type="object.version.created",
        payload={
            "object_id": object_id,
            "version_number": version_number,
            "reason": request.reason,
        },
    )
    session.add(version_row)
    session.add(event)
    await session.commit()
    return version_row.version_document


@router.get("/{project_id}/relationships")
async def list_foundation_relationships(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[dict[str, Any]]:
    _require_human(actor)
    model_version = await _required_latest_model_version(session, project_id)
    rows = (
        await session.scalars(
            select(AeirRelationshipModel)
            .where(AeirRelationshipModel.model_version_id == model_version.id)
            .order_by(AeirRelationshipModel.relationship_id)
        )
    ).all()
    return [row.relationship_document for row in rows]


@router.post("/{project_id}/validation-runs")
async def run_foundation_validation(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    project = await _project(session, project_id)
    report = AepmValidationEngine().validate(project.manifest or {})
    model_version = await _latest_model_version(session, project_id)
    snapshot = await _latest_snapshot(session, project_id)
    event = await _event(
        session,
        project_id=project_id,
        model_version_id=None if model_version is None else model_version.id,
        actor_id=actor.subject,
        event_type="validation.completed",
        payload=report.model_dump(mode="json"),
    )
    finding_rows = [
        AeirValidationFindingModel(
            id=uuid.uuid4(),
            project_id=project_id,
            snapshot_row_id=None if snapshot is None else snapshot.id,
            model_version_id=None if model_version is None else model_version.id,
            rule_row_id=None,
            finding_id=finding.id,
            rule_id=finding.rule_id,
            severity=finding.severity,
            category=finding.category,
            blocking=finding.blocking,
            object_refs=list(finding.object_refs),
            finding_document=finding.model_dump(mode="json"),
            finding_hash=hash_json(
                {
                    "project_id": str(project_id),
                    "event_hash": event.event_hash,
                    "finding": finding.model_dump(mode="json"),
                }
            ),
        )
        for finding in report.findings
    ]
    session.add_all(finding_rows)
    session.add(event)
    await session.commit()
    return report.model_dump(mode="json")


@router.get("/{project_id}/validation-findings")
async def list_foundation_validation_findings(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[dict[str, Any]]:
    _require_human(actor)
    rows = (
        await session.scalars(
            select(AeirValidationFindingModel)
            .where(AeirValidationFindingModel.project_id == project_id)
            .order_by(AeirValidationFindingModel.created_at, AeirValidationFindingModel.finding_id)
        )
    ).all()
    return [row.finding_document for row in rows]


@router.post("/{project_id}/validation-findings/{finding_id}/resolution")
async def resolve_foundation_validation_finding(
    project_id: uuid.UUID,
    finding_id: str,
    request: FoundationFindingResolutionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> dict[str, Any]:
    _require_human(actor)
    finding = await session.scalar(
        select(AeirValidationFindingModel).where(
            AeirValidationFindingModel.project_id == project_id,
            AeirValidationFindingModel.finding_id == finding_id,
        )
    )
    if finding is None:
        raise HTTPException(status_code=404, detail="Validation finding not found")
    decision_document = {
        "schema_version": "validation-finding-resolution-0.1",
        "project_id": str(project_id),
        "finding_id": finding_id,
        "resolution": request.resolution,
        "resolution_note": request.resolution_note,
    }
    decision = AeirDecisionModel(
        id=uuid.uuid4(),
        project_id=project_id,
        snapshot_row_id=finding.snapshot_row_id,
        object_id=None,
        decision_type="validation_finding_resolution",
        decision=request.resolution,
        reviewer_id=actor.subject,
        decision_document=decision_document,
        decision_hash=hash_json(decision_document),
    )
    event = await _event(
        session,
        project_id=project_id,
        model_version_id=finding.model_version_id,
        actor_id=actor.subject,
        event_type="validation.finding.resolved",
        payload=decision_document,
    )
    session.add(decision)
    session.add(event)
    await session.commit()
    return decision_document


@router.post("/{project_id}/snapshots", response_model=FoundationSnapshotResponse)
async def create_foundation_snapshot(
    project_id: uuid.UUID,
    request: FoundationSnapshotRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> FoundationSnapshotResponse:
    _require_human(actor)
    project = await _project(session, project_id)
    model_version = await _required_latest_model_version(session, project_id)
    model = AeirProjectModel.model_validate(model_version.model_document)
    validation = AepmValidationEngine().validate(project.manifest or {})
    if request.status == "approved" and any(finding.blocking for finding in validation.findings):
        raise HTTPException(
            status_code=422,
            detail="Blocking validation findings prevent snapshot approval",
        )
    snapshot = compile_project_snapshot(
        model,
        snapshot_id=await _next_snapshot_id(session, project_id),
        status=request.status,
    )
    write_set = build_aeir_snapshot_write_set(
        project_id=project_id,
        model_version_id=model_version.id,
        model=model,
        snapshot=snapshot,
        validation=validation,
        interpretation=None,
        clarification=None,
        bundle=None,
        traceability=None,
        artifact_version_start=1,
        actor_id=actor.subject,
        event_sequence=await _next_event_sequence(session, project_id),
        previous_event_hash=await _previous_event_hash(session, project_id),
        review_decision={
            "decision": request.status,
            "snapshot_status": request.status,
            "foundation_api": True,
        },
    )
    session.add_all(list(write_set.records))
    await session.commit()
    return _snapshot_response(project_id, write_set.snapshot, model)


@router.get("/{project_id}/snapshots/{snapshot_id}", response_model=FoundationSnapshotResponse)
async def get_foundation_snapshot(
    project_id: uuid.UUID,
    snapshot_id: str,
    session: SessionDependency,
    actor: ActorDependency,
) -> FoundationSnapshotResponse:
    _require_human(actor)
    snapshot = await session.scalar(
        select(AeirProjectSnapshotModel).where(
            AeirProjectSnapshotModel.project_id == project_id,
            AeirProjectSnapshotModel.snapshot_id == snapshot_id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    model_version = await session.get(AeirModelVersionModel, snapshot.model_version_id)
    reconstructed = None if model_version is None else copy.deepcopy(model_version.model_document)
    return FoundationSnapshotResponse(
        project_id=project_id,
        snapshot_id=snapshot.snapshot_id,
        status=snapshot.status,
        snapshot_sha256=snapshot.snapshot_sha256,
        source_model_sha256=snapshot.snapshot_document["source_model_sha256"],
        object_count=len(snapshot.snapshot_document.get("object_versions", [])),
        relationship_count=len(snapshot.snapshot_document.get("relationship_versions", [])),
        reconstructed_model=reconstructed,
    )


async def _project(session: Any, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _latest_model_version(
    session: Any, project_id: uuid.UUID
) -> AeirModelVersionModel | None:
    return await session.scalar(
        select(AeirModelVersionModel)
        .where(AeirModelVersionModel.project_id == project_id)
        .order_by(AeirModelVersionModel.version_number.desc())
        .limit(1)
    )


async def _required_latest_model_version(
    session: Any, project_id: uuid.UUID
) -> AeirModelVersionModel:
    model_version = await _latest_model_version(session, project_id)
    if model_version is None:
        raise HTTPException(status_code=404, detail="AEIR model version not found")
    return model_version


async def _latest_snapshot(session: Any, project_id: uuid.UUID) -> AeirProjectSnapshotModel | None:
    return await session.scalar(
        select(AeirProjectSnapshotModel)
        .where(AeirProjectSnapshotModel.project_id == project_id)
        .order_by(
            AeirProjectSnapshotModel.created_at.desc(),
            AeirProjectSnapshotModel.snapshot_id.desc(),
        )
        .limit(1)
    )


async def _next_object_version(session: Any, object_row_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(func.max(AeirObjectVersionModel.version_number)).where(
            AeirObjectVersionModel.object_row_id == object_row_id
        )
    )
    return int(value or 0) + 1


async def _next_snapshot_id(session: Any, project_id: uuid.UUID) -> str:
    value = await session.scalar(
        select(func.max(AeirProjectSnapshotModel.snapshot_id)).where(
            AeirProjectSnapshotModel.project_id == project_id
        )
    )
    if not value:
        return "SNP-0001"
    return f"SNP-{int(str(value).removeprefix('SNP-')) + 1:04d}"


async def _next_event_sequence(session: Any, project_id: uuid.UUID) -> int:
    value = await session.scalar(
        select(func.max(AeirChangeEventModel.sequence)).where(
            AeirChangeEventModel.project_id == project_id
        )
    )
    return int(value or 0) + 1


async def _previous_event_hash(session: Any, project_id: uuid.UUID) -> str | None:
    return await session.scalar(
        select(AeirChangeEventModel.event_hash)
        .where(AeirChangeEventModel.project_id == project_id)
        .order_by(AeirChangeEventModel.sequence.desc())
        .limit(1)
    )


async def _event(
    session: Any,
    *,
    project_id: uuid.UUID,
    model_version_id: uuid.UUID | None,
    actor_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> AeirChangeEventModel:
    sequence = await _next_event_sequence(session, project_id)
    previous_hash = await _previous_event_hash(session, project_id)
    document = {
        "project_id": str(project_id),
        "sequence": sequence,
        "event_type": event_type,
        "actor_id": actor_id,
        "previous_hash": previous_hash,
        "payload": payload,
    }
    return AeirChangeEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=model_version_id,
        sequence=sequence,
        event_type=event_type,
        actor_id=actor_id,
        previous_hash=previous_hash,
        event_hash=hash_json(document),
        payload=payload,
    )


def _object_payload(row: AeirObjectModel) -> dict[str, Any]:
    return {
        "id": row.object_id,
        "type": row.object_type,
        "name": row.name,
        "description": row.description,
        "lifecycle_status": row.lifecycle_status,
        "truth_status": row.truth_status,
        "approval_status": row.approval_status,
        "confidence": row.confidence,
        "version": row.object_version,
        "source_refs": row.source_refs,
        "evidence_refs": row.evidence_refs,
        "relationship_refs": row.relationship_refs,
        "attributes": row.attributes,
        "metadata": row.object_metadata,
        "source": row.source_document,
    }


def _snapshot_response(
    project_id: uuid.UUID,
    snapshot: AeirProjectSnapshotModel,
    model: AeirProjectModel,
) -> FoundationSnapshotResponse:
    return FoundationSnapshotResponse(
        project_id=project_id,
        snapshot_id=snapshot.snapshot_id,
        status=snapshot.status,
        snapshot_sha256=snapshot.snapshot_sha256,
        source_model_sha256=snapshot.snapshot_document["source_model_sha256"],
        object_count=len(model.objects),
        relationship_count=len(model.relationships),
        reconstructed_model=model.model_dump(mode="json"),
    )
