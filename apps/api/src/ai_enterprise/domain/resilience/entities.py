from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from .enums import (
    BackupStatus,
    Capability,
    ContinuityMode,
    CriticalityTier,
    DependencyRequirement,
    DisasterRecoveryStatus,
    GovernanceAdmissionEffect,
    GovernanceAvailabilityClass,
    GovernanceContinuityEffect,
    GovernanceDeadlineClass,
    GovernanceDependencyCriticality,
    GovernanceDependencyState,
    RestoreStatus,
)


@dataclass(frozen=True, slots=True)
class RecoveryObjective:
    service_id: UUID
    tier: CriticalityTier
    rto_seconds: int
    rpo_seconds: int
    mtpd_seconds: int
    work_recovery_time_seconds: int
    primary_owner: str
    deputy_owner: str
    policy_version: int
    approved_by: str | None = None
    approved_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ServiceDependency:
    service_id: UUID
    dependency_service_id: UUID
    requirement: DependencyRequirement
    fail_open_prohibited: bool


@dataclass(frozen=True, slots=True)
class GovernanceDependencyAvailability:
    dependency_id: str
    state: GovernanceDependencyState
    criticality: GovernanceDependencyCriticality
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class GovernanceStalenessEnvelope:
    capability: Capability
    maximum_age_by_dimension_seconds: dict[str, int]


@dataclass(frozen=True, slots=True)
class GovernanceCachedAuthority:
    authority_id: str
    subject_id: str
    capability: Capability
    captured_at: datetime
    valid_until: datetime
    revocation_sensitive: bool
    dimensions: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class GovernanceAvailabilityBudget:
    maximum_duration_seconds: int
    maximum_executions: int | None = None
    maximum_external_effects: int | None = None
    maximum_ai_tool_calls: int | None = None


@dataclass(frozen=True, slots=True)
class GovernanceAvailabilityBudgetUsage:
    started_at: datetime
    executions: int = 0
    external_effects: int = 0
    ai_tool_calls: int = 0


@dataclass(frozen=True, slots=True)
class GovernanceContinuityLease:
    id: UUID
    capability: Capability
    mode: ContinuityMode
    issued_at: datetime
    expires_at: datetime
    authority: str
    issued_to: str
    self_renewal_prohibited: bool = True


@dataclass(frozen=True, slots=True)
class ContinuityPolicy:
    mode: ContinuityMode
    allowed: frozenset[Capability]
    prohibited: frozenset[Capability]
    maximum_duration_seconds: int
    policy_version: int


@dataclass(frozen=True, slots=True)
class GovernanceAvailabilityContract:
    id: str
    capability: Capability
    availability_class: GovernanceAvailabilityClass
    dependency_behaviors: dict[str, ContinuityMode]
    fail_open_allowed: bool
    cached_authority_allowed: bool
    queue_allowed: bool
    emergency_capabilities: frozenset[Capability]
    required_evidence: bool
    policy_version: int


@dataclass(frozen=True, slots=True)
class GovernanceContinuityDecision:
    capability: Capability
    effect: GovernanceContinuityEffect
    mode: ContinuityMode
    reason: str
    policy_version: int
    dependency_states: dict[str, GovernanceDependencyState]
    lease_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GovernanceAdmissionToken:
    id: UUID
    capability: Capability
    effect: GovernanceAdmissionEffect
    mode: ContinuityMode
    priority: str
    valid_until: datetime
    policy_version: int


@dataclass(frozen=True, slots=True)
class GovernanceContinuityEvidence:
    id: UUID
    capability: Capability
    decision: GovernanceContinuityDecision
    admitted_executions: int
    blocked_executions: int
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class ContinuityActivation:
    id: UUID
    policy: ContinuityPolicy
    activated_at: datetime
    expires_at: datetime
    activated_by: str
    reason: str
    closed_at: datetime | None = None
    exit_reviewed_by: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityDecision:
    capability: Capability
    allowed: bool
    reason: str
    policy_versions: tuple[int, ...]
    activation_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class BackupManifest:
    id: UUID
    backup_type: str
    content_hash: str
    object_count: int
    total_bytes: int
    encryption_profile: str
    schema_version: str
    audit_checkpoint_hash: str
    storage_locations: tuple[str, ...]
    status: BackupStatus = BackupStatus.CREATED


@dataclass(frozen=True, slots=True)
class RestoreVerification:
    id: UUID
    backup_id: UUID
    status: RestoreStatus
    isolated_environment: bool
    production_credentials_disabled: bool
    external_dispatch_blocked: bool
    checks: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DisasterRecoveryRun:
    id: UUID
    plan_version: int
    status: DisasterRecoveryStatus
    commander: str
    recovery_site: str
    selected_recovery_point: str | None = None
    unresolved_workflows: int = 0
    unresolved_external_effects: int = 0
    missing_artifacts: int = 0
    exit_reviewed_by: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    ready: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernanceDeadline:
    id: str
    capability: Capability
    deadline_class: GovernanceDeadlineClass
    due_at: datetime
    miss_behavior: GovernanceContinuityEffect


@dataclass(frozen=True, slots=True)
class GovernanceLatencyBudget:
    capability: Capability
    end_to_end_milliseconds: int
    evaluation_milliseconds: int
    authorization_milliseconds: int
    evidence_milliseconds: int
    revocation_milliseconds: int = 0


@dataclass(frozen=True, slots=True)
class GovernancePerformanceEvidence:
    capability: Capability
    started_at: datetime
    completed_at: datetime
    elapsed_milliseconds: int
    budget_milliseconds: int
    deadline_met: bool
    reason: str
