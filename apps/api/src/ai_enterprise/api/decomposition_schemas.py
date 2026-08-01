import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StartDecompositionRequest(BaseModel):
    architecture_artifact_id: uuid.UUID
    repository_uri: str = Field(min_length=1, max_length=2000)
    base_commit_sha: str = Field(pattern=r"^[0-9a-f]{40,64}$")


class ReviewDecompositionRequest(BaseModel):
    decision: Literal["approved", "changes_requested", "rejected"]
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    comments: str | None = Field(default=None, max_length=10000)


class RevisionDecompositionRequest(BaseModel):
    artifact_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    comments: str = Field(min_length=3, max_length=10000)


class RunResponse(OrmModel):
    id: uuid.UUID
    project_id: uuid.UUID
    architecture_artifact_id: uuid.UUID
    repository_snapshot_id: uuid.UUID
    repository_index_id: uuid.UUID
    status: str
    policy_version: str
    parent_decomposition_run_id: uuid.UUID | None
    parent_artifact_id: uuid.UUID | None
    created_at: datetime


class ArtifactResponse(OrmModel):
    id: uuid.UUID
    decomposition_run_id: uuid.UUID
    project_id: uuid.UUID
    artifact_document: dict[str, Any]
    artifact_hash: str
    graph_hash: str
    validation_status: str
    status: str


class ReviewResponse(OrmModel):
    id: uuid.UUID
    decomposition_artifact_id: uuid.UUID
    reviewer_id: str
    decision: str
    artifact_hash: str
    comments: str | None


class FindingResponse(OrmModel):
    validator_code: str
    severity: str
    package_key: str | None
    path: str | None
    message: str
    evidence: dict[str, Any]


class WorkPackageResponse(OrmModel):
    id: uuid.UUID
    package_key: str
    sequence_number: int
    title: str
    objective: str
    status: str
    package_document: dict[str, Any]
    package_hash: str
