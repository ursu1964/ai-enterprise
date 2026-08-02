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
from ai_enterprise.domain.execution.enums import ExecutionStatus, TestStatus


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=20, max_length=20_000)
    repository_path: str = Field(min_length=1, max_length=2000)
    repository_url: str | None = Field(default=None, max_length=2000)
    default_branch: str = Field(default="main", min_length=1, max_length=200)
    project_type: str | None = Field(default=None, min_length=1, max_length=120)
    manifest: dict[str, Any] | None = None


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


class RequestExecutionRequest(BaseModel):
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[a-zA-Z0-9._:-]+$",
    )


class ExecutionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    work_package_id: uuid.UUID
    approval_id: uuid.UUID
    status: ExecutionStatus
    base_commit: str
    container_image: str
    container_image_digest: str | None
    failure_code: str | None
    failure_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    timeout_seconds: int
    cpu_limit: float
    memory_limit_bytes: int
    pids_limit: int
    network_disabled: bool
    runtime_policy: dict[str, Any]
    changed_files: list[str] | None
    changed_file_count: int | None
    insertions: int | None
    deletions: int | None
    patch_artifact_id: uuid.UUID | None
    log_artifact_id: uuid.UUID | None
    patch_sha256: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class ExecutionTestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    execution_run_id: uuid.UUID
    sequence: int
    command: list[str]
    exit_code: int | None
    status: TestStatus
    duration_ms: int | None
    stdout_artifact_id: uuid.UUID | None
    stderr_artifact_id: uuid.UUID | None


class ExecutionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    execution_run_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime


class CreatePatchReviewRequest(BaseModel):
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[a-zA-Z0-9._:-]+$",
    )


class PatchReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    work_package_id: uuid.UUID
    execution_run_id: uuid.UUID
    status: str
    base_commit: str
    expected_patch_sha256: str
    actual_patch_sha256: str | None
    decision_summary: str | None
    review_report_artifact_id: uuid.UUID | None
    failure_code: str | None
    failure_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class PatchReviewFindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patch_review_run_id: uuid.UUID
    rule_id: str
    category: str
    severity: str
    status: str
    title: str
    description: str
    file_path: str | None
    line_start: int | None
    line_end: int | None
    evidence: dict[str, Any] | None
    blocking: bool
    created_at: datetime


class PatchReviewCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patch_review_run_id: uuid.UUID
    sequence: int
    check_type: str
    name: str
    command: list[str] | None
    status: str
    exit_code: int | None
    duration_ms: int | None
    stdout_artifact_id: uuid.UUID | None
    stderr_artifact_id: uuid.UUID | None


class PatchReviewEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patch_review_run_id: uuid.UUID
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime
