from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R6GenerationBuildRequest(BaseModel):
    generator_pack_id: str = Field(default="uagf.core", pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_pack_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")


class R6RegenerationPlanRequest(BaseModel):
    generator_pack_id: str = Field(default="uagf.core", pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    generator_pack_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")
    previous_build_id: uuid.UUID | None = None


class R6LifecycleTransitionRequest(BaseModel):
    event_type: str = Field(pattern=r"^(request_review|approve|reject|publish)$")
    reason: str = Field(min_length=1, max_length=500)
    file_id: str | None = Field(default=None, pattern=r"^UAGF-FILE-[0-9]{4}$")
    policy_document: dict[str, Any] = Field(default_factory=dict)


class R6InstallGeneratorPackRequest(BaseModel):
    pack_id: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,119}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+$")


class R6ParallelGenerationPlanRequest(BaseModel):
    max_parallelism: int = Field(default=4, ge=1, le=32)


class R6ValidationGateRunRequest(BaseModel):
    gate_id: str = Field(pattern=r"^[a-z][a-z0-9_.:-]{2,159}$")


class R6ArtifactRepositoryPublicationRequest(BaseModel):
    repository_kind: str = Field(pattern=r"^(filesystem|git|s3|package_registry)$")
    repository_ref: str = Field(min_length=1, max_length=300)
    version_ref: str = Field(min_length=1, max_length=160)


class R6ArtifactRepositoryReadinessResponse(BaseModel):
    repository_kind: str
    repository_ref: str | None
    ready: bool
    checks: list[dict[str, Any]]
    required_configuration: list[str]


class R6GeneratorPackResponse(BaseModel):
    schema_version: str
    pack_id: str
    version: str
    status: str
    technology_stack: list[str]
    supported_targets: list[str]
    validation_gates: list[str]
    repository_kinds: list[str]
    pack_hash: str


class R6InstalledGeneratorPackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    installation_id: str
    pack_id: str
    version: str
    status: str
    technology_stack: list[str]
    supported_targets: list[str]
    validation_gates: list[str]
    repository_kinds: list[str]
    pack_document: dict[str, Any]
    installation_document: dict[str, Any]
    installation_hash: str
    installed_by: str


class R6ParallelGenerationPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    plan_id: str
    generator_pack_id: str
    max_parallelism: int
    lanes_document: dict[str, Any]
    plan_document: dict[str, Any]
    plan_hash: str


class R6ValidationGateRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    gate_run_id: str
    gate_id: str
    command: list[str]
    status: str
    exit_code: int | None
    output_hash: str | None
    gate_document: dict[str, Any]
    gate_hash: str


class R6ArtifactRepositoryPublicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    publication_id: str
    repository_kind: str
    repository_ref: str
    version_ref: str
    file_count: int
    content_address: str
    publication_document: dict[str, Any]
    publication_hash: str


class R6GenerationBuildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    r5_export_bundle_id: uuid.UUID
    r5_export_bundle_hash: str
    status: str
    generator_pack_id: str
    generator_pack_version: str
    artifact_count: int
    file_count: int
    root_path: str
    manifest_document: dict[str, Any]
    manifest_hash: str
    build_hash: str


class R6GeneratedFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    file_id: str
    artifact_key: str
    relative_path: str
    media_type: str
    generator_id: str
    template_ref: str
    lifecycle_status: str
    content_hash: str
    file_hash: str
    file_document: dict[str, Any]


class R6ValidationReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    status: str
    finding_count: int
    blocking_finding_count: int
    report_document: dict[str, Any]
    report_hash: str


class R6RegenerationPlanResponse(BaseModel):
    schema_version: str
    r5_export_bundle_hash: str
    generator_pack_id: str
    generator_pack_version: str
    actions_by_artifact_key: dict[str, str]
    reused_file_ids: list[str]
    regenerated_artifact_keys: list[str]
    preserved_custom_region_count: int
    removed_artifact_keys: list[str]
    plan_hash: str


class R6LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    generation_build_id: uuid.UUID
    event_id: str
    build_hash: str
    file_id: str | None
    event_type: str
    from_status: str
    to_status: str
    actor: str
    reason: str
    policy_document: dict[str, Any]
    event_hash: str


class R6GenerationResultResponse(BaseModel):
    build: R6GenerationBuildResponse
    files: list[R6GeneratedFileResponse]
    validation: R6ValidationReportResponse
