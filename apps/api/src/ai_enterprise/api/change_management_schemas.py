from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ai_enterprise.application.change_management.dto import (
    EntityReferenceInput,
    EvidenceReferenceInput,
)


class ChangeProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    title: str
    description: str
    category: str
    proposed_by: str
    sponsor_id: str
    problem_statement: str
    desired_outcome: str
    risk: str
    status: str
    affected_entities: tuple[EntityReferenceInput, ...]
    evidence: tuple[EvidenceReferenceInput, ...]
    created_at: datetime
    content_hash: str


class ChangeSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    proposal_id: UUID
    version: int
    operations: tuple[dict[str, Any], ...]
    created_by: str
    created_at: datetime
    content_hash: str


class ImpactAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    proposal_id: UUID
    change_set_id: UUID
    version: int
    assessed_by: str
    findings: tuple[dict[str, Any], ...]
    required_approval_roles: tuple[str, ...]
    required_tests: tuple[str, ...]
    estimated_blast_radius: str
    rollback_complexity: str
    confidence: float
    has_unknown_impact: bool
    created_at: datetime
    content_hash: str


class ValidationPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    proposal_id: UUID
    impact_assessment_id: UUID
    version: int
    requirements: tuple[dict[str, Any], ...]
    rollback_evidence_required: bool
    created_by: str
    created_at: datetime
    content_hash: str


class ChangeDecisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    proposal_id: UUID
    decision: str
    decided_by: str
    actor_roles: tuple[str, ...]
    reason: str
    decided_at: datetime
    content_hash: str


class ChangeTimelineResponse(BaseModel):
    proposal_id: UUID
    records: list[dict[str, Any]]
