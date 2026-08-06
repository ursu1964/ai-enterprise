from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r5_umte_schemas import (
    R5ArtifactSpecResponse,
    R5ExportBundleResponse,
    R5GeneratedArtifactResponse,
    R5TransformationResultResponse,
    R5TransformationRunRequest,
    R5TransformationRunResponse,
    R5VerificationReportResponse,
)
from ai_enterprise.domain.aeir import AeirProjectModel, ProjectSnapshot
from ai_enterprise.domain.r5_umte import (
    UmteTransformationResult,
    compile_umte_export_bundle,
    compile_umte_transformation,
    require_approved_snapshot,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    AeirModelVersionModel,
    AeirProjectSnapshotModel,
    R5ArtifactSpecModel,
    R5ExportBundleModel,
    R5GeneratedArtifactModel,
    R5TransformationRunModel,
    R5VerificationReportModel,
)

router = APIRouter(prefix="/projects", tags=["r5-umte"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human project authority is required")


@router.post(
    "/{project_id}/umte/transformations",
    response_model=R5TransformationResultResponse,
    status_code=201,
)
async def create_umte_transformation(
    project_id: uuid.UUID,
    request: R5TransformationRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R5TransformationResultResponse:
    _require_human(actor)
    await _project(session, project_id)
    model_version = await _required_latest_model_version(session, project_id)
    snapshot_row = await _latest_snapshot(session, project_id)
    snapshot = _snapshot(snapshot_row) if snapshot_row is not None else None
    if request.require_approved_snapshot:
        try:
            require_approved_snapshot(snapshot)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    model = AeirProjectModel.model_validate(model_version.model_document)
    result = compile_umte_transformation(
        model,
        snapshot,
        target_stack=tuple(request.target_stack),
        registry_version=request.registry_version,
        template_pack_version=request.template_pack_version,
    )
    existing = await session.scalar(
        select(R5TransformationRunModel).where(
            R5TransformationRunModel.project_id == project_id,
            R5TransformationRunModel.run_hash == result.result_hash,
        )
    )
    if existing is not None:
        return await _result_response(session, existing)

    run = R5TransformationRunModel(
        id=uuid.uuid4(),
        project_id=project_id,
        model_version_id=model_version.id,
        snapshot_row_id=None if snapshot_row is None else snapshot_row.id,
        source_model_sha256=result.plan.source_model_sha256,
        source_snapshot_id=result.plan.source_snapshot_id,
        source_snapshot_sha256=result.plan.source_snapshot_sha256,
        registry_version=result.plan.registry_version,
        template_pack_version=result.plan.template_pack_version,
        target_stack=list(result.plan.target_stack),
        status=result.verification_report.status.value,
        artifact_count=len(result.artifact_specs),
        blocking_finding_count=sum(
            1 for finding in result.verification_report.findings if finding.blocking
        ),
        plan_document=result.plan.model_dump(mode="json"),
        plan_hash=result.plan.plan_hash,
        result_document=result.model_dump(mode="json"),
        run_hash=result.result_hash,
        created_by=actor.subject,
    )
    session.add(run)
    artifact_rows = [
        R5ArtifactSpecModel(
            id=uuid.uuid4(),
            project_id=project_id,
            transformation_run_id=run.id,
            artifact_key=artifact.artifact_key,
            artifact_kind=artifact.artifact_kind.value,
            target=artifact.target,
            source_object_id=artifact.source_object_id,
            source_object_type=artifact.source_object_type.value,
            depends_on_object_ids=list(artifact.depends_on_object_ids),
            artifact_document=artifact.specification_document,
            provenance_document=artifact.provenance.model_dump(mode="json"),
            artifact_spec_hash=artifact.artifact_spec_hash,
        )
        for artifact in result.artifact_specs
    ]
    generated_rows = [
        R5GeneratedArtifactModel(
            id=uuid.uuid4(),
            project_id=project_id,
            transformation_run_id=run.id,
            artifact_key=artifact.artifact_key,
            artifact_kind=artifact.artifact_kind.value,
            target=artifact.target,
            media_type=artifact.media_type,
            source_artifact_spec_hash=artifact.source_artifact_spec_hash,
            content_document=artifact.content_document,
            generated_hash=artifact.generated_hash,
        )
        for artifact in result.generated_artifacts
    ]
    report = R5VerificationReportModel(
        id=uuid.uuid4(),
        project_id=project_id,
        transformation_run_id=run.id,
        status=result.verification_report.status.value,
        finding_count=len(result.verification_report.findings),
        blocking_finding_count=run.blocking_finding_count,
        report_document=result.verification_report.model_dump(mode="json"),
        report_hash=result.verification_report.report_hash,
    )
    session.add_all([*artifact_rows, *generated_rows, report])
    await session.commit()
    return R5TransformationResultResponse(
        run=R5TransformationRunResponse.model_validate(run),
        artifacts=[R5ArtifactSpecResponse.model_validate(row) for row in artifact_rows],
        generated_artifacts=[
            R5GeneratedArtifactResponse.model_validate(row) for row in generated_rows
        ],
        verification=R5VerificationReportResponse.model_validate(report),
    )


@router.get(
    "/{project_id}/umte/transformations",
    response_model=list[R5TransformationRunResponse],
)
async def list_umte_transformations(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R5TransformationRunResponse]:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R5TransformationRunModel)
            .where(R5TransformationRunModel.project_id == project_id)
            .order_by(R5TransformationRunModel.created_at.desc())
        )
    ).all()
    return [R5TransformationRunResponse.model_validate(row) for row in rows]


@router.get(
    "/{project_id}/umte/transformations/{run_id}",
    response_model=R5TransformationResultResponse,
)
async def get_umte_transformation(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R5TransformationResultResponse:
    _require_human(actor)
    await _project(session, project_id)
    run = await session.get(R5TransformationRunModel, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="UMTE transformation not found")
    return await _result_response(session, run)


@router.post(
    "/{project_id}/umte/transformations/{run_id}/export-bundle",
    response_model=R5ExportBundleResponse,
    status_code=201,
)
async def create_umte_export_bundle(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R5ExportBundleResponse:
    _require_human(actor)
    await _project(session, project_id)
    run = await session.get(R5TransformationRunModel, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="UMTE transformation not found")
    existing = await session.scalar(
        select(R5ExportBundleModel).where(
            R5ExportBundleModel.transformation_run_id == run.id
        )
    )
    if existing is not None:
        return R5ExportBundleResponse.model_validate(existing)
    result = UmteTransformationResult.model_validate(run.result_document)
    try:
        bundle = compile_umte_export_bundle(result)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = R5ExportBundleModel(
        id=uuid.uuid4(),
        project_id=project_id,
        transformation_run_id=run.id,
        artifact_count=bundle.artifact_count,
        source_model_sha256=bundle.source_model_sha256,
        source_snapshot_id=bundle.source_snapshot_id,
        source_snapshot_sha256=bundle.source_snapshot_sha256,
        registry_version=bundle.registry_version,
        template_pack_version=bundle.template_pack_version,
        bundle_document=bundle.model_dump(mode="json"),
        bundle_hash=bundle.bundle_hash,
        created_by=actor.subject,
    )
    session.add(row)
    await session.commit()
    return R5ExportBundleResponse.model_validate(row)


@router.get(
    "/{project_id}/umte/transformations/{run_id}/export-bundle",
    response_model=R5ExportBundleResponse,
)
async def get_umte_export_bundle(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R5ExportBundleResponse:
    _require_human(actor)
    await _project(session, project_id)
    run = await session.get(R5TransformationRunModel, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="UMTE transformation not found")
    row = await session.scalar(
        select(R5ExportBundleModel).where(R5ExportBundleModel.transformation_run_id == run.id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="UMTE export bundle not found")
    return R5ExportBundleResponse.model_validate(row)


async def _result_response(
    session: object, run: R5TransformationRunModel
) -> R5TransformationResultResponse:
    artifacts = (
        await session.scalars(
            select(R5ArtifactSpecModel)
            .where(R5ArtifactSpecModel.transformation_run_id == run.id)
            .order_by(R5ArtifactSpecModel.artifact_key)
        )
    ).all()
    generated_artifacts = (
        await session.scalars(
            select(R5GeneratedArtifactModel)
            .where(R5GeneratedArtifactModel.transformation_run_id == run.id)
            .order_by(R5GeneratedArtifactModel.artifact_key)
        )
    ).all()
    report = await session.scalar(
        select(R5VerificationReportModel).where(
            R5VerificationReportModel.transformation_run_id == run.id
        )
    )
    if report is None:
        raise HTTPException(status_code=500, detail="UMTE verification report missing")
    return R5TransformationResultResponse(
        run=R5TransformationRunResponse.model_validate(run),
        artifacts=[R5ArtifactSpecResponse.model_validate(row) for row in artifacts],
        generated_artifacts=[
            R5GeneratedArtifactResponse.model_validate(row) for row in generated_artifacts
        ],
        verification=R5VerificationReportResponse.model_validate(report),
    )


async def _project(session: object, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _required_latest_model_version(
    session: object, project_id: uuid.UUID
) -> AeirModelVersionModel:
    row = await session.scalar(
        select(AeirModelVersionModel)
        .where(AeirModelVersionModel.project_id == project_id)
        .order_by(AeirModelVersionModel.version_number.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="AEIR model version not found")
    return row


async def _latest_snapshot(
    session: object, project_id: uuid.UUID
) -> AeirProjectSnapshotModel | None:
    return await session.scalar(
        select(AeirProjectSnapshotModel)
        .where(AeirProjectSnapshotModel.project_id == project_id)
        .order_by(
            AeirProjectSnapshotModel.created_at.desc(),
            AeirProjectSnapshotModel.snapshot_id.desc(),
        )
        .limit(1)
    )


def _snapshot(row: AeirProjectSnapshotModel) -> ProjectSnapshot:
    return ProjectSnapshot.model_validate(row.snapshot_document)
