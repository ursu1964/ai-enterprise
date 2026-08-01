from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ai_enterprise.domain.change_management.enums import (
    ChangeCategory,
    ChangeDecisionType,
    ChangeOutcomeDisposition,
    ChangeRisk,
    ImpactKnowledge,
)


class EntityReferenceInput(BaseModel):
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: UUID
    entity_version: str | None = Field(default=None, max_length=100)


class EvidenceReferenceInput(BaseModel):
    artifact_id: UUID
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_type: str = Field(min_length=1, max_length=100)


class CreateChangeProposal(BaseModel):
    organization_id: UUID
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=10_000)
    category: ChangeCategory
    sponsor_id: str = Field(min_length=1, max_length=200)
    problem_statement: str = Field(min_length=3, max_length=10_000)
    desired_outcome: str = Field(min_length=3, max_length=10_000)
    risk: ChangeRisk
    affected_entities: tuple[EntityReferenceInput, ...]
    evidence: tuple[EvidenceReferenceInput, ...]


class ChangeOperationInput(BaseModel):
    operation_type: str = Field(min_length=1, max_length=100)
    target: EntityReferenceInput
    before_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    description: str = Field(min_length=3, max_length=5000)


class CreateChangeSet(BaseModel):
    operations: tuple[ChangeOperationInput, ...] = Field(min_length=1)


class CreateTransformationPlan(BaseModel):
    change_set_id: UUID
    strategy: str = Field(min_length=3, max_length=5000)
    steps: tuple[str, ...] = Field(min_length=1)
    prerequisites: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[EvidenceReferenceInput, ...] = Field(min_length=1)


class ImpactFindingInput(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    dimension: str = Field(min_length=1, max_length=100)
    knowledge: ImpactKnowledge
    severity: ChangeRisk
    message: str = Field(min_length=3, max_length=5000)
    affected_entities: tuple[EntityReferenceInput, ...] = ()


class RecordImpactAssessment(BaseModel):
    change_set_id: UUID
    direct_impacts: tuple[EntityReferenceInput, ...]
    indirect_impacts: tuple[EntityReferenceInput, ...]
    findings: tuple[ImpactFindingInput, ...]
    required_approval_roles: tuple[str, ...]
    required_tests: tuple[str, ...]
    estimated_blast_radius: ChangeRisk
    rollback_complexity: ChangeRisk
    confidence: float = Field(ge=0, le=1)
    dependency_analysis_complete: bool


class ValidationRequirementInput(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=3, max_length=5000)
    blocking: bool = True


class CreateValidationPlan(BaseModel):
    impact_assessment_id: UUID
    requirements: tuple[ValidationRequirementInput, ...] = Field(min_length=1)
    rollback_evidence_required: bool = True


class CreateRolloutPlan(BaseModel):
    transformation_plan_id: UUID
    validation_plan_id: UUID
    stages: tuple[str, ...] = Field(min_length=2)
    eligible_scope: dict[str, Any] = Field(default_factory=dict)
    excluded_scope: dict[str, Any] = Field(default_factory=dict)
    success_criteria: tuple[str, ...] = Field(min_length=1)
    rollback_criteria: tuple[str, ...] = Field(min_length=1)


class CreateRollbackPlan(BaseModel):
    transformation_plan_id: UUID
    validation_plan_id: UUID
    rollback_steps: tuple[str, ...] = Field(min_length=1)
    trigger_criteria: tuple[str, ...] = Field(min_length=1)
    recovery_time_objective_seconds: int = Field(gt=0)
    evidence: tuple[EvidenceReferenceInput, ...] = Field(min_length=1)


class ValidationResultInput(BaseModel):
    requirement_code: str
    passed: bool
    evidence: tuple[EvidenceReferenceInput, ...] = ()


class RecordChangeDecision(BaseModel):
    change_set_id: UUID
    impact_assessment_id: UUID
    validation_plan_id: UUID
    decision: ChangeDecisionType
    reason: str = Field(min_length=3, max_length=5000)
    validation_results: tuple[ValidationResultInput, ...]

    @model_validator(mode="after")
    def successful_validation_requires_evidence(self) -> "RecordChangeDecision":
        for result in self.validation_results:
            if result.passed and not result.evidence:
                raise ValueError("Passing validation requires evidence")
        return self


class RecordChangeObservation(BaseModel):
    decision_id: UUID
    observation_window_start: datetime
    observation_window_end: datetime
    metrics: dict[str, Any] = Field(min_length=1)
    findings: tuple[str, ...] = Field(min_length=1)
    evidence: tuple[EvidenceReferenceInput, ...] = Field(min_length=1)


class RecordChangeOutcome(BaseModel):
    observation_id: UUID
    disposition: ChangeOutcomeDisposition
    reason: str = Field(min_length=3, max_length=5000)
    evidence: tuple[EvidenceReferenceInput, ...] = Field(min_length=1)


class GovernanceActor(BaseModel):
    subject: str
    roles: frozenset[str] = frozenset()
    metadata: dict[str, Any] = Field(default_factory=dict)
