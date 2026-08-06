from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency
from ai_enterprise.api.r6_uagf_schemas import (
    R6ArtifactRepositoryPublicationRequest,
    R6ArtifactRepositoryPublicationResponse,
    R6ArtifactRepositoryReadinessResponse,
    R6GeneratedFileResponse,
    R6GenerationBuildRequest,
    R6GenerationBuildResponse,
    R6GenerationResultResponse,
    R6GeneratorPackResponse,
    R6InstalledGeneratorPackResponse,
    R6InstallGeneratorPackRequest,
    R6LifecycleEventResponse,
    R6LifecycleTransitionRequest,
    R6ParallelGenerationPlanRequest,
    R6ParallelGenerationPlanResponse,
    R6RegenerationPlanRequest,
    R6RegenerationPlanResponse,
    R6ValidationGateRunRequest,
    R6ValidationGateRunResponse,
    R6ValidationReportResponse,
)
from ai_enterprise.config import get_settings
from ai_enterprise.domain.r5_umte import UmteExportBundle, UmteGeneratedArtifact
from ai_enterprise.domain.r6_uagf import (
    UagfArtifactRepositoryKind,
    UagfBuildManifest,
    UagfFileLifecycle,
    UagfGeneratedFile,
    UagfGenerationResult,
    UagfLifecycleEvent,
    UagfLifecycleEventType,
    UagfValidationGateStatus,
    UagfValidationReport,
    certified_uagf_generator_packs,
    current_uagf_lifecycle_status,
    generate_uagf_build,
    install_uagf_generator_pack,
    plan_parallel_uagf_generation,
    plan_uagf_regeneration,
    publish_uagf_artifacts_to_repository,
    transition_uagf_lifecycle,
    uagf_validation_gate_run,
)
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.knowledge.models import (
    R5ExportBundleModel,
    R5GeneratedArtifactModel,
    R6ArtifactRepositoryPublicationModel,
    R6GeneratedFileModel,
    R6GenerationBuildModel,
    R6InstalledGeneratorPackModel,
    R6LifecycleEventModel,
    R6ParallelGenerationPlanModel,
    R6ValidationGateRunModel,
    R6ValidationReportModel,
)

router = APIRouter(prefix="/projects", tags=["r6-uagf"])


def _require_human(actor: object) -> None:
    if getattr(actor, "actor_type", None) != "human":
        raise HTTPException(status_code=403, detail="Human project authority is required")


@router.get(
    "/{project_id}/uagf/generator-packs/marketplace",
    response_model=list[R6GeneratorPackResponse],
)
async def list_uagf_generator_pack_marketplace(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R6GeneratorPackResponse]:
    _require_human(actor)
    await _project(session, project_id)
    return [
        R6GeneratorPackResponse(
            **{
                **pack.model_dump(mode="json"),
                "technology_stack": list(pack.technology_stack),
                "supported_targets": list(pack.supported_targets),
                "validation_gates": list(pack.validation_gates),
                "repository_kinds": [kind.value for kind in pack.repository_kinds],
            }
        )
        for pack in certified_uagf_generator_packs()
    ]


@router.post(
    "/{project_id}/uagf/generator-packs/installations",
    response_model=R6InstalledGeneratorPackResponse,
    status_code=201,
)
async def install_uagf_generator_pack_for_project(
    project_id: uuid.UUID,
    request: R6InstallGeneratorPackRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6InstalledGeneratorPackResponse:
    _require_human(actor)
    await _project(session, project_id)
    existing = await session.scalar(
        select(R6InstalledGeneratorPackModel).where(
            R6InstalledGeneratorPackModel.project_id == project_id,
            R6InstalledGeneratorPackModel.pack_id == request.pack_id,
            R6InstalledGeneratorPackModel.version == request.version,
        )
    )
    if existing is not None:
        return R6InstalledGeneratorPackResponse.model_validate(existing)
    count = len(
        (
            await session.scalars(
                select(R6InstalledGeneratorPackModel).where(
                    R6InstalledGeneratorPackModel.project_id == project_id
                )
            )
        ).all()
    )
    try:
        installation = install_uagf_generator_pack(
            index=count + 1,
            project_id=str(project_id),
            pack_id=request.pack_id,
            version=request.version,
            installed_by=actor.subject,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = R6InstalledGeneratorPackModel(
        id=uuid.uuid4(),
        project_id=project_id,
        installation_id=installation.installation_id,
        pack_id=installation.pack.pack_id,
        version=installation.pack.version,
        status=installation.pack.status.value,
        technology_stack=list(installation.pack.technology_stack),
        supported_targets=list(installation.pack.supported_targets),
        validation_gates=list(installation.pack.validation_gates),
        repository_kinds=[kind.value for kind in installation.pack.repository_kinds],
        pack_document=installation.pack.model_dump(mode="json"),
        installation_document=installation.model_dump(mode="json"),
        installation_hash=installation.installation_hash,
        installed_by=installation.installed_by,
    )
    session.add(row)
    await session.commit()
    return R6InstalledGeneratorPackResponse.model_validate(row)


@router.get(
    "/{project_id}/uagf/generator-packs/installations",
    response_model=list[R6InstalledGeneratorPackResponse],
)
async def list_uagf_installed_generator_packs(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R6InstalledGeneratorPackResponse]:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R6InstalledGeneratorPackModel)
            .where(R6InstalledGeneratorPackModel.project_id == project_id)
            .order_by(R6InstalledGeneratorPackModel.created_at.desc())
        )
    ).all()
    return [R6InstalledGeneratorPackResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uagf/builds/from-r5-export-bundle/{bundle_id}",
    response_model=R6GenerationResultResponse,
    status_code=201,
)
async def create_uagf_build(
    project_id: uuid.UUID,
    bundle_id: uuid.UUID,
    request: R6GenerationBuildRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6GenerationResultResponse:
    _require_human(actor)
    await _project(session, project_id)
    bundle_row = await session.get(R5ExportBundleModel, bundle_id)
    if bundle_row is None or bundle_row.project_id != project_id:
        raise HTTPException(status_code=404, detail="R5 export bundle not found")
    existing = await session.scalar(
        select(R6GenerationBuildModel).where(
            R6GenerationBuildModel.r5_export_bundle_id == bundle_row.id,
            R6GenerationBuildModel.generator_pack_id == request.generator_pack_id,
            R6GenerationBuildModel.generator_pack_version == request.generator_pack_version,
        )
    )
    if existing is not None:
        return await _result_response(session, existing)

    bundle, generated_artifacts = await _r5_generation_inputs(session, project_id, bundle_row)
    try:
        result = generate_uagf_build(
            bundle,
            generated_artifacts,
            generator_pack_id=request.generator_pack_id,
            generator_pack_version=request.generator_pack_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    root = _build_root(project_id, result.build_hash)
    _write_build_files(root, result.files)
    build = R6GenerationBuildModel(
        id=uuid.uuid4(),
        project_id=project_id,
        r5_export_bundle_id=bundle_row.id,
        r5_export_bundle_hash=bundle.bundle_hash,
        status=result.validation_report.status.value,
        generator_pack_id=result.manifest.generator_pack_id,
        generator_pack_version=result.manifest.generator_pack_version,
        artifact_count=result.manifest.artifact_count,
        file_count=result.manifest.file_count,
        root_path=str(root),
        manifest_document=result.manifest.model_dump(mode="json"),
        manifest_hash=result.manifest.manifest_hash,
        build_hash=result.build_hash,
        created_by=actor.subject,
    )
    session.add(build)
    file_rows = [
        R6GeneratedFileModel(
            id=uuid.uuid4(),
            project_id=project_id,
            generation_build_id=build.id,
            file_id=file.file_id,
            artifact_key=file.artifact_key,
            relative_path=file.relative_path,
            media_type=file.media_type,
            generator_id=file.generator_id,
            template_ref=file.template_ref,
            lifecycle_status=file.lifecycle_status.value,
            content_hash=file.content_hash,
            file_hash=file.file_hash,
            file_document=file.model_dump(mode="json", exclude={"content"}),
        )
        for file in result.files
    ]
    report = R6ValidationReportModel(
        id=uuid.uuid4(),
        project_id=project_id,
        generation_build_id=build.id,
        status=result.validation_report.status.value,
        finding_count=len(result.validation_report.findings),
        blocking_finding_count=sum(
            1 for finding in result.validation_report.findings if finding.blocking
        ),
        report_document=result.validation_report.model_dump(mode="json"),
        report_hash=result.validation_report.report_hash,
    )
    session.add_all([*file_rows, report])
    await session.commit()
    return R6GenerationResultResponse(
        build=R6GenerationBuildResponse.model_validate(build),
        files=[R6GeneratedFileResponse.model_validate(row) for row in file_rows],
        validation=R6ValidationReportResponse.model_validate(report),
    )


@router.post(
    "/{project_id}/uagf/regeneration-plans/from-r5-export-bundle/{bundle_id}",
    response_model=R6RegenerationPlanResponse,
)
async def plan_uagf_build_regeneration(
    project_id: uuid.UUID,
    bundle_id: uuid.UUID,
    request: R6RegenerationPlanRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6RegenerationPlanResponse:
    _require_human(actor)
    await _project(session, project_id)
    bundle_row = await session.get(R5ExportBundleModel, bundle_id)
    if bundle_row is None or bundle_row.project_id != project_id:
        raise HTTPException(status_code=404, detail="R5 export bundle not found")
    bundle, generated_artifacts = await _r5_generation_inputs(session, project_id, bundle_row)
    previous_files: tuple[UagfGeneratedFile, ...] = ()
    if request.previous_build_id is not None:
        previous_build = await session.get(R6GenerationBuildModel, request.previous_build_id)
        if previous_build is None or previous_build.project_id != project_id:
            raise HTTPException(status_code=404, detail="Previous UAGF build not found")
        previous_files = await _stored_uagf_files(session, previous_build)
    try:
        plan = plan_uagf_regeneration(
            bundle,
            generated_artifacts,
            previous_files,
            generator_pack_id=request.generator_pack_id,
            generator_pack_version=request.generator_pack_version,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    document = plan.model_dump(mode="json")
    return R6RegenerationPlanResponse(
        **{
            **document,
            "reused_file_ids": list(document["reused_file_ids"]),
            "regenerated_artifact_keys": list(document["regenerated_artifact_keys"]),
            "removed_artifact_keys": list(document["removed_artifact_keys"]),
        }
    )


@router.get(
    "/{project_id}/uagf/builds",
    response_model=list[R6GenerationBuildResponse],
)
async def list_uagf_builds(
    project_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R6GenerationBuildResponse]:
    _require_human(actor)
    await _project(session, project_id)
    rows = (
        await session.scalars(
            select(R6GenerationBuildModel)
            .where(R6GenerationBuildModel.project_id == project_id)
            .order_by(R6GenerationBuildModel.created_at.desc())
        )
    ).all()
    return [R6GenerationBuildResponse.model_validate(row) for row in rows]


@router.get(
    "/{project_id}/uagf/builds/{build_id}",
    response_model=R6GenerationResultResponse,
)
async def get_uagf_build(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6GenerationResultResponse:
    _require_human(actor)
    await _project(session, project_id)
    build = await session.get(R6GenerationBuildModel, build_id)
    if build is None or build.project_id != project_id:
        raise HTTPException(status_code=404, detail="UAGF build not found")
    return await _result_response(session, build)


@router.get(
    "/{project_id}/uagf/builds/{build_id}/lifecycle/events",
    response_model=list[R6LifecycleEventResponse],
)
async def list_uagf_lifecycle_events(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    session: SessionDependency,
    actor: ActorDependency,
) -> list[R6LifecycleEventResponse]:
    _require_human(actor)
    build = await _build(session, project_id, build_id)
    rows = await _lifecycle_event_rows(session, build)
    return [R6LifecycleEventResponse.model_validate(row) for row in rows]


@router.post(
    "/{project_id}/uagf/builds/{build_id}/lifecycle/transitions",
    response_model=R6LifecycleEventResponse,
    status_code=201,
)
async def transition_uagf_build_lifecycle(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    request: R6LifecycleTransitionRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6LifecycleEventResponse:
    _require_human(actor)
    build = await _build(session, project_id, build_id)
    if build.status != "verified":
        raise HTTPException(status_code=409, detail="Only verified UAGF builds can enter lifecycle")
    all_rows = await _lifecycle_event_rows(session, build)
    target_rows = [row for row in all_rows if row.file_id == request.file_id]
    try:
        current_status = current_uagf_lifecycle_status(
            tuple(_lifecycle_event_from_row(row) for row in target_rows)
        )
        event = transition_uagf_lifecycle(
            index=len(all_rows) + 1,
            build_hash=build.build_hash,
            current_status=current_status,
            event_type=UagfLifecycleEventType(request.event_type),
            actor=actor.subject,
            reason=request.reason,
            file_id=request.file_id,
            policy_document=request.policy_document,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = R6LifecycleEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        generation_build_id=build.id,
        event_id=event.event_id,
        build_hash=event.build_hash,
        file_id=event.file_id,
        event_type=event.event_type.value,
        from_status=event.from_status.value,
        to_status=event.to_status.value,
        actor=event.actor,
        reason=event.reason,
        policy_document=event.policy_document,
        event_hash=event.event_hash,
    )
    session.add(row)
    await session.commit()
    return R6LifecycleEventResponse.model_validate(row)


@router.post(
    "/{project_id}/uagf/builds/{build_id}/parallel-generation-plans",
    response_model=R6ParallelGenerationPlanResponse,
    status_code=201,
)
async def create_uagf_parallel_generation_plan(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    request: R6ParallelGenerationPlanRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6ParallelGenerationPlanResponse:
    _require_human(actor)
    build = await _build(session, project_id, build_id)
    result = await _generation_result_from_build(session, build)
    count = len(
        (
            await session.scalars(
                select(R6ParallelGenerationPlanModel).where(
                    R6ParallelGenerationPlanModel.generation_build_id == build.id
                )
            )
        ).all()
    )
    plan = plan_parallel_uagf_generation(
        index=count + 1,
        build=result,
        max_parallelism=request.max_parallelism,
    )
    row = R6ParallelGenerationPlanModel(
        id=uuid.uuid4(),
        project_id=project_id,
        generation_build_id=build.id,
        plan_id=plan.plan_id,
        generator_pack_id=plan.generator_pack_id,
        max_parallelism=plan.max_parallelism,
        lanes_document={key: list(value) for key, value in plan.lanes.items()},
        plan_document=plan.model_dump(mode="json"),
        plan_hash=plan.plan_hash,
    )
    session.add(row)
    await session.commit()
    return R6ParallelGenerationPlanResponse.model_validate(row)


@router.post(
    "/{project_id}/uagf/builds/{build_id}/validation-gates",
    response_model=R6ValidationGateRunResponse,
    status_code=201,
)
async def run_uagf_validation_gate(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    request: R6ValidationGateRunRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6ValidationGateRunResponse:
    _require_human(actor)
    build = await _build(session, project_id, build_id)
    command = _validation_gate_command(request.gate_id)
    count = len(
        (
            await session.scalars(
                select(R6ValidationGateRunModel).where(
                    R6ValidationGateRunModel.generation_build_id == build.id
                )
            )
        ).all()
    )
    status, exit_code, output = _execute_validation_gate(command, Path(build.root_path))
    gate = uagf_validation_gate_run(
        index=count + 1,
        build_hash=build.build_hash,
        gate_id=request.gate_id,
        command=command,
        status=status,
        exit_code=exit_code,
        output=output,
    )
    row = R6ValidationGateRunModel(
        id=uuid.uuid4(),
        project_id=project_id,
        generation_build_id=build.id,
        gate_run_id=gate.gate_run_id,
        gate_id=gate.gate_id,
        command=list(gate.command),
        status=gate.status.value,
        exit_code=gate.exit_code,
        output_hash=gate.output_hash,
        gate_document=gate.model_dump(mode="json"),
        gate_hash=gate.gate_hash,
    )
    session.add(row)
    await session.commit()
    return R6ValidationGateRunResponse.model_validate(row)


@router.post(
    "/{project_id}/uagf/builds/{build_id}/artifact-repository-publications",
    response_model=R6ArtifactRepositoryPublicationResponse,
    status_code=201,
)
async def publish_uagf_build_to_artifact_repository(
    project_id: uuid.UUID,
    build_id: uuid.UUID,
    request: R6ArtifactRepositoryPublicationRequest,
    session: SessionDependency,
    actor: ActorDependency,
) -> R6ArtifactRepositoryPublicationResponse:
    _require_human(actor)
    build = await _build(session, project_id, build_id)
    result = await _generation_result_from_build(session, build)
    count = len(
        (
            await session.scalars(
                select(R6ArtifactRepositoryPublicationModel).where(
                    R6ArtifactRepositoryPublicationModel.generation_build_id == build.id
                )
            )
        ).all()
    )
    publication = publish_uagf_artifacts_to_repository(
        index=count + 1,
        build=result,
        repository_kind=UagfArtifactRepositoryKind(request.repository_kind),
        repository_ref=_materialize_repository_publication(
            project_id=project_id,
            build=build,
            repository_kind=UagfArtifactRepositoryKind(request.repository_kind),
            repository_ref=request.repository_ref,
            version_ref=request.version_ref,
        ),
        version_ref=request.version_ref,
    )
    row = R6ArtifactRepositoryPublicationModel(
        id=uuid.uuid4(),
        project_id=project_id,
        generation_build_id=build.id,
        publication_id=publication.publication_id,
        repository_kind=publication.repository_kind.value,
        repository_ref=publication.repository_ref,
        version_ref=publication.version_ref,
        file_count=publication.file_count,
        content_address=publication.content_address,
        publication_document=publication.model_dump(mode="json"),
        publication_hash=publication.publication_hash,
    )
    session.add(row)
    await session.commit()
    return R6ArtifactRepositoryPublicationResponse.model_validate(row)


@router.get(
    "/{project_id}/uagf/artifact-repositories/readiness",
    response_model=R6ArtifactRepositoryReadinessResponse,
)
async def uagf_artifact_repository_readiness(
    project_id: uuid.UUID,
    repository_kind: str,
    session: SessionDependency,
    actor: ActorDependency,
    repository_ref: str | None = None,
) -> R6ArtifactRepositoryReadinessResponse:
    _require_human(actor)
    await _project(session, project_id)
    try:
        kind = UagfArtifactRepositoryKind(repository_kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Unsupported artifact repository kind") from exc
    report = _artifact_repository_readiness(kind, repository_ref)
    return R6ArtifactRepositoryReadinessResponse(**report)


async def _result_response(
    session: object, build: R6GenerationBuildModel
) -> R6GenerationResultResponse:
    files = (
        await session.scalars(
            select(R6GeneratedFileModel)
            .where(R6GeneratedFileModel.generation_build_id == build.id)
            .order_by(R6GeneratedFileModel.relative_path)
        )
    ).all()
    report = await session.scalar(
        select(R6ValidationReportModel).where(
            R6ValidationReportModel.generation_build_id == build.id
        )
    )
    if report is None:
        raise HTTPException(status_code=500, detail="UAGF validation report missing")
    return R6GenerationResultResponse(
        build=R6GenerationBuildResponse.model_validate(build),
        files=[R6GeneratedFileResponse.model_validate(row) for row in files],
        validation=R6ValidationReportResponse.model_validate(report),
    )


async def _generation_result_from_build(
    session: object, build: R6GenerationBuildModel
) -> UagfGenerationResult:
    files = await _stored_uagf_files(session, build)
    report = await session.scalar(
        select(R6ValidationReportModel).where(
            R6ValidationReportModel.generation_build_id == build.id
        )
    )
    if report is None:
        raise HTTPException(status_code=500, detail="UAGF validation report missing")
    return UagfGenerationResult(
        manifest=UagfBuildManifest.model_validate(build.manifest_document),
        files=files,
        validation_report=UagfValidationReport.model_validate(report.report_document),
        build_hash=build.build_hash,
    )


def _validation_gate_command(gate_id: str) -> tuple[str, ...]:
    commands = {
        "docker.build": ("docker", "build", "."),
        "dotnet.build": ("dotnet", "build", "--nologo"),
        "maven.test": ("mvn", "test"),
        "npm.test": ("npm", "test"),
        "python.pytest": ("python", "-m", "pytest", "-q"),
        "terraform.validate": ("terraform", "validate", "-no-color"),
    }
    try:
        return commands[gate_id]
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Unsupported UAGF validation gate") from exc


def _execute_validation_gate(
    command: tuple[str, ...], root: Path
) -> tuple[UagfValidationGateStatus, int | None, str]:
    executable = shutil.which(command[0])
    if executable is None:
        return (
            UagfValidationGateStatus.SKIPPED,
            None,
            f"Validation tool is not installed: {command[0]}",
        )
    if not root.exists():
        return UagfValidationGateStatus.FAILED, 127, "UAGF build root does not exist"
    completed = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    status = (
        UagfValidationGateStatus.PASSED
        if completed.returncode == 0
        else UagfValidationGateStatus.FAILED
    )
    return status, completed.returncode, output[:4000]


def _materialize_repository_publication(
    *,
    project_id: uuid.UUID,
    build: R6GenerationBuildModel,
    repository_kind: UagfArtifactRepositoryKind,
    repository_ref: str,
    version_ref: str,
) -> str:
    repository_root = (
        get_settings().artifact_root / "r6-repositories" / str(project_id)
    ).resolve()
    artifact_root = get_settings().artifact_root.resolve()
    if artifact_root not in repository_root.parents:
        raise HTTPException(status_code=500, detail="Invalid artifact repository root")
    safe_version = version_ref.replace("/", "_").replace("..", "_")
    if repository_kind is UagfArtifactRepositoryKind.FILESYSTEM:
        target_root = (repository_root / "filesystem" / safe_version).resolve()
        if repository_root not in target_root.parents:
            raise HTTPException(status_code=500, detail="Invalid artifact repository target")
        source_root = Path(build.root_path).resolve()
        if not source_root.exists():
            raise HTTPException(status_code=409, detail="UAGF build files are missing")
        for source in source_root.rglob("*"):
            if not source.is_file():
                continue
            relative = source.relative_to(source_root)
            target = (target_root / relative).resolve()
            if target_root not in target.parents:
                raise HTTPException(status_code=500, detail="Unsafe repository file target")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        return str(target_root)
    source_root = Path(build.root_path).resolve()
    if not source_root.exists():
        raise HTTPException(status_code=409, detail="UAGF build files are missing")
    if repository_kind is UagfArtifactRepositoryKind.GIT:
        return _publish_to_git_repository(
            source_root=source_root,
            repository_ref=repository_ref,
            version_ref=version_ref,
            work_root=(repository_root / "git-work" / safe_version).resolve(),
        )
    if repository_kind is UagfArtifactRepositoryKind.S3:
        return _publish_to_s3_repository(
            source_root=source_root,
            repository_ref=repository_ref,
            version_ref=version_ref,
        )
    if repository_kind is UagfArtifactRepositoryKind.PACKAGE_REGISTRY:
        return _publish_to_package_registry(
            source_root=source_root,
            repository_ref=repository_ref,
            version_ref=version_ref,
            work_root=(repository_root / "package-work" / safe_version).resolve(),
            build_hash=build.build_hash,
        )
    raise HTTPException(status_code=422, detail="Unsupported artifact repository kind")


def _artifact_repository_readiness(
    repository_kind: UagfArtifactRepositoryKind,
    repository_ref: str | None,
) -> dict[str, object]:
    checks: list[dict[str, object]] = []
    required: list[str] = []
    settings = get_settings()
    _readiness_check(
        checks,
        "artifact_root",
        settings.artifact_root.exists() or settings.artifact_root.parent.exists(),
        f"Artifact root is {settings.artifact_root}.",
        "Create artifact_root or ensure its parent is writable.",
    )
    if repository_kind is UagfArtifactRepositoryKind.FILESYSTEM:
        _readiness_check(
            checks,
            "filesystem_repository",
            True,
            "Filesystem repository publication uses local artifact_root storage.",
            "No external credential is required.",
        )
    elif repository_kind is UagfArtifactRepositoryKind.GIT:
        _readiness_check(
            checks,
            "git_executable",
            shutil.which("git") is not None,
            "git executable is available.",
            "Install git in the API runtime image.",
        )
        git_ssh_config_path = getattr(settings, "r6_publication_git_ssh_config_path", None)
        if git_ssh_config_path is not None:
            _readiness_check(
                checks,
                "git_ssh_config",
                git_ssh_config_path.exists(),
                "Configured Git SSH config path exists.",
                "Mount R6_PUBLICATION_GIT_SSH_CONFIG_PATH into the API runtime.",
            )
        required.append("Git remote credentials via SSH config, credential helper, or URL auth")
        if repository_ref:
            ok, detail = _probe_command(
                ("git", "ls-remote", repository_ref),
                timeout=20,
                env=_publication_environment(),
            )
            _readiness_check(
                checks,
                "git_remote_access",
                ok,
                detail,
                "Grant the API runtime read/write access to the Git remote.",
            )
    elif repository_kind is UagfArtifactRepositoryKind.S3:
        _readiness_check(
            checks,
            "aws_cli",
            shutil.which("aws") is not None,
            "AWS CLI is available.",
            "Install AWS CLI in the API runtime image.",
        )
        has_aws_config = bool(
            getattr(settings, "r6_publication_aws_profile", None)
            or os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_WEB_IDENTITY_TOKEN_FILE")
            or os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
        )
        _readiness_check(
            checks,
            "aws_credentials",
            has_aws_config,
            "AWS credentials/profile are configured.",
            "Set R6_PUBLICATION_AWS_PROFILE or standard AWS credential environment.",
        )
        required.extend(
            ["AWS CLI", "AWS credentials with s3:ListBucket/s3:PutObject", "s3:// repository_ref"]
        )
        if repository_ref:
            _readiness_check(
                checks,
                "s3_repository_ref",
                repository_ref.startswith("s3://"),
                "S3 repository_ref uses s3://.",
                "Use an s3://bucket/prefix repository_ref.",
            )
        if shutil.which("aws") is not None and has_aws_config:
            ok, detail = _probe_command(
                _aws_readiness_command("sts", "get-caller-identity"),
                timeout=20,
                env=_publication_environment(),
            )
            _readiness_check(
                checks,
                "aws_identity",
                ok,
                detail,
                "Ensure AWS credentials are valid for the API runtime.",
            )
            if repository_ref and repository_ref.startswith("s3://"):
                ok, detail = _probe_command(
                    _aws_readiness_command("s3", "ls", repository_ref),
                    timeout=20,
                    env=_publication_environment(),
                )
                _readiness_check(
                    checks,
                    "s3_repository_access",
                    ok,
                    detail,
                    "Grant s3:ListBucket on the configured S3 bucket/prefix.",
                )
    elif repository_kind is UagfArtifactRepositoryKind.PACKAGE_REGISTRY:
        _readiness_check(
            checks,
            "npm_executable",
            shutil.which("npm") is not None,
            "npm executable is available.",
            "Install npm in the API runtime image.",
        )
        has_npm_auth = bool(
            getattr(settings, "r6_publication_npm_token", None)
            or os.environ.get("NPM_TOKEN")
            or (
                getattr(settings, "r6_publication_npmrc_path", None)
                and settings.r6_publication_npmrc_path.exists()
            )
        )
        _readiness_check(
            checks,
            "npm_auth",
            has_npm_auth,
            "npm registry auth is configured.",
            "Set R6_PUBLICATION_NPM_TOKEN, NPM_TOKEN, or R6_PUBLICATION_NPMRC_PATH.",
        )
        required.extend(["npm", "npm registry auth token/.npmrc", "registry URL repository_ref"])
        if shutil.which("npm") is not None and has_npm_auth and repository_ref:
            ok, detail = _probe_npm_registry(repository_ref)
            _readiness_check(
                checks,
                "npm_registry_identity",
                ok,
                detail,
                "Ensure npm auth can resolve an identity for the configured registry.",
            )
    ready = all(bool(item["ok"]) for item in checks)
    return {
        "repository_kind": repository_kind.value,
        "repository_ref": repository_ref,
        "ready": ready,
        "checks": checks,
        "required_configuration": required,
    }


def _readiness_check(
    checks: list[dict[str, object]],
    name: str,
    ok: bool,
    detail: str,
    action: str,
) -> None:
    checks.append({"name": name, "ok": ok, "detail": detail, "action": action})


def _probe_command(
    command: tuple[str, ...],
    *,
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    if shutil.which(command[0]) is None:
        return False, f"Executable is not installed: {command[0]}"
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"Readiness probe timed out: {' '.join(command[:2])}"
    if completed.returncode == 0:
        return True, "Readiness probe succeeded."
    output = (completed.stderr or completed.stdout).strip()
    return False, output[:500] or "Readiness probe failed."


def _aws_readiness_command(*args: str) -> tuple[str, ...]:
    command = ["aws", *args]
    settings = get_settings()
    aws_profile = getattr(settings, "r6_publication_aws_profile", None)
    aws_region = getattr(settings, "r6_publication_aws_region", None)
    if aws_profile:
        command.extend(["--profile", aws_profile])
    if aws_region:
        command.extend(["--region", aws_region])
    return tuple(command)


def _probe_npm_registry(repository_ref: str) -> tuple[bool, str]:
    settings = get_settings()
    npmrc_path = getattr(settings, "r6_publication_npmrc_path", None)
    npm_token = getattr(settings, "r6_publication_npm_token", None)
    env = _publication_environment()
    if npmrc_path and npmrc_path.exists():
        env["NPM_CONFIG_USERCONFIG"] = str(npmrc_path)
        return _probe_command(
            ("npm", "whoami", "--registry", repository_ref),
            timeout=20,
            env=env,
        )
    token = (
        npm_token.get_secret_value()
        if npm_token is not None
        else os.environ.get("NPM_TOKEN")
    )
    if not token:
        return False, "npm token is not configured."
    with tempfile.TemporaryDirectory(prefix="uagf-npm-readiness-") as tmp:
        npmrc = Path(tmp) / ".npmrc"
        registry_host = repository_ref.removeprefix("https://").removeprefix("http://").rstrip("/")
        npmrc.write_text(f"//{registry_host}/:_authToken={token}\n", encoding="utf-8")
        env["NPM_CONFIG_USERCONFIG"] = str(npmrc)
        return _probe_command(
            ("npm", "whoami", "--registry", repository_ref),
            timeout=20,
            env=env,
        )


def _publish_to_git_repository(
    *,
    source_root: Path,
    repository_ref: str,
    version_ref: str,
    work_root: Path,
) -> str:
    if shutil.which("git") is None:
        raise HTTPException(status_code=409, detail="Git executable is not installed")
    env = _publication_environment()
    _replace_tree(work_root)
    _run_publication_command(("git", "clone", repository_ref, str(work_root)), cwd=None, env=env)
    _copy_tree_contents(source_root, work_root)
    _run_publication_command(("git", "add", "."), cwd=work_root, env=env)
    status = _run_publication_command(
        ("git", "status", "--porcelain"),
        cwd=work_root,
        allow_failure=False,
        env=env,
    )
    if status.strip():
        _run_publication_command(
            ("git", "config", "user.name", "AI Enterprise Artifact Publisher"),
            cwd=work_root,
            env=env,
        )
        _run_publication_command(
            ("git", "config", "user.email", "artifact-publisher@internal.invalid"),
            cwd=work_root,
            env=env,
        )
        _run_publication_command(
            ("git", "commit", "-m", f"Publish UAGF artifacts {version_ref}"),
            cwd=work_root,
            env=env,
        )
    tag_name = f"uagf-{version_ref[:40]}"
    _run_publication_command(("git", "tag", "-f", tag_name), cwd=work_root, env=env)
    _run_publication_command(("git", "push", "origin", "HEAD"), cwd=work_root, env=env)
    _run_publication_command(
        ("git", "push", "origin", tag_name, "--force"),
        cwd=work_root,
        env=env,
    )
    return repository_ref


def _publish_to_s3_repository(
    *,
    source_root: Path,
    repository_ref: str,
    version_ref: str,
) -> str:
    if not repository_ref.startswith("s3://"):
        raise HTTPException(status_code=422, detail="S3 repository_ref must start with s3://")
    if shutil.which("aws") is None:
        raise HTTPException(status_code=409, detail="AWS CLI is not installed")
    destination = repository_ref.rstrip("/") + "/" + version_ref.strip("/")
    command = ["aws", "s3", "sync", str(source_root), destination, "--only-show-errors"]
    settings = get_settings()
    aws_profile = getattr(settings, "r6_publication_aws_profile", None)
    aws_region = getattr(settings, "r6_publication_aws_region", None)
    if aws_profile:
        command.extend(["--profile", aws_profile])
    if aws_region:
        command.extend(["--region", aws_region])
    _run_publication_command(
        tuple(command),
        cwd=source_root,
        env=_publication_environment(),
    )
    return destination


def _publish_to_package_registry(
    *,
    source_root: Path,
    repository_ref: str,
    version_ref: str,
    work_root: Path,
    build_hash: str,
) -> str:
    if shutil.which("npm") is None:
        raise HTTPException(status_code=409, detail="npm executable is not installed")
    _replace_tree(work_root)
    package_root = work_root / "package"
    package_root.mkdir(parents=True)
    _copy_tree_contents(source_root, package_root / "dist")
    package_name = "ai-enterprise-uagf-artifacts"
    package_json = {
        "name": package_name,
        "version": _npm_version(version_ref),
        "private": False,
        "description": "AI Enterprise UAGF artifact bundle",
        "aiEnterprise": {
            "schema_version": "uagf-package-publication-0.1",
            "build_hash": build_hash,
            "version_ref": version_ref,
        },
        "files": ["dist"],
    }
    (package_root / "package.json").write_text(
        json.dumps(package_json, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    settings = get_settings()
    npmrc_path = getattr(settings, "r6_publication_npmrc_path", None)
    npm_token = getattr(settings, "r6_publication_npm_token", None)
    if npmrc_path and npmrc_path.exists():
        shutil.copyfile(npmrc_path, package_root / ".npmrc")
    elif npm_token is not None or os.environ.get("NPM_TOKEN"):
        registry_host = repository_ref.removeprefix("https://").removeprefix("http://").rstrip("/")
        token = (
            npm_token.get_secret_value()
            if npm_token is not None
            else os.environ["NPM_TOKEN"]
        )
        (package_root / ".npmrc").write_text(
            f"//{registry_host}/:_authToken={token}\n",
            encoding="utf-8",
        )
    _run_publication_command(("npm", "pack", "--json"), cwd=package_root)
    _run_publication_command(
        ("npm", "publish", "--registry", repository_ref, "--access", "restricted"),
        cwd=package_root,
        env=_publication_environment(),
    )
    return f"{repository_ref.rstrip('/')}/{package_name}/{package_json['version']}"


def _replace_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def _copy_tree_contents(source_root: Path, target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(source_root)
        target = (target_root / relative).resolve()
        if target_root.resolve() not in target.parents:
            raise HTTPException(status_code=500, detail="Unsafe publication file target")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())


def _run_publication_command(
    command: tuple[str, ...],
    *,
    cwd: Path | None,
    allow_failure: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=env,
    )
    if completed.returncode != 0 and not allow_failure:
        output = (completed.stderr or completed.stdout).strip()
        raise HTTPException(
            status_code=409,
            detail=f"Artifact repository publication failed: {output[:500]}",
        )
    return completed.stdout


def _publication_environment() -> dict[str, str]:
    env = os.environ.copy()
    settings = get_settings()
    git_ssh_config_path = getattr(settings, "r6_publication_git_ssh_config_path", None)
    aws_profile = getattr(settings, "r6_publication_aws_profile", None)
    aws_region = getattr(settings, "r6_publication_aws_region", None)
    if git_ssh_config_path is not None:
        env["GIT_SSH_COMMAND"] = f"ssh -F {git_ssh_config_path}"
    if aws_profile:
        env["AWS_PROFILE"] = aws_profile
    if aws_region:
        env["AWS_REGION"] = aws_region
    return env


def _npm_version(version_ref: str) -> str:
    candidate = version_ref.strip().lstrip("v")
    if re.match(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$", candidate):
        return candidate
    numeric = re.sub(r"[^0-9]+", ".", candidate).strip(".")
    parts = [part for part in numeric.split(".") if part][:3]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts)


async def _r5_generation_inputs(
    session: object, project_id: uuid.UUID, bundle_row: R5ExportBundleModel
) -> tuple[UmteExportBundle, tuple[UmteGeneratedArtifact, ...]]:
    generated_rows = (
        await session.scalars(
            select(R5GeneratedArtifactModel)
            .where(
                R5GeneratedArtifactModel.project_id == project_id,
                R5GeneratedArtifactModel.generated_hash.in_(
                    [entry["generated_hash"] for entry in bundle_row.bundle_document["entries"]]
                ),
            )
            .order_by(R5GeneratedArtifactModel.artifact_key)
        )
    ).all()
    return UmteExportBundle.model_validate(bundle_row.bundle_document), tuple(
        UmteGeneratedArtifact.model_validate(
            {
                "artifact_key": row.artifact_key,
                "artifact_kind": row.artifact_kind,
                "target": row.target,
                "media_type": row.media_type,
                "source_artifact_spec_hash": row.source_artifact_spec_hash,
                "content_document": row.content_document,
                "generated_hash": row.generated_hash,
            }
        )
        for row in generated_rows
    )


async def _build(
    session: object, project_id: uuid.UUID, build_id: uuid.UUID
) -> R6GenerationBuildModel:
    await _project(session, project_id)
    build = await session.get(R6GenerationBuildModel, build_id)
    if build is None or build.project_id != project_id:
        raise HTTPException(status_code=404, detail="UAGF build not found")
    return build


async def _stored_uagf_files(
    session: object, build: R6GenerationBuildModel
) -> tuple[UagfGeneratedFile, ...]:
    rows = (
        await session.scalars(
            select(R6GeneratedFileModel)
            .where(R6GeneratedFileModel.generation_build_id == build.id)
            .order_by(R6GeneratedFileModel.relative_path)
        )
    ).all()
    root = Path(build.root_path).resolve()
    files: list[UagfGeneratedFile] = []
    for row in rows:
        path = (root / row.relative_path).resolve()
        if root not in path.parents or not path.exists():
            raise HTTPException(status_code=409, detail="Previous UAGF build files are missing")
        files.append(
            UagfGeneratedFile.model_validate(
                {**row.file_document, "content": path.read_text(encoding="utf-8")}
            )
        )
    return tuple(files)


async def _lifecycle_event_rows(
    session: object, build: R6GenerationBuildModel
) -> list[R6LifecycleEventModel]:
    return list(
        (
            await session.scalars(
                select(R6LifecycleEventModel)
                .where(R6LifecycleEventModel.generation_build_id == build.id)
                .order_by(R6LifecycleEventModel.event_id)
            )
        ).all()
    )


def _lifecycle_event_from_row(row: R6LifecycleEventModel) -> UagfLifecycleEvent:
    return UagfLifecycleEvent(
        event_id=row.event_id,
        build_hash=row.build_hash,
        file_id=row.file_id,
        event_type=UagfLifecycleEventType(row.event_type),
        from_status=UagfFileLifecycle(row.from_status),
        to_status=UagfFileLifecycle(row.to_status),
        actor=row.actor,
        reason=row.reason,
        policy_document=row.policy_document,
        event_hash=row.event_hash,
    )


async def _project(session: object, project_id: uuid.UUID) -> ProjectModel:
    project = await session.get(ProjectModel, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _build_root(project_id: uuid.UUID, build_hash: str) -> Path:
    root = (get_settings().artifact_root / "r6" / str(project_id) / build_hash).resolve()
    artifact_root = get_settings().artifact_root.resolve()
    if artifact_root not in root.parents:
        raise HTTPException(status_code=500, detail="Invalid artifact root")
    return root


def _write_build_files(root: Path, files: tuple[UagfGeneratedFile, ...]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for file in files:
        relative_path = Path(file.relative_path)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise HTTPException(status_code=500, detail="Unsafe generated file path")
        target = (root / relative_path).resolve()
        if root not in target.parents:
            raise HTTPException(status_code=500, detail="Unsafe generated file target")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing != file.content:
                raise HTTPException(status_code=409, detail="Generated file content conflict")
            continue
        target.write_text(file.content, encoding="utf-8")
