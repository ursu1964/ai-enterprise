import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExtractedCandidate(BaseModel):
    candidate_type: str
    title: str = Field(min_length=5, max_length=200)
    statement: str = Field(min_length=10, max_length=4000)
    scope_type: str
    scope_id: uuid.UUID
    evidence_locators: list[dict[str, Any]] = Field(min_length=1)
    confidence_band: str
    classification: str


class ExtractKnowledgeRequest(BaseModel):
    source_id: uuid.UUID
    source_hash: str = Field(min_length=64, max_length=64)
    runtime_session_id: uuid.UUID
    extraction_skill_version_id: uuid.UUID
    candidates: list[ExtractedCandidate] = Field(max_length=10)


class ReviewCandidateRequest(BaseModel):
    decision: str
    reviewer_id: uuid.UUID
    candidate_hash: str
    policy_version: str
    comments: str | None = None
    review_scope: str = "project"
    knowledge_key: str | None = None


class SupersedeRequest(BaseModel):
    superseding_item_id: uuid.UUID
    reason: str


class WithdrawRequest(BaseModel):
    reason: str


class ResolveContradictionRequest(BaseModel):
    resolution: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class RetrieveKnowledgeRequest(BaseModel):
    runtime_session_id: uuid.UUID
    actor_id: uuid.UUID
    assignment_id: uuid.UUID
    query_text: str = Field(min_length=1, max_length=2000)
    project_id: uuid.UUID | None = None
    organization_id: uuid.UUID
    requested_item_types: list[str] = Field(default_factory=list)
    maximum_classification: str = "internal"
    maximum_results: int = Field(default=10, ge=1, le=50)
    include_stale: bool = False
    include_disputed: bool = False


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class SourceResponse(OrmResponse):
    source_type: str
    source_id: uuid.UUID
    source_hash: str
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    classification: str
    trust_level: str


class CandidateResponse(OrmResponse):
    candidate_type: str
    title: str
    statement: str
    scope_type: str
    scope_id: uuid.UUID
    classification: str
    status: str
    candidate_hash: str


class ItemResponse(OrmResponse):
    knowledge_key: str
    version_number: int
    item_type: str
    title: str
    statement: str
    scope_type: str
    scope_id: uuid.UUID
    classification: str
    trust_level: str
    temporal_status: str
    valid_from: datetime
    valid_until: datetime | None
    evidence_manifest_hash: str
    knowledge_hash: str
