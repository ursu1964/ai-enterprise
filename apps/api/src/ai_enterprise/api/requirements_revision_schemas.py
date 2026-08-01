import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.requirements_revision.models import RequirementsReviewFinding


class RequestRequirementsChanges(BaseModel):
    reviewer: str = Field(min_length=2, max_length=200)
    summary: str = Field(min_length=3, max_length=4000)
    findings: tuple[RequirementsReviewFinding, ...] = Field(min_length=1, max_length=100)


class RequirementsRevisionCycleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requirements_run_id: uuid.UUID
    revision_request_id: uuid.UUID
    cycle_number: int
    status: str
    resulting_artifact_id: uuid.UUID | None
    completed_at: datetime | None
    created_at: datetime


class RequirementsArtifactLineageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    artifact_id: uuid.UUID
    revision_cycle_id: uuid.UUID | None
    previous_artifact_id: uuid.UUID | None
    version: int
    revision_feedback_hash: str | None
    created_at: datetime
