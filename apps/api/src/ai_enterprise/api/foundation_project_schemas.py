from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class FoundationManifestImportRequest(BaseModel):
    manifest: dict[str, Any] | None = None
    manifest_text: str | None = Field(default=None, min_length=2, max_length=200_000)
    content_type: Literal["application/json", "application/yaml", "text/yaml"] = (
        "application/json"
    )


class FoundationImportResponse(BaseModel):
    project_id: uuid.UUID
    status: str
    review_state: str
    validation_report: dict[str, Any]
    canonical_model_sha256: str
    canonical_object_count: int
    relationship_count: int
    snapshot_id: str
    snapshot_status: str
    source_manifest_sha256: str
    traceability: dict[str, Any]


class FoundationProjectStateResponse(BaseModel):
    project_id: uuid.UUID
    project_name: str
    status: str
    latest_model_sha256: str | None = None
    latest_snapshot_id: str | None = None
    latest_snapshot_status: str | None = None


class FoundationObjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=4000)
    lifecycle_status: str | None = Field(default=None, max_length=30)
    truth_status: str | None = Field(default=None, max_length=30)
    approval_status: str | None = Field(default=None, max_length=30)
    attributes: dict[str, Any] | None = None
    reason: str = Field(default="R3 foundation object update", min_length=1, max_length=2000)


class FoundationFindingResolutionRequest(BaseModel):
    resolution: Literal["acknowledged", "resolved", "accepted_risk", "rejected"]
    resolution_note: str | None = Field(default=None, max_length=2000)


class FoundationSnapshotRequest(BaseModel):
    status: Literal["draft", "approved"] = "draft"


class FoundationSnapshotResponse(BaseModel):
    project_id: uuid.UUID
    snapshot_id: str
    status: str
    snapshot_sha256: str
    source_model_sha256: str
    object_count: int
    relationship_count: int
    reconstructed_model: dict[str, Any] | None = None
