from __future__ import annotations

import ast
import json
import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.r5_umte import (
    UmteExportBundle,
    UmteGeneratedArtifact,
)
from ai_enterprise.domain.specification.kernel import canonical_json, specification_hash


class UagfValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class UagfBuildStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"


class UagfFileLifecycle(StrEnum):
    GENERATED = "generated"
    VERIFIED = "verified"
    REVIEW_REQUESTED = "review_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class UagfRegenerationAction(StrEnum):
    REUSE = "reuse"
    REGENERATE = "regenerate"
    PRESERVE_CUSTOM = "preserve_custom"
    REMOVE = "remove"


class UagfLifecycleEventType(StrEnum):
    REQUEST_REVIEW = "request_review"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"


class UagfGeneratorPackStatus(StrEnum):
    CERTIFIED = "certified"
    INSTALLED = "installed"
    DEPRECATED = "deprecated"


class UagfValidationGateStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class UagfArtifactRepositoryKind(StrEnum):
    FILESYSTEM = "filesystem"
    GIT = "git"
    S3 = "s3"
    PACKAGE_REGISTRY = "package_registry"


class UagfGeneratorPackDefinition(UagfValue):
    schema_version: Literal["uagf-generator-pack-0.1"] = "uagf-generator-pack-0.1"
    pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    status: UagfGeneratorPackStatus
    technology_stack: tuple[str, ...]
    supported_targets: tuple[str, ...]
    validation_gates: tuple[str, ...]
    repository_kinds: tuple[UagfArtifactRepositoryKind, ...]
    pack_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_pack(self) -> UagfGeneratorPackDefinition:
        if tuple(sorted(set(self.technology_stack))) != self.technology_stack:
            raise ValueError("UAGF generator pack technologies must be unique and sorted")
        if tuple(sorted(set(self.supported_targets))) != self.supported_targets:
            raise ValueError("UAGF generator pack targets must be unique and sorted")
        if tuple(sorted(set(self.validation_gates))) != self.validation_gates:
            raise ValueError("UAGF generator pack validation gates must be unique and sorted")
        if self.pack_hash != _generator_pack_hash(self):
            raise ValueError("UAGF generator pack hash does not match canonical content")
        return self


class UagfInstalledGeneratorPack(UagfValue):
    schema_version: Literal["uagf-installed-generator-pack-0.1"] = (
        "uagf-installed-generator-pack-0.1"
    )
    installation_id: str = Field(pattern=r"^UAGF-PACK-[0-9]{4}$")
    project_id: str = Field(min_length=1)
    pack: UagfGeneratorPackDefinition
    installed_by: str = Field(min_length=1, max_length=200)
    installation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_installation(self) -> UagfInstalledGeneratorPack:
        if self.installation_hash != _installed_generator_pack_hash(self):
            raise ValueError("UAGF installed generator pack hash does not match canonical content")
        return self


class UagfParallelGenerationPlan(UagfValue):
    schema_version: Literal["uagf-parallel-generation-plan-0.1"] = (
        "uagf-parallel-generation-plan-0.1"
    )
    plan_id: str = Field(pattern=r"^UAGF-PAR-[0-9]{4}$")
    build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    lanes: dict[str, tuple[str, ...]]
    max_parallelism: int = Field(ge=1, le=32)
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_parallel_plan(self) -> UagfParallelGenerationPlan:
        normalized = {key: tuple(sorted(set(value))) for key, value in sorted(self.lanes.items())}
        if self.lanes != normalized:
            raise ValueError("UAGF parallel lanes must be sorted and unique")
        if self.plan_hash != _parallel_generation_plan_hash(self):
            raise ValueError("UAGF parallel generation plan hash does not match canonical content")
        return self


class UagfValidationGateRun(UagfValue):
    schema_version: Literal["uagf-validation-gate-run-0.1"] = "uagf-validation-gate-run-0.1"
    gate_run_id: str = Field(pattern=r"^UAGF-GATE-[0-9]{4}$")
    build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")
    command: tuple[str, ...]
    status: UagfValidationGateStatus
    exit_code: int | None = None
    output_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    gate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_gate(self) -> UagfValidationGateRun:
        if not self.command:
            raise ValueError("UAGF validation gate command must not be empty")
        if self.gate_hash != _validation_gate_run_hash(self):
            raise ValueError("UAGF validation gate hash does not match canonical content")
        return self


class UagfArtifactRepositoryPublication(UagfValue):
    schema_version: Literal["uagf-artifact-repository-publication-0.1"] = (
        "uagf-artifact-repository-publication-0.1"
    )
    publication_id: str = Field(pattern=r"^UAGF-REPO-[0-9]{4}$")
    build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    repository_kind: UagfArtifactRepositoryKind
    repository_ref: str = Field(min_length=1, max_length=300)
    version_ref: str = Field(min_length=1, max_length=160)
    file_count: int = Field(ge=1)
    content_address: str = Field(pattern=r"^[0-9a-f]{64}$")
    publication_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_publication(self) -> UagfArtifactRepositoryPublication:
        if self.publication_hash != _artifact_repository_publication_hash(self):
            raise ValueError("UAGF artifact publication hash does not match canonical content")
        return self


class UagfGeneratedFile(UagfValue):
    file_id: str = Field(pattern=r"^UAGF-FILE-[0-9]{4}$")
    artifact_key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,179}$")
    relative_path: str = Field(pattern=r"^[a-z0-9][a-z0-9_./-]{1,240}$")
    media_type: str = Field(min_length=1, max_length=120)
    generator_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    template_ref: str = Field(pattern=r"^uagf\.[a-z0-9_.-]+\.v[0-9]+\.[0-9]+$")
    source_generated_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_artifact_spec_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    lifecycle_status: UagfFileLifecycle
    content: str = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_file(self) -> UagfGeneratedFile:
        if self.relative_path.startswith("/") or "/../" in f"/{self.relative_path}/":
            raise ValueError("UAGF generated file path must be repository-relative and safe")
        if self.content_hash != _content_hash(self.content):
            raise ValueError("UAGF generated file content hash does not match content")
        if self.file_hash != _file_hash(self):
            raise ValueError("UAGF generated file hash does not match canonical content")
        return self


class UagfLifecycleEvent(UagfValue):
    schema_version: Literal["uagf-lifecycle-event-0.1"] = "uagf-lifecycle-event-0.1"
    event_id: str = Field(pattern=r"^UAGF-LIFE-[0-9]{4}$")
    build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_id: str | None = Field(default=None, pattern=r"^UAGF-FILE-[0-9]{4}$")
    event_type: UagfLifecycleEventType
    from_status: UagfFileLifecycle
    to_status: UagfFileLifecycle
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=500)
    policy_document: dict[str, object]
    event_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_event(self) -> UagfLifecycleEvent:
        if self.to_status != _next_lifecycle_status(self.from_status, self.event_type):
            raise ValueError("UAGF lifecycle event does not match allowed transition")
        if self.event_hash != _lifecycle_event_hash(self):
            raise ValueError("UAGF lifecycle event hash does not match canonical content")
        return self


class UagfRegenerationPlan(UagfValue):
    schema_version: Literal["uagf-regeneration-plan-0.1"] = "uagf-regeneration-plan-0.1"
    r5_export_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    actions_by_artifact_key: dict[str, UagfRegenerationAction]
    reused_file_ids: tuple[str, ...] = ()
    regenerated_artifact_keys: tuple[str, ...] = ()
    preserved_custom_region_count: int = Field(ge=0)
    removed_artifact_keys: tuple[str, ...] = ()
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_plan(self) -> UagfRegenerationPlan:
        if tuple(sorted(set(self.reused_file_ids))) != self.reused_file_ids:
            raise ValueError("UAGF reused file identifiers must be unique and sorted")
        if tuple(sorted(set(self.regenerated_artifact_keys))) != self.regenerated_artifact_keys:
            raise ValueError("UAGF regenerated artifact keys must be unique and sorted")
        if tuple(sorted(set(self.removed_artifact_keys))) != self.removed_artifact_keys:
            raise ValueError("UAGF removed artifact keys must be unique and sorted")
        if self.plan_hash != _regeneration_plan_hash(self):
            raise ValueError("UAGF regeneration plan hash does not match canonical content")
        return self


class UagfValidationFinding(UagfValue):
    finding_id: str = Field(pattern=r"^UAGF-FIND-[0-9]{3}$")
    rule_id: str = Field(pattern=r"^UAGF\.VERIFY\.[A-Z0-9_.]+$")
    severity: Literal["error", "warning", "information"]
    message: str = Field(min_length=1)
    file_ids: tuple[str, ...] = ()
    blocking: bool
    suggested_action: str = Field(min_length=1)


class UagfValidationReport(UagfValue):
    schema_version: Literal["uagf-validation-report-0.1"] = "uagf-validation-report-0.1"
    r5_export_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    file_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: UagfBuildStatus
    findings: tuple[UagfValidationFinding, ...]
    report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> UagfValidationReport:
        expected = (
            UagfBuildStatus.FAILED
            if any(finding.blocking for finding in self.findings)
            else UagfBuildStatus.VERIFIED
        )
        if self.status is not expected:
            raise ValueError("UAGF validation status must match blocking findings")
        if self.report_hash != _validation_report_hash(self):
            raise ValueError("UAGF validation report hash does not match canonical content")
        return self


class UagfBuildManifest(UagfValue):
    schema_version: Literal["uagf-build-manifest-0.1"] = "uagf-build-manifest-0.1"
    r5_export_bundle_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_snapshot_id: str = Field(pattern=r"^SNP-[0-9]{4}$")
    source_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator_pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_pack_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")
    artifact_count: int = Field(ge=1)
    file_count: int = Field(ge=1)
    file_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_manifest(self) -> UagfBuildManifest:
        if self.manifest_hash != _manifest_hash(self):
            raise ValueError("UAGF build manifest hash does not match canonical content")
        return self


class UagfGenerationResult(UagfValue):
    schema_version: Literal["uagf-generation-result-0.1"] = "uagf-generation-result-0.1"
    manifest: UagfBuildManifest
    files: tuple[UagfGeneratedFile, ...]
    validation_report: UagfValidationReport
    build_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result(self) -> UagfGenerationResult:
        paths = [file.relative_path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("UAGF generated file paths must be unique")
        if tuple(sorted(paths)) != tuple(paths):
            raise ValueError("UAGF generated files must be sorted by path")
        if self.manifest.file_set_hash != _file_set_hash(self.files):
            raise ValueError("UAGF manifest does not match generated files")
        if self.validation_report.file_set_hash != self.manifest.file_set_hash:
            raise ValueError("UAGF validation report does not match generated files")
        if self.manifest.validation_report_hash != self.validation_report.report_hash:
            raise ValueError("UAGF manifest does not match validation report")
        if self.build_hash != _build_hash(self):
            raise ValueError("UAGF build hash does not match canonical content")
        return self


def generate_uagf_build(
    export_bundle: UmteExportBundle,
    generated_artifacts: tuple[UmteGeneratedArtifact, ...],
    *,
    generator_pack_id: str = "uagf.core",
    generator_pack_version: str = "1.0",
    previous_files: tuple[UagfGeneratedFile, ...] = (),
) -> UagfGenerationResult:
    _require_supported_generator_pack(generator_pack_id, generator_pack_version)
    bundle_entries = {entry.artifact_key: entry for entry in export_bundle.entries}
    artifacts = {artifact.artifact_key: artifact for artifact in generated_artifacts}
    if set(bundle_entries) != set(artifacts):
        raise ValueError("UAGF input artifacts do not match R5 export bundle")
    previous_by_artifact_key = {file.artifact_key: file for file in previous_files}
    files = tuple(
        sorted(
            (
                _render_file(
                    index,
                    export_bundle,
                    artifacts[key],
                    generator_pack_id,
                    generator_pack_version,
                    previous_by_artifact_key.get(key),
                )
                for index, key in enumerate(sorted(artifacts), start=1)
            ),
            key=lambda file: file.relative_path,
        )
    )
    validation = validate_uagf_files(export_bundle, files, generated_artifacts=generated_artifacts)
    file_set_hash = _file_set_hash(files)
    provisional_manifest = UagfBuildManifest.model_construct(
        schema_version="uagf-build-manifest-0.1",
        r5_export_bundle_hash=export_bundle.bundle_hash,
        source_model_sha256=export_bundle.source_model_sha256,
        source_snapshot_id=export_bundle.source_snapshot_id,
        source_snapshot_sha256=export_bundle.source_snapshot_sha256,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        artifact_count=export_bundle.artifact_count,
        file_count=len(files),
        file_set_hash=file_set_hash,
        validation_report_hash=validation.report_hash,
        manifest_hash="0" * 64,
    )
    manifest = UagfBuildManifest(
        r5_export_bundle_hash=export_bundle.bundle_hash,
        source_model_sha256=export_bundle.source_model_sha256,
        source_snapshot_id=export_bundle.source_snapshot_id,
        source_snapshot_sha256=export_bundle.source_snapshot_sha256,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        artifact_count=export_bundle.artifact_count,
        file_count=len(files),
        file_set_hash=file_set_hash,
        validation_report_hash=validation.report_hash,
        manifest_hash=_manifest_hash(provisional_manifest),
    )
    provisional = UagfGenerationResult.model_construct(
        schema_version="uagf-generation-result-0.1",
        manifest=manifest,
        files=files,
        validation_report=validation,
        build_hash="0" * 64,
    )
    return UagfGenerationResult(
        manifest=manifest,
        files=files,
        validation_report=validation,
        build_hash=_build_hash(provisional),
    )


def plan_uagf_regeneration(
    export_bundle: UmteExportBundle,
    generated_artifacts: tuple[UmteGeneratedArtifact, ...],
    previous_files: tuple[UagfGeneratedFile, ...],
    *,
    generator_pack_id: str = "uagf.core",
    generator_pack_version: str = "1.0",
) -> UagfRegenerationPlan:
    _require_supported_generator_pack(generator_pack_id, generator_pack_version)
    artifacts = {artifact.artifact_key: artifact for artifact in generated_artifacts}
    previous = {file.artifact_key: file for file in previous_files}
    actions: dict[str, UagfRegenerationAction] = {}
    reused_file_ids: list[str] = []
    regenerated_keys: list[str] = []
    preserved_count = 0
    for key, artifact in sorted(artifacts.items()):
        template_ref = (
            f"uagf.{artifact.artifact_kind.value}."
            f"{artifact.target}.v{generator_pack_version}"
        )
        previous_file = previous.get(key)
        if (
            previous_file is not None
            and previous_file.source_generated_hash == artifact.generated_hash
            and previous_file.template_ref == template_ref
            and previous_file.generator_version == generator_pack_version
        ):
            actions[key] = UagfRegenerationAction.REUSE
            reused_file_ids.append(previous_file.file_id)
            continue
        generated_content = _render_content(
            export_bundle,
            artifact,
            f"uagf.{artifact.target}",
            template_ref,
        )
        custom_region_count = (
            _count_preserved_custom_regions(generated_content, previous_file.content)
            if previous_file is not None
            else 0
        )
        if custom_region_count:
            actions[key] = UagfRegenerationAction.PRESERVE_CUSTOM
            preserved_count += custom_region_count
        else:
            actions[key] = UagfRegenerationAction.REGENERATE
        regenerated_keys.append(key)
    removed_keys = tuple(sorted(set(previous) - set(artifacts)))
    for key in removed_keys:
        actions[key] = UagfRegenerationAction.REMOVE
    provisional = UagfRegenerationPlan.model_construct(
        schema_version="uagf-regeneration-plan-0.1",
        r5_export_bundle_hash=export_bundle.bundle_hash,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        actions_by_artifact_key=actions,
        reused_file_ids=tuple(sorted(set(reused_file_ids))),
        regenerated_artifact_keys=tuple(sorted(set(regenerated_keys))),
        preserved_custom_region_count=preserved_count,
        removed_artifact_keys=removed_keys,
        plan_hash="0" * 64,
    )
    return UagfRegenerationPlan(
        r5_export_bundle_hash=export_bundle.bundle_hash,
        generator_pack_id=generator_pack_id,
        generator_pack_version=generator_pack_version,
        actions_by_artifact_key=actions,
        reused_file_ids=tuple(sorted(set(reused_file_ids))),
        regenerated_artifact_keys=tuple(sorted(set(regenerated_keys))),
        preserved_custom_region_count=preserved_count,
        removed_artifact_keys=removed_keys,
        plan_hash=_regeneration_plan_hash(provisional),
    )


def certified_uagf_generator_packs() -> tuple[UagfGeneratorPackDefinition, ...]:
    definitions = (
        {
            "pack_id": "uagf.core",
            "version": "1.0",
            "technology_stack": (
                "alembic",
                "json",
                "openapi",
                "postgresql",
                "prometheus",
                "prompt",
                "pytest",
                "python",
                "react",
                "yaml",
            ),
            "supported_targets": (
                "alembic",
                "json",
                "openapi",
                "postgresql",
                "prometheus",
                "prompt",
                "pytest",
                "python",
                "react",
                "yaml",
            ),
            "validation_gates": ("python.ast", "json.schema", "kubernetes.manifest"),
            "repository_kinds": (UagfArtifactRepositoryKind.FILESYSTEM,),
        },
        {
            "pack_id": "uagf.react-nestjs-kubernetes",
            "version": "1.0",
            "technology_stack": ("kubernetes", "nestjs", "react", "terraform", "typescript"),
            "supported_targets": ("json", "openapi", "react", "yaml"),
            "validation_gates": ("docker.build", "npm.test", "terraform.validate"),
            "repository_kinds": (
                UagfArtifactRepositoryKind.FILESYSTEM,
                UagfArtifactRepositoryKind.GIT,
                UagfArtifactRepositoryKind.PACKAGE_REGISTRY,
            ),
        },
        {
            "pack_id": "uagf.spring-terraform",
            "version": "1.0",
            "technology_stack": ("java", "kubernetes", "spring", "terraform"),
            "supported_targets": ("json", "openapi", "yaml"),
            "validation_gates": ("docker.build", "maven.test", "terraform.validate"),
            "repository_kinds": (
                UagfArtifactRepositoryKind.FILESYSTEM,
                UagfArtifactRepositoryKind.GIT,
                UagfArtifactRepositoryKind.S3,
            ),
        },
    )
    return tuple(
        _generator_pack_definition(
            pack_id=str(item["pack_id"]),
            version=str(item["version"]),
            technology_stack=tuple(item["technology_stack"]),
            supported_targets=tuple(item["supported_targets"]),
            validation_gates=tuple(item["validation_gates"]),
            repository_kinds=tuple(item["repository_kinds"]),
        )
        for item in definitions
    )


def install_uagf_generator_pack(
    *,
    index: int,
    project_id: str,
    pack_id: str,
    version: str,
    installed_by: str,
) -> UagfInstalledGeneratorPack:
    pack = _find_generator_pack(pack_id, version)
    provisional = UagfInstalledGeneratorPack.model_construct(
        schema_version="uagf-installed-generator-pack-0.1",
        installation_id=f"UAGF-PACK-{index:04d}",
        project_id=project_id,
        pack=pack,
        installed_by=installed_by,
        installation_hash="0" * 64,
    )
    return UagfInstalledGeneratorPack(
        installation_id=f"UAGF-PACK-{index:04d}",
        project_id=project_id,
        pack=pack,
        installed_by=installed_by,
        installation_hash=_installed_generator_pack_hash(provisional),
    )


def plan_parallel_uagf_generation(
    *,
    index: int,
    build: UagfGenerationResult,
    max_parallelism: int = 4,
) -> UagfParallelGenerationPlan:
    lanes: dict[str, tuple[str, ...]] = {}
    for file in build.files:
        lanes.setdefault(file.generator_id, ())
        lanes[file.generator_id] = (*lanes[file.generator_id], file.file_id)
    normalized = {key: tuple(sorted(set(value))) for key, value in sorted(lanes.items())}
    provisional = UagfParallelGenerationPlan.model_construct(
        schema_version="uagf-parallel-generation-plan-0.1",
        plan_id=f"UAGF-PAR-{index:04d}",
        build_hash=build.build_hash,
        generator_pack_id=build.manifest.generator_pack_id,
        lanes=normalized,
        max_parallelism=max_parallelism,
        plan_hash="0" * 64,
    )
    return UagfParallelGenerationPlan(
        plan_id=f"UAGF-PAR-{index:04d}",
        build_hash=build.build_hash,
        generator_pack_id=build.manifest.generator_pack_id,
        lanes=normalized,
        max_parallelism=max_parallelism,
        plan_hash=_parallel_generation_plan_hash(provisional),
    )


def uagf_validation_gate_run(
    *,
    index: int,
    build_hash: str,
    gate_id: str,
    command: tuple[str, ...],
    status: UagfValidationGateStatus,
    exit_code: int | None = None,
    output: str | None = None,
) -> UagfValidationGateRun:
    output_hash = specification_hash({"output": output}) if output is not None else None
    provisional = UagfValidationGateRun.model_construct(
        schema_version="uagf-validation-gate-run-0.1",
        gate_run_id=f"UAGF-GATE-{index:04d}",
        build_hash=build_hash,
        gate_id=gate_id,
        command=command,
        status=status,
        exit_code=exit_code,
        output_hash=output_hash,
        gate_hash="0" * 64,
    )
    return UagfValidationGateRun(
        gate_run_id=f"UAGF-GATE-{index:04d}",
        build_hash=build_hash,
        gate_id=gate_id,
        command=command,
        status=status,
        exit_code=exit_code,
        output_hash=output_hash,
        gate_hash=_validation_gate_run_hash(provisional),
    )


def publish_uagf_artifacts_to_repository(
    *,
    index: int,
    build: UagfGenerationResult,
    repository_kind: UagfArtifactRepositoryKind,
    repository_ref: str,
    version_ref: str,
) -> UagfArtifactRepositoryPublication:
    content_address = _file_set_hash(build.files)
    provisional = UagfArtifactRepositoryPublication.model_construct(
        schema_version="uagf-artifact-repository-publication-0.1",
        publication_id=f"UAGF-REPO-{index:04d}",
        build_hash=build.build_hash,
        repository_kind=repository_kind,
        repository_ref=repository_ref,
        version_ref=version_ref,
        file_count=len(build.files),
        content_address=content_address,
        publication_hash="0" * 64,
    )
    return UagfArtifactRepositoryPublication(
        publication_id=f"UAGF-REPO-{index:04d}",
        build_hash=build.build_hash,
        repository_kind=repository_kind,
        repository_ref=repository_ref,
        version_ref=version_ref,
        file_count=len(build.files),
        content_address=content_address,
        publication_hash=_artifact_repository_publication_hash(provisional),
    )


def transition_uagf_lifecycle(
    *,
    index: int,
    build_hash: str,
    current_status: UagfFileLifecycle,
    event_type: UagfLifecycleEventType,
    actor: str,
    reason: str,
    file_id: str | None = None,
    policy_document: dict[str, object] | None = None,
) -> UagfLifecycleEvent:
    to_status = _next_lifecycle_status(current_status, event_type)
    policy = {
        "schema_version": "uagf-lifecycle-policy-0.1",
        "requires_human_actor": True,
        "requires_verified_build": event_type is UagfLifecycleEventType.REQUEST_REVIEW,
        "requires_approval_before_publish": event_type is UagfLifecycleEventType.PUBLISH,
    } | (policy_document or {})
    provisional = UagfLifecycleEvent.model_construct(
        schema_version="uagf-lifecycle-event-0.1",
        event_id=f"UAGF-LIFE-{index:04d}",
        build_hash=build_hash,
        file_id=file_id,
        event_type=event_type,
        from_status=current_status,
        to_status=to_status,
        actor=actor,
        reason=reason,
        policy_document=policy,
        event_hash="0" * 64,
    )
    return UagfLifecycleEvent(
        event_id=f"UAGF-LIFE-{index:04d}",
        build_hash=build_hash,
        file_id=file_id,
        event_type=event_type,
        from_status=current_status,
        to_status=to_status,
        actor=actor,
        reason=reason,
        policy_document=policy,
        event_hash=_lifecycle_event_hash(provisional),
    )


def current_uagf_lifecycle_status(
    events: tuple[UagfLifecycleEvent, ...],
    *,
    initial_status: UagfFileLifecycle = UagfFileLifecycle.VERIFIED,
) -> UagfFileLifecycle:
    status = initial_status
    for event in sorted(events, key=lambda item: item.event_id):
        if event.from_status is not status:
            raise ValueError("UAGF lifecycle event chain is not contiguous")
        status = event.to_status
    return status


def validate_uagf_files(
    export_bundle: UmteExportBundle,
    files: tuple[UagfGeneratedFile, ...],
    *,
    generated_artifacts: tuple[UmteGeneratedArtifact, ...] = (),
) -> UagfValidationReport:
    findings: list[UagfValidationFinding] = []
    entries = {entry.artifact_key: entry for entry in export_bundle.entries}
    artifacts = {artifact.artifact_key: artifact for artifact in generated_artifacts}
    file_keys = {file.artifact_key for file in files}
    missing = tuple(sorted(set(entries) - file_keys))
    if missing:
        findings.append(
            _finding(
                len(findings) + 1,
                "UAGF.VERIFY.COVERAGE.BUNDLE_ENTRIES",
                "error",
                "Every R5 export bundle entry must produce a generated file.",
                (),
                True,
                "Render each exported R5 artifact into a managed generated file.",
            )
        )
    for file in files:
        entry = entries.get(file.artifact_key)
        if entry is None:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.REGISTRY.KNOWN_ARTIFACT",
                    "error",
                    "Generated file is not backed by an R5 export bundle entry.",
                    (file.file_id,),
                    True,
                    "Generate files only from the R5 export bundle.",
                )
            )
            continue
        if file.source_generated_hash != entry.generated_hash:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.TRACEABILITY.GENERATED_HASH",
                    "error",
                    "Generated file source hash does not match the R5 generated artifact.",
                    (file.file_id,),
                    True,
                    "Regenerate the file from the matching R5 artifact payload.",
                )
            )
        if file.source_artifact_spec_hash != entry.source_artifact_spec_hash:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.TRACEABILITY.SPEC_HASH",
                    "error",
                    "Generated file source specification hash does not match the R5 bundle.",
                    (file.file_id,),
                    True,
                    "Regenerate the file from the matching R5 artifact specification.",
                )
            )
        if file.media_type != entry.media_type:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.CONSISTENCY.MEDIA_TYPE",
                    "error",
                    "Generated file media type does not match the R5 bundle target.",
                    (file.file_id,),
                    True,
                    "Use the media type selected by UMTE for this artifact target.",
                )
            )
        expected_path_prefix = f"generated/{entry.target}/"
        if not file.relative_path.startswith(expected_path_prefix):
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.CONSISTENCY.TARGET_PATH",
                    "error",
                    "Generated file path does not match the R5 target technology.",
                    (file.file_id,),
                    True,
                    "Place generated files under the target-specific generated folder.",
                )
            )
        if f".{entry.target}.v" not in file.template_ref:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.CONSISTENCY.TEMPLATE_TARGET",
                    "error",
                    "Generated file template reference does not match the R5 target.",
                    (file.file_id,),
                    True,
                    "Resolve templates from the target selected by UMTE.",
                )
            )
        if "AI-Enterprise-Generated" not in file.content:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.METADATA.EMBEDDED",
                    "error",
                    "Generated file is missing embedded generation metadata.",
                    (file.file_id,),
                    True,
                    "Embed generation metadata in every generated file.",
                )
            )
        if export_bundle.bundle_hash not in file.content:
            findings.append(
                _finding(
                    len(findings) + 1,
                    "UAGF.VERIFY.TRACEABILITY.EMBEDDED_BUNDLE_HASH",
                    "error",
                    "Generated file content does not embed the R5 export bundle hash.",
                    (file.file_id,),
                    True,
                    "Embed R5 export bundle hashes in generated metadata.",
                )
            )
        syntax_finding = _syntax_validation_finding(file, len(findings) + 1)
        if syntax_finding is not None:
            findings.append(syntax_finding)
    if artifacts:
        findings.extend(_artifact_consistency_findings(export_bundle, artifacts, len(findings)))
    file_set_hash = _file_set_hash(files)
    provisional = UagfValidationReport.model_construct(
        schema_version="uagf-validation-report-0.1",
        r5_export_bundle_hash=export_bundle.bundle_hash,
        file_set_hash=file_set_hash,
        status=(
            UagfBuildStatus.FAILED
            if any(finding.blocking for finding in findings)
            else UagfBuildStatus.VERIFIED
        ),
        findings=tuple(findings),
        report_hash="0" * 64,
    )
    return UagfValidationReport(
        r5_export_bundle_hash=export_bundle.bundle_hash,
        file_set_hash=file_set_hash,
        status=provisional.status,
        findings=tuple(findings),
        report_hash=_validation_report_hash(provisional),
    )


def _artifact_consistency_findings(
    export_bundle: UmteExportBundle,
    artifacts: dict[str, UmteGeneratedArtifact],
    finding_offset: int,
) -> list[UagfValidationFinding]:
    findings: list[UagfValidationFinding] = []
    entry_keys = {entry.artifact_key for entry in export_bundle.entries}
    missing_artifacts = tuple(sorted(entry_keys - set(artifacts)))
    if missing_artifacts:
        findings.append(
            _finding(
                finding_offset + len(findings) + 1,
                "UAGF.VERIFY.COVERAGE.GENERATED_ARTIFACTS",
                "error",
                "R6 consistency validation requires every R5 artifact payload.",
                (),
                True,
                (
                    "Load all R5 generated artifact payloads before validating "
                    "cross-artifact consistency."
                ),
            )
        )
    source_ids = {
        source_id
        for artifact in artifacts.values()
        if (source_id := _artifact_source_object_id(artifact)) is not None
    }
    dependencies_by_source: dict[str, tuple[str, ...]] = {}
    for artifact in artifacts.values():
        source_id = _artifact_source_object_id(artifact)
        dependencies = _artifact_dependencies(artifact)
        if source_id is None:
            findings.append(
                _finding(
                    finding_offset + len(findings) + 1,
                    "UAGF.VERIFY.TRACEABILITY.SOURCE_OBJECT",
                    "error",
                    "Generated artifact payload is missing source object traceability.",
                    (),
                    True,
                    "Preserve source_object_id in every UMTE generated artifact payload.",
                )
            )
            continue
        existing = dependencies_by_source.setdefault(source_id, dependencies)
        if existing != dependencies:
            findings.append(
                _finding(
                    finding_offset + len(findings) + 1,
                    "UAGF.VERIFY.CONSISTENCY.SOURCE_DEPENDENCIES",
                    "error",
                    "Artifacts for the same source object expose inconsistent dependencies.",
                    (),
                    True,
                    "Regenerate all artifact families from one UMTE transformation result.",
                )
            )
        unknown_dependencies = tuple(dep for dep in dependencies if dep not in source_ids)
        if unknown_dependencies:
            findings.append(
                _finding(
                    finding_offset + len(findings) + 1,
                    "UAGF.VERIFY.CONSISTENCY.DEPENDENCY_COVERAGE",
                    "error",
                    "Generated artifact dependencies are not covered by generated source objects.",
                    (),
                    True,
                    "Generate dependent artifacts together or remove stale dependency references.",
                )
            )
    return findings


def _syntax_validation_finding(
    file: UagfGeneratedFile, finding_index: int
) -> UagfValidationFinding | None:
    try:
        _validate_target_syntax(file)
    except ValueError as exc:
        return _finding(
            finding_index,
            "UAGF.VERIFY.SYNTAX.TARGET",
            "error",
            str(exc),
            (file.file_id,),
            True,
            "Regenerate the artifact with the target-specific renderer.",
        )
    return None


def _validate_target_syntax(file: UagfGeneratedFile) -> None:
    target = file.relative_path.split("/", maxsplit=2)[1] if "/" in file.relative_path else ""
    if target in {"json", "openapi", "prometheus", "prompt", "react"}:
        document = _parse_json_content(file.content)
        _validate_json_target_shape(target, document)
        return
    if target in {"python", "pytest", "alembic"}:
        try:
            ast.parse(file.content)
        except SyntaxError as exc:
            raise ValueError("Generated Python artifact is not syntactically valid.") from exc
        if target == "pytest" and "def test_generated_" not in file.content:
            raise ValueError("Generated pytest artifact must define a generated test function.")
        if target == "alembic" and "def upgrade() -> None:" not in file.content:
            raise ValueError("Generated Alembic artifact must define upgrade().")
        return
    if target == "postgresql":
        if "CREATE TABLE IF NOT EXISTS generated_" not in file.content:
            raise ValueError("Generated PostgreSQL artifact must create a generated table.")
        if "payload JSONB NOT NULL" not in file.content:
            raise ValueError("Generated PostgreSQL artifact must include JSONB payload storage.")
        return
    if target == "yaml":
        _validate_yaml_deployment(file.content)


def _parse_json_content(content: str) -> dict[str, object]:
    try:
        document = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Generated JSON artifact is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise ValueError("Generated JSON artifact must be a JSON object.")
    return document


def _validate_json_target_shape(target: str, document: dict[str, object]) -> None:
    if target == "openapi":
        if document.get("openapi") != "3.1.0" or not isinstance(document.get("paths"), dict):
            raise ValueError("Generated OpenAPI artifact must be an OpenAPI 3.1 document.")
        return
    if target == "react":
        if not document.get("component") or not isinstance(document.get("props"), list):
            raise ValueError("Generated React artifact must define component and props.")
        return
    if target == "prometheus":
        groups = document.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError("Generated Prometheus artifact must define rule groups.")
        return
    if target == "prompt":
        if not document.get("prompt_id") or not document.get("system"):
            raise ValueError("Generated prompt artifact must define prompt_id and system.")
        return
    if target == "json" and document.get("schema_version") != "uagf-json-contract-0.1":
        raise ValueError("Generated JSON contract must declare the UAGF schema version.")


def _validate_yaml_deployment(content: str) -> None:
    required_lines = (
        "apiVersion: apps/v1",
        "kind: Deployment",
        "metadata:",
        "spec:",
        "containers:",
    )
    if not all(line in content for line in required_lines):
        raise ValueError("Generated YAML artifact must define a Kubernetes deployment.")


def _artifact_body(artifact: UmteGeneratedArtifact) -> dict[str, object]:
    body = artifact.content_document.get("body", {})
    return body if isinstance(body, dict) else {}


def _artifact_source_object_id(artifact: UmteGeneratedArtifact) -> str | None:
    source_id = _artifact_body(artifact).get("source_object_id")
    return str(source_id) if source_id else None


def _artifact_dependencies(artifact: UmteGeneratedArtifact) -> tuple[str, ...]:
    dependencies = _artifact_body(artifact).get("dependencies", [])
    if not isinstance(dependencies, list):
        return ()
    return tuple(sorted(str(item) for item in dependencies))


def _next_lifecycle_status(
    current_status: UagfFileLifecycle, event_type: UagfLifecycleEventType
) -> UagfFileLifecycle:
    transitions = {
        (UagfFileLifecycle.VERIFIED, UagfLifecycleEventType.REQUEST_REVIEW): (
            UagfFileLifecycle.REVIEW_REQUESTED
        ),
        (UagfFileLifecycle.REVIEW_REQUESTED, UagfLifecycleEventType.APPROVE): (
            UagfFileLifecycle.APPROVED
        ),
        (UagfFileLifecycle.REVIEW_REQUESTED, UagfLifecycleEventType.REJECT): (
            UagfFileLifecycle.REJECTED
        ),
        (UagfFileLifecycle.REJECTED, UagfLifecycleEventType.REQUEST_REVIEW): (
            UagfFileLifecycle.REVIEW_REQUESTED
        ),
        (UagfFileLifecycle.APPROVED, UagfLifecycleEventType.PUBLISH): (
            UagfFileLifecycle.PUBLISHED
        ),
    }
    try:
        return transitions[(current_status, event_type)]
    except KeyError as exc:
        raise ValueError("UAGF lifecycle transition is not allowed") from exc


def _render_file(
    index: int,
    export_bundle: UmteExportBundle,
    artifact: UmteGeneratedArtifact,
    generator_pack_id: str,
    generator_pack_version: str,
    previous_file: UagfGeneratedFile | None = None,
) -> UagfGeneratedFile:
    extension = _extension(artifact.target)
    relative_path = f"generated/{artifact.target}/{artifact.artifact_key}.{extension}"
    generator_id = f"uagf.{artifact.target}"
    template_ref = (
        f"uagf.{artifact.artifact_kind.value}."
        f"{artifact.target}.v{generator_pack_version}"
    )
    rendered_content = _render_content(export_bundle, artifact, generator_id, template_ref)
    content = _regenerated_content(rendered_content, artifact, template_ref, previous_file)
    provisional = UagfGeneratedFile.model_construct(
        file_id=f"UAGF-FILE-{index:04d}",
        artifact_key=artifact.artifact_key,
        relative_path=relative_path,
        media_type=artifact.media_type,
        generator_id=generator_id,
        generator_version=generator_pack_version,
        template_ref=template_ref,
        source_generated_hash=artifact.generated_hash,
        source_artifact_spec_hash=artifact.source_artifact_spec_hash,
        lifecycle_status=UagfFileLifecycle.VERIFIED,
        content=content,
        content_hash=_content_hash(content),
        file_hash="0" * 64,
    )
    return UagfGeneratedFile(
        file_id=f"UAGF-FILE-{index:04d}",
        artifact_key=artifact.artifact_key,
        relative_path=relative_path,
        media_type=artifact.media_type,
        generator_id=generator_id,
        generator_version=generator_pack_version,
        template_ref=template_ref,
        source_generated_hash=artifact.generated_hash,
        source_artifact_spec_hash=artifact.source_artifact_spec_hash,
        lifecycle_status=UagfFileLifecycle.VERIFIED,
        content=content,
        content_hash=_content_hash(content),
        file_hash=_file_hash(provisional),
    )


def _regenerated_content(
    rendered_content: str,
    artifact: UmteGeneratedArtifact,
    template_ref: str,
    previous_file: UagfGeneratedFile | None,
) -> str:
    if previous_file is None:
        return rendered_content
    if (
        previous_file.source_generated_hash == artifact.generated_hash
        and previous_file.template_ref == template_ref
        and previous_file.generator_version == template_ref.rsplit(".v", maxsplit=1)[-1]
    ):
        return previous_file.content
    return preserve_uagf_custom_regions(rendered_content, previous_file.content)


def _render_content(
    export_bundle: UmteExportBundle,
    artifact: UmteGeneratedArtifact,
    generator_id: str,
    template_ref: str,
) -> str:
    metadata = {
        "AI-Enterprise-Generated": True,
        "schema_version": "uagf-file-metadata-0.1",
        "r5_export_bundle_hash": export_bundle.bundle_hash,
        "artifact_key": artifact.artifact_key,
        "artifact_kind": artifact.artifact_kind.value,
        "source_generated_hash": artifact.generated_hash,
        "source_artifact_spec_hash": artifact.source_artifact_spec_hash,
        "generator": generator_id,
        "template_ref": template_ref,
    }
    payload = artifact.content_document
    body = payload.get("body", {})
    if artifact.target == "openapi":
        return canonical_json(_openapi_document(metadata, artifact, body)) + "\n"
    if artifact.target == "react":
        return canonical_json(_react_component_spec(metadata, artifact, body)) + "\n"
    if artifact.target == "prometheus":
        return canonical_json(_prometheus_rules(metadata, artifact, body)) + "\n"
    if artifact.target == "prompt":
        return canonical_json(_ai_prompt_document(metadata, artifact, body)) + "\n"
    if artifact.target == "json":
        return canonical_json(_json_contract(metadata, artifact, body)) + "\n"
    if artifact.target in {"python", "pytest"}:
        return _python_module(metadata, artifact, body, is_test=artifact.target == "pytest")
    if artifact.target == "postgresql":
        return _postgresql_sql(metadata, artifact, body)
    if artifact.target == "alembic":
        return _alembic_migration_spec(metadata, artifact, body)
    if artifact.target == "yaml":
        return _yaml_deployment(metadata, artifact, body)
    return (
        "---\n"
        + "AI-Enterprise-Generated: true\n"
        + f"artifact_key: {artifact.artifact_key}\n"
        + f"r5_export_bundle_hash: {export_bundle.bundle_hash}\n"
        + "---\n\n"
        + json.dumps(payload, sort_keys=True, indent=2)
        + "\n"
    )


_CUSTOM_REGION_PATTERN = re.compile(
    r"(?P<open>^[^\n]*<AI-ENTERPRISE-CUSTOM-REGION name=\"(?P<name>[A-Za-z0-9_.-]+)\">[^\n]*\n)"
    r"(?P<body>.*?)"
    r"(?P<close>^[^\n]*</AI-ENTERPRISE-CUSTOM-REGION>[^\n]*(?:\n|$))",
    re.MULTILINE | re.DOTALL,
)


def preserve_uagf_custom_regions(generated_content: str, previous_content: str) -> str:
    previous_regions = {
        match.group("name"): match.group("body")
        for match in _CUSTOM_REGION_PATTERN.finditer(previous_content)
    }
    if not previous_regions:
        return generated_content

    def replace(match: re.Match[str]) -> str:
        preserved = previous_regions.get(match.group("name"))
        if preserved is None:
            return match.group(0)
        return match.group("open") + preserved + match.group("close")

    return _CUSTOM_REGION_PATTERN.sub(replace, generated_content)


def _count_preserved_custom_regions(generated_content: str, previous_content: str) -> int:
    previous_names = {
        match.group("name") for match in _CUSTOM_REGION_PATTERN.finditer(previous_content)
    }
    generated_names = {
        match.group("name") for match in _CUSTOM_REGION_PATTERN.finditer(generated_content)
    }
    return len(previous_names & generated_names)


def _generator_pack_definition(
    *,
    pack_id: str,
    version: str,
    technology_stack: tuple[str, ...],
    supported_targets: tuple[str, ...],
    validation_gates: tuple[str, ...],
    repository_kinds: tuple[UagfArtifactRepositoryKind, ...],
) -> UagfGeneratorPackDefinition:
    stack = tuple(sorted(set(technology_stack)))
    targets = tuple(sorted(set(supported_targets)))
    gates = tuple(sorted(set(validation_gates)))
    repos = tuple(sorted(set(repository_kinds), key=lambda item: item.value))
    provisional = UagfGeneratorPackDefinition.model_construct(
        schema_version="uagf-generator-pack-0.1",
        pack_id=pack_id,
        version=version,
        status=UagfGeneratorPackStatus.CERTIFIED,
        technology_stack=stack,
        supported_targets=targets,
        validation_gates=gates,
        repository_kinds=repos,
        pack_hash="0" * 64,
    )
    return UagfGeneratorPackDefinition(
        pack_id=pack_id,
        version=version,
        status=UagfGeneratorPackStatus.CERTIFIED,
        technology_stack=stack,
        supported_targets=targets,
        validation_gates=gates,
        repository_kinds=repos,
        pack_hash=_generator_pack_hash(provisional),
    )


def _find_generator_pack(pack_id: str, version: str) -> UagfGeneratorPackDefinition:
    for pack in certified_uagf_generator_packs():
        if pack.pack_id == pack_id and pack.version == version:
            return pack
    raise ValueError("UAGF generator pack is not certified")


def _require_supported_generator_pack(pack_id: str, version: str) -> None:
    _find_generator_pack(pack_id, version)


def _source_name(body: object) -> str:
    if isinstance(body, dict):
        source = body.get("source_object_id") or body.get("title") or "artifact"
        return str(source).lower().replace("-", "_").replace(".", "_")
    return "artifact"


def _title(body: object, artifact: UmteGeneratedArtifact) -> str:
    if isinstance(body, dict) and body.get("title"):
        return str(body["title"])
    return artifact.artifact_key


def _operations(body: object) -> list[str]:
    if isinstance(body, dict) and isinstance(body.get("operations"), list):
        return [str(item) for item in body["operations"]]
    return []


def _dependencies(body: object) -> list[str]:
    if isinstance(body, dict) and isinstance(body.get("dependencies"), list):
        return [str(item) for item in body["dependencies"]]
    return []


def _openapi_document(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> dict[str, object]:
    name = _source_name(body)
    path = f"/generated/{name}"
    return {
        "openapi": "3.1.0",
        "info": {
            "title": _title(body, artifact),
            "version": "1.0.0",
            "x-ai-enterprise-generated": metadata,
        },
        "paths": {
            path: {
                "get": {
                    "operationId": f"get_{name}",
                    "summary": f"Read {_title(body, artifact)}",
                    "responses": {"200": {"description": "Generated response contract"}},
                },
                "post": {
                    "operationId": f"create_{name}",
                    "summary": f"Create {_title(body, artifact)}",
                    "responses": {"201": {"description": "Generated creation contract"}},
                },
            }
        },
        "x-ai-enterprise-traceability": metadata,
    }


def _react_component_spec(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> dict[str, object]:
    name = _source_name(body)
    return {
        "AI-Enterprise-Generated": True,
        "component": f"{''.join(part.title() for part in name.split('_'))}View",
        "artifact_key": artifact.artifact_key,
        "metadata": metadata,
        "props": [{"name": "model", "type": "Record<string, unknown>", "required": True}],
        "states": ["loading", "ready", "error"],
        "actions": _operations(body),
        "accessibility": {"landmark": "main", "keyboard_navigation": True},
    }


def _prometheus_rules(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> dict[str, object]:
    name = _source_name(body)
    return {
        "AI-Enterprise-Generated": True,
        "groups": [
            {
                "name": f"{name}.generated.rules",
                "rules": [
                    {
                        "alert": f"{name.title().replace('_', '')}GenerationDrift",
                        "expr": (
                            "uagf_artifact_hash_mismatch"
                            f'{{artifact_key="{artifact.artifact_key}"}} > 0'
                        ),
                        "for": "5m",
                        "labels": {"severity": "warning"},
                        "annotations": {"summary": "Generated artifact hash drift detected."},
                    }
                ],
            }
        ],
        "metadata": metadata,
    }


def _ai_prompt_document(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> dict[str, object]:
    return {
        "AI-Enterprise-Generated": True,
        "prompt_id": f"prompt.{artifact.artifact_key}",
        "system": "Transform only the supplied generated artifact. Do not invent business intent.",
        "task": f"Work on {_title(body, artifact)} using the attached traceability metadata.",
        "constraints": [
            "Preserve artifact identifiers.",
            "Preserve source hashes.",
            "Do not add hidden dependencies.",
        ],
        "metadata": metadata,
    }


def _json_contract(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> dict[str, object]:
    return {
        "AI-Enterprise-Generated": True,
        "schema_version": "uagf-json-contract-0.1",
        "artifact_key": artifact.artifact_key,
        "metadata": metadata,
        "operations": _operations(body),
        "dependencies": _dependencies(body),
    }


def _python_module(
    metadata: dict[str, object],
    artifact: UmteGeneratedArtifact,
    body: object,
    *,
    is_test: bool,
) -> str:
    name = _source_name(body)
    if is_test:
        return (
            '"""AI-Enterprise-Generated\n'
            + json.dumps(metadata, sort_keys=True)
            + '\n"""\n\n'
            + f"def test_generated_{name}_contract() -> None:\n"
            + f"    assert {artifact.artifact_key!r}\n"
            + f"    assert {artifact.generated_hash!r}\n"
            + "\n# <AI-ENTERPRISE-CUSTOM-REGION name=\"custom_tests\">\n"
            + "# Downstream test extensions may be added here.\n"
            + "# </AI-ENTERPRISE-CUSTOM-REGION>\n"
        )
    class_name = "".join(part.title() for part in name.split("_")) or "GeneratedArtifact"
    return (
        '"""AI-Enterprise-Generated\n'
        + json.dumps(metadata, sort_keys=True)
        + '\n"""\n\n'
        + "from dataclasses import dataclass\n\n\n"
        + "@dataclass(frozen=True)\n"
        + f"class {class_name}GeneratedService:\n"
        + f"    artifact_key: str = {artifact.artifact_key!r}\n"
        + f"    generated_hash: str = {artifact.generated_hash!r}\n\n"
        + "    def operations(self) -> tuple[str, ...]:\n"
        + f"        return {tuple(_operations(body))!r}\n"
        + "\n# <AI-ENTERPRISE-CUSTOM-REGION name=\"custom_logic\">\n"
        + "# Custom extension code may be added here by downstream tools.\n"
        + "# </AI-ENTERPRISE-CUSTOM-REGION>\n"
    )


def _postgresql_sql(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> str:
    name = _source_name(body)
    return (
        "-- AI-Enterprise-Generated\n"
        + "-- "
        + json.dumps(metadata, sort_keys=True)
        + "\n"
        + f"CREATE TABLE IF NOT EXISTS generated_{name} (\n"
        + "    id UUID PRIMARY KEY,\n"
        + "    artifact_key TEXT NOT NULL,\n"
        + "    payload JSONB NOT NULL,\n"
        + "    created_at TIMESTAMPTZ NOT NULL DEFAULT now()\n"
        + ");\n"
        + f"COMMENT ON TABLE generated_{name} IS "
        + f"'Generated from {artifact.artifact_key}';\n"
    )


def _alembic_migration_spec(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> str:
    return (
        "# AI-Enterprise-Generated\n"
        + "# "
        + json.dumps(metadata, sort_keys=True)
        + "\n"
        + "revision = None\n"
        + "down_revision = None\n\n"
        + "def upgrade() -> None:\n"
        + f"    # Apply generated migration for {artifact.artifact_key}.\n"
        + "    pass\n\n"
        + "def downgrade() -> None:\n"
        + "    pass\n"
        + "\n# <AI-ENTERPRISE-CUSTOM-REGION name=\"migration_extensions\">\n"
        + "# </AI-ENTERPRISE-CUSTOM-REGION>\n"
    )


def _yaml_deployment(
    metadata: dict[str, object], artifact: UmteGeneratedArtifact, body: object
) -> str:
    name = _source_name(body)
    return (
        "# AI-Enterprise-Generated\n"
        + "# "
        + json.dumps(metadata, sort_keys=True)
        + "\n"
        + "apiVersion: apps/v1\n"
        + "kind: Deployment\n"
        + "metadata:\n"
        + f"  name: generated-{name}\n"
        + "  labels:\n"
        + "    app.kubernetes.io/managed-by: ai-enterprise\n"
        + "spec:\n"
        + "  replicas: 1\n"
        + "  selector:\n"
        + "    matchLabels:\n"
        + f"      app: generated-{name}\n"
        + "  template:\n"
        + "    metadata:\n"
        + "      labels:\n"
        + f"        app: generated-{name}\n"
        + "    spec:\n"
        + "      containers:\n"
        + f"        - name: generated-{name}\n"
        + "          image: example.invalid/ai-enterprise/generated:latest\n"
    )


def _extension(target: str) -> str:
    return {
        "alembic": "py",
        "json": "json",
        "markdown": "md",
        "openapi": "json",
        "postgresql": "sql",
        "prometheus": "json",
        "prompt": "json",
        "pytest": "py",
        "python": "py",
        "react": "json",
        "yaml": "yaml",
    }.get(target, "json")


def _finding(
    index: int,
    rule_id: str,
    severity: Literal["error", "warning", "information"],
    message: str,
    file_ids: tuple[str, ...],
    blocking: bool,
    suggested_action: str,
) -> UagfValidationFinding:
    return UagfValidationFinding(
        finding_id=f"UAGF-FIND-{index:03d}",
        rule_id=rule_id,
        severity=severity,
        message=message,
        file_ids=tuple(sorted(set(file_ids))),
        blocking=blocking,
        suggested_action=suggested_action,
    )


def _content_hash(content: str) -> str:
    return specification_hash({"content": content})


def _file_hash(file: UagfGeneratedFile) -> str:
    return specification_hash(file.model_dump(mode="json", exclude={"file_hash"}))


def _file_set_hash(files: tuple[UagfGeneratedFile, ...]) -> str:
    return specification_hash([file.model_dump(mode="json") for file in files])


def _regeneration_plan_hash(plan: UagfRegenerationPlan) -> str:
    return specification_hash(plan.model_dump(mode="json", exclude={"plan_hash"}))


def _lifecycle_event_hash(event: UagfLifecycleEvent) -> str:
    return specification_hash(event.model_dump(mode="json", exclude={"event_hash"}))


def _generator_pack_hash(pack: UagfGeneratorPackDefinition) -> str:
    return specification_hash(pack.model_dump(mode="json", exclude={"pack_hash"}))


def _installed_generator_pack_hash(pack: UagfInstalledGeneratorPack) -> str:
    return specification_hash(pack.model_dump(mode="json", exclude={"installation_hash"}))


def _parallel_generation_plan_hash(plan: UagfParallelGenerationPlan) -> str:
    return specification_hash(plan.model_dump(mode="json", exclude={"plan_hash"}))


def _validation_gate_run_hash(run: UagfValidationGateRun) -> str:
    return specification_hash(run.model_dump(mode="json", exclude={"gate_hash"}))


def _artifact_repository_publication_hash(
    publication: UagfArtifactRepositoryPublication,
) -> str:
    return specification_hash(
        publication.model_dump(mode="json", exclude={"publication_hash"})
    )


def _validation_report_hash(report: UagfValidationReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_hash"}))


def _manifest_hash(manifest: UagfBuildManifest) -> str:
    return specification_hash(manifest.model_dump(mode="json", exclude={"manifest_hash"}))


def _build_hash(result: UagfGenerationResult) -> str:
    return specification_hash(result.model_dump(mode="json", exclude={"build_hash"}))
