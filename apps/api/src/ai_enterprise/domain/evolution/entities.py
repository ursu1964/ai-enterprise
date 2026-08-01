from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from .enums import (
    Compatibility,
    ControlEffectiveness,
    LifecycleStatus,
    PolicyLevel,
    RolloutStatus,
)


@dataclass(frozen=True, slots=True)
class VersionedCandidate:
    id: UUID
    subject_id: UUID
    version: int
    content_hash: str
    status: LifecycleStatus
    created_by: str
    created_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ArchitectureDecision:
    id: UUID
    change_proposal_id: UUID
    title: str
    context: str
    decision: str
    alternatives: tuple[str, ...]
    consequences: tuple[str, ...]
    current_state_hash: str
    target_state_hash: str
    transition_plan_hash: str
    approved_by: str | None
    content_hash: str


@dataclass(frozen=True, slots=True)
class FitnessResult:
    rule_code: str
    passed: bool
    blocking: bool
    evidence_hash: str


@dataclass(frozen=True, slots=True)
class PolicyVersion:
    id: UUID
    policy_id: UUID
    version: int
    level: PolicyLevel
    rule_content_hash: str
    status: LifecycleStatus
    test_results: tuple[FitnessResult, ...]
    supersedes_id: UUID | None


@dataclass(frozen=True, slots=True)
class WorkflowMigrationPlan:
    id: UUID
    source_definition_id: UUID
    source_version: int
    target_definition_id: UUID
    target_version: int
    eligible_states: tuple[str, ...]
    prohibited_states: tuple[str, ...]
    state_mapping: dict[str, str]
    validation_hashes: tuple[str, ...]
    rollback_supported: bool


@dataclass(frozen=True, slots=True)
class SchemaVersion:
    id: UUID
    schema_id: UUID
    version: str
    compatibility: Compatibility
    schema_hash: str
    semantic_hash: str
    migration_plan_id: UUID | None


@dataclass(frozen=True, slots=True)
class PromotionEvidence:
    offline_passed: bool
    replay_passed: bool
    shadow_passed: bool
    pilot_passed: bool
    evidence_hashes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Experiment:
    id: UUID
    change_proposal_id: UUID
    version: int
    assignment_salt: str
    control_hash: str
    treatment_hash: str
    guardrail_codes: tuple[str, ...]
    status: LifecycleStatus


@dataclass(frozen=True, slots=True)
class ExperimentAssignment:
    experiment_id: UUID
    subject_id: UUID
    arm: str
    assignment_hash: str


@dataclass(frozen=True, slots=True)
class ShadowCommand:
    command_type: str
    payload_hash: str
    side_effecting: bool
    credential_scope: str | None


@dataclass(frozen=True, slots=True)
class Rollout:
    id: UUID
    change_proposal_id: UUID
    stages: tuple[str, ...]
    current_stage: int
    status: RolloutStatus
    required_gate_codes: tuple[str, ...]
    rollback_plan_hash: str


@dataclass(frozen=True, slots=True)
class ControlTest:
    control_id: UUID
    passed: bool
    evidence_hashes: tuple[str, ...]
    tested_at: datetime


@dataclass(frozen=True, slots=True)
class ControlState:
    control_id: UUID
    effectiveness: ControlEffectiveness
    last_test: ControlTest | None


@dataclass(frozen=True, slots=True)
class ImprovementItem:
    id: UUID
    source_type: str
    source_id: UUID
    owner_id: str
    priority_score: float
    evidence_hashes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DebtItem:
    id: UUID
    debt_type: str
    risk_level: str
    owner_id: str
    target_resolution_at: datetime | None
    origin_change_id: UUID | None


@dataclass(frozen=True, slots=True)
class PolicyException:
    id: UUID
    policy_id: UUID
    owner_id: str
    reason: str
    scope_hash: str
    compensating_control_ids: tuple[UUID, ...]
    removal_plan_hash: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ConstitutionalApproval:
    actor_id: str
    role: str
    signature_reference: str
    approved_at: datetime


@dataclass(frozen=True, slots=True)
class ConstitutionalAmendment:
    id: UUID
    change_proposal_id: UUID
    constitutional_policy_id: UUID
    proposed_by: str
    candidate_hash: str
    required_roles: tuple[str, ...]
    minimum_approval_count: int
    cooling_off_until: datetime
    approvals: tuple[ConstitutionalApproval, ...]
