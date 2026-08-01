import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.architecture.enums import ArchitectureReviewDecision


class CreateArchitectureRunRequest(BaseModel):
    requirements_artifact_id: uuid.UUID


class CompleteArchitectureRunRequest(BaseModel):
    markdown_content: str = Field(min_length=20, max_length=1_000_000)
    structured_content: dict[str, Any]


class OpenArchitectureReviewRequest(BaseModel):
    reviewer_id: str = Field(min_length=2, max_length=200)


class FindingRequest(BaseModel):
    finding_key: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{2,99}$")
    severity: Literal["info", "low", "medium", "high", "critical"]
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=5, max_length=5000)
    required_change: str | None = Field(default=None, max_length=5000)
    blocking: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)


class CompleteArchitectureReviewRequest(BaseModel):
    decision: ArchitectureReviewDecision
    comments: str = Field(min_length=3, max_length=10_000)
    findings: list[FindingRequest] = Field(default_factory=list, max_length=100)


class CreateArchitectureRevisionRequest(BaseModel):
    revision_instructions: str = Field(min_length=10, max_length=20_000)


class ApproveArchitectureRequest(BaseModel):
    evidence: dict[str, Any] = Field(default_factory=dict)


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class ArchitectureRunResponse(OrmResponse):
    project_id: uuid.UUID
    requirements_artifact_id: uuid.UUID
    status: str
    revision_request_id: uuid.UUID | None
    parent_architecture_artifact_id: uuid.UUID | None
    created_at: datetime


class ArchitectureArtifactResponse(OrmResponse):
    run_id: uuid.UUID
    project_id: uuid.UUID
    version: int
    status: str
    checksum: str
    markdown_content: str
    structured_content: dict[str, Any]
    parent_artifact_id: uuid.UUID | None
    created_at: datetime


class ArchitectureReviewResponse(OrmResponse):
    architecture_artifact_id: uuid.UUID
    review_round: int
    status: str
    reviewer_id: str
    decision: str | None
    reviewed_checksum: str
    completed_at: datetime | None


class ArchitectureApprovalResponse(OrmResponse):
    architecture_artifact_id: uuid.UUID
    approving_review_id: uuid.UUID
    approved_by: str
    approved_checksum: str
    architecture_version: int
    evidence_checksum: str
    approved_at: datetime


class ArchitectureLineageResponse(BaseModel):
    artifact: ArchitectureArtifactResponse
    ancestors: list[ArchitectureArtifactResponse]


class WorkPackageGateResponse(BaseModel):
    eligible: bool
    architecture_artifact_id: uuid.UUID
    architecture_approval_id: uuid.UUID
    checksum: str
    version: int
