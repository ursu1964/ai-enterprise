from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCollectRequest(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID | None = None
    workflow_type: str = Field(min_length=1, max_length=60)
    workflow_id: uuid.UUID
    evidence_type: str = Field(min_length=1, max_length=60)
    evidence_document: dict[str, Any]
    source_audit_event_id: uuid.UUID
    observed_at: datetime
    agent_profile_id: uuid.UUID | None = None
    crew_id: uuid.UUID | None = None
    assignment_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None
    prompt_version: str | None = Field(default=None, max_length=80)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    workflow_type: str
    workflow_id: uuid.UUID
    evidence_type: str
    agent_profile_id: uuid.UUID | None
    crew_id: uuid.UUID | None
    assignment_id: uuid.UUID | None
    prompt_version: str | None
    observed_at: datetime
    evidence_document: dict[str, Any]
    evidence_hash: str
    source_audit_event_id: uuid.UUID


class MetricDeriveRequest(BaseModel):
    organization_id: uuid.UUID
    scope_type: str = Field(min_length=1, max_length=40)
    scope_id: uuid.UUID
    metric_key: str = Field(min_length=1, max_length=80)
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    evidence_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    window_days: int = Field(gt=0, le=3660)
    policy_version: str = Field(min_length=1, max_length=40)


class MetricResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    metric_key: str
    numerator: int
    denominator: int
    metric_value: Decimal
    window_days: int
    evidence_ids: list[str]
    evidence_set_hash: str
    policy_version: str
    calculated_at: datetime


class RecommendationRequest(BaseModel):
    organization_id: uuid.UUID
    agent_profile_id: uuid.UUID
    capability_key: str = Field(min_length=1, max_length=120)
    recommended_level: str = Field(min_length=1, max_length=30)
    evidence_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    policy_version: str = Field(min_length=1, max_length=40)
    assessment: dict[str, Any]


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_profile_id: uuid.UUID
    capability_key: str
    recommended_level: str
    status: str
    recommendation_document: dict[str, Any]
    recommendation_hash: str
    evidence_ids: list[str]
    evidence_set_hash: str
    policy_version: str
    created_at: datetime


class CertificationDecisionRequest(BaseModel):
    recommendation_hash: str = Field(min_length=64, max_length=64)
    decision: str
    rationale: str = Field(min_length=1)
    validity_days: int = Field(gt=0, le=1825)


class CertificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    agent_profile_id: uuid.UUID
    capability_key: str
    level: str
    version: int
    status: str
    recommendation_id: uuid.UUID
    decision_id: uuid.UUID
    evidence_set_hash: str
    granted_by: str
    granted_at: datetime
    expires_at: datetime
    supersedes_id: uuid.UUID | None


class LearningProposalRequest(BaseModel):
    organization_id: uuid.UUID
    project_id: uuid.UUID | None = None
    proposal_type: str = Field(min_length=1, max_length=60)
    observation: str = Field(min_length=1, max_length=20_000)
    recommendation: str = Field(min_length=1, max_length=20_000)
    target_reference: str = Field(min_length=1, max_length=200)
    evidence_ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)


class LearningReviewRequest(BaseModel):
    decision: str
    rationale: str = Field(min_length=1)


class LearningProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    proposal_type: str
    observation: str
    recommendation: str
    target_reference: str
    status: str
    proposal_document: dict[str, Any]
    proposal_hash: str
    evidence_ids: list[str]
    evidence_set_hash: str
    proposed_by: str
    reviewed_by: str | None
    review_rationale: str | None
    created_at: datetime
    reviewed_at: datetime | None
