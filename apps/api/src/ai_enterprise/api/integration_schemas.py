import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RevisionAttemptRequest(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=128, pattern=r"^[a-zA-Z0-9._:-]+$")


class RevisionAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    parent_execution_run_id: uuid.UUID | None
    root_execution_run_id: uuid.UUID | None
    lineage_depth: int
    status: str


class IntegrationEligibilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    execution_run_id: uuid.UUID
    eligible: bool
    patch_sha256: str
    base_commit_sha: str
    base_tree_sha: str
    accepted_review_id: uuid.UUID | None
    evaluated_at: datetime
    failure_reasons: list[dict[str, Any]]


class IntegrationApprovalRequest(BaseModel):
    target_branch: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._/-]+$")
    reason: str = Field(min_length=3, max_length=5000)


class IntegrationApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    execution_run_id: uuid.UUID
    target_branch: str
    approved_patch_sha256: str
    approved_base_commit_sha: str
    approved_base_tree_sha: str
    decision: str
    approver_subject: str
    approver_role: str


class IntegrationAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    execution_run_id: uuid.UUID
    integration_approval_id: uuid.UUID
    status: str
    target_branch: str
    expected_patch_sha256: str
    expected_base_commit_sha: str
    expected_base_tree_sha: str
    actual_base_commit_sha: str | None
    actual_base_tree_sha: str | None
    resulting_tree_sha: str | None
    failure_code: str | None
    failure_message: str | None
    correlation_id: uuid.UUID
