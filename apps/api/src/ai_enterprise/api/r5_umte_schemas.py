from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class R5TransformationRunRequest(BaseModel):
    target_stack: list[str] = Field(
        default_factory=lambda: ["postgresql", "python", "react"],
        min_length=1,
        max_length=20,
    )
    registry_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")
    template_pack_version: str = Field(default="1.0", pattern=r"^[0-9]+\.[0-9]+$")
    require_approved_snapshot: bool = False


class R5TransformationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source_model_sha256: str
    source_snapshot_id: str
    source_snapshot_sha256: str
    registry_version: str
    template_pack_version: str
    target_stack: list[str]
    status: str
    artifact_count: int
    blocking_finding_count: int
    plan_hash: str
    run_hash: str


class R5ArtifactSpecResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    transformation_run_id: uuid.UUID
    artifact_key: str
    artifact_kind: str
    target: str
    source_object_id: str
    source_object_type: str
    depends_on_object_ids: list[str]
    artifact_document: dict[str, Any]
    provenance_document: dict[str, Any]
    artifact_spec_hash: str


class R5VerificationReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    transformation_run_id: uuid.UUID
    status: str
    finding_count: int
    blocking_finding_count: int
    report_document: dict[str, Any]
    report_hash: str


class R5GeneratedArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    transformation_run_id: uuid.UUID
    artifact_key: str
    artifact_kind: str
    target: str
    media_type: str
    source_artifact_spec_hash: str
    content_document: dict[str, Any]
    generated_hash: str


class R5ExportBundleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    transformation_run_id: uuid.UUID
    artifact_count: int
    source_model_sha256: str
    source_snapshot_id: str
    source_snapshot_sha256: str
    registry_version: str
    template_pack_version: str
    bundle_document: dict[str, Any]
    bundle_hash: str


class R5TransformationResultResponse(BaseModel):
    run: R5TransformationRunResponse
    artifacts: list[R5ArtifactSpecResponse]
    generated_artifacts: list[R5GeneratedArtifactResponse]
    verification: R5VerificationReportResponse
