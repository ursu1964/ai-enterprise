import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.enums import (
    ApprovalDecision,
    ProjectStatus,
    RunStatus,
    WorkPackageStatus,
)


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=20_000)
    repository_path: str = Field(min_length=1, max_length=2000)
    repository_url: str | None = Field(default=None, max_length=2000)
    default_branch: str = Field(default="main", min_length=1, max_length=200)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    repository_path: str
    repository_url: str | None
    default_branch: str
    status: ProjectStatus
    manifest_hash: str
    created_at: datetime
    updated_at: datetime


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    crew_name: str
    status: RunStatus
    error_message: str | None
    created_at: datetime


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    run_id: uuid.UUID | None
    artifact_type: str
    media_type: str
    content: str
    content_hash: str
    created_at: datetime


class ApprovalRequest(BaseModel):
    decision: ApprovalDecision
    reviewer: str = Field(min_length=2, max_length=200)
    comment: str | None = Field(default=None, max_length=5_000)


class WorkPackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    planning_run_id: uuid.UUID
    artifact_id: uuid.UUID | None
    status: WorkPackageStatus
    title: str
    objective: str
    base_commit_sha: str
    contract_hash: str
    contract: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class WorkPackageApprovalRequest(BaseModel):
    decision: ApprovalDecision
    reviewer: str = Field(min_length=2, max_length=200)
    comment: str | None = Field(
        default=None,
        max_length=5000,
    )
