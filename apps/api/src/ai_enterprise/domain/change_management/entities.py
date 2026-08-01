from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from .enums import (
    ChangeCategory,
    ChangeDecisionType,
    ChangeRisk,
    ChangeStatus,
    ImpactKnowledge,
)


@dataclass(frozen=True, slots=True)
class EntityReference:
    entity_type: str
    entity_id: UUID
    entity_version: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    artifact_id: UUID
    content_hash: str
    evidence_type: str


@dataclass(frozen=True, slots=True)
class ChangeProposal:
    id: UUID
    organization_id: UUID
    title: str
    description: str
    category: ChangeCategory
    proposed_by: str
    sponsor_id: str
    problem_statement: str
    desired_outcome: str
    risk: ChangeRisk
    status: ChangeStatus
    affected_entities: tuple[EntityReference, ...]
    evidence: tuple[EvidenceReference, ...]
    created_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ChangeOperation:
    operation_type: str
    target: EntityReference
    before_hash: str | None
    candidate_hash: str
    description: str


@dataclass(frozen=True, slots=True)
class ChangeSet:
    id: UUID
    proposal_id: UUID
    version: int
    operations: tuple[ChangeOperation, ...]
    created_by: str
    created_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ImpactFinding:
    code: str
    dimension: str
    knowledge: ImpactKnowledge
    severity: ChangeRisk
    message: str
    affected_entities: tuple[EntityReference, ...] = ()


@dataclass(frozen=True, slots=True)
class ImpactAssessment:
    id: UUID
    proposal_id: UUID
    change_set_id: UUID
    version: int
    assessed_by: str
    direct_impacts: tuple[EntityReference, ...]
    indirect_impacts: tuple[EntityReference, ...]
    findings: tuple[ImpactFinding, ...]
    required_approval_roles: tuple[str, ...]
    required_tests: tuple[str, ...]
    estimated_blast_radius: ChangeRisk
    rollback_complexity: ChangeRisk
    confidence: float
    created_at: datetime
    content_hash: str

    @property
    def has_unknown_impact(self) -> bool:
        return any(item.knowledge is ImpactKnowledge.UNKNOWN for item in self.findings)


@dataclass(frozen=True, slots=True)
class ValidationRequirement:
    code: str
    description: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class ValidationPlan:
    id: UUID
    proposal_id: UUID
    impact_assessment_id: UUID
    version: int
    requirements: tuple[ValidationRequirement, ...]
    rollback_evidence_required: bool
    created_by: str
    created_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    requirement_code: str
    passed: bool
    evidence: tuple[EvidenceReference, ...]


@dataclass(frozen=True, slots=True)
class ChangeDecision:
    id: UUID
    proposal_id: UUID
    change_set_id: UUID
    impact_assessment_id: UUID
    validation_plan_id: UUID
    decision: ChangeDecisionType
    decided_by: str
    actor_roles: tuple[str, ...]
    reason: str
    validation_results: tuple[ValidationResult, ...]
    decided_at: datetime
    content_hash: str


@dataclass(frozen=True, slots=True)
class ChangeAuditRecord:
    event_type: str
    aggregate_id: UUID
    actor_id: str
    occurred_at: datetime
    payload: dict[str, Any]
    payload_hash: str
