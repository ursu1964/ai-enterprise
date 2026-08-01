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
class ContinuityPolicy:
    mode: ContinuityMode
    allowed: frozenset[Capability]
    prohibited: frozenset[Capability]
    maximum_duration_seconds: int
    policy_version: int


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
