from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ai_enterprise.domain.resilience.enums import (
    Capability,
    ContinuityMode,
    CriticalityTier,
    DependencyRequirement,
    DisasterRecoveryStatus,
    RestoreStatus,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServiceRequest(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    service_type: str = Field(min_length=1, max_length=40)
    primary_owner: str = Field(min_length=1, max_length=200)
    deputy_owner: str = Field(min_length=1, max_length=200)


class ObjectiveRequest(StrictModel):
    tier: CriticalityTier
    rto_seconds: int = Field(gt=0)
    rpo_seconds: int = Field(ge=0)
    mtpd_seconds: int = Field(gt=0)
    work_recovery_time_seconds: int = Field(ge=0)


class DependencyRequest(StrictModel):
    dependency_service_id: UUID
    requirement: DependencyRequirement
    fail_open_prohibited: bool = True


class ContinuityActivationRequest(StrictModel):
    mode: ContinuityMode
    allowed_capabilities: list[Capability]
    prohibited_capabilities: list[Capability]
    maximum_duration_seconds: int = Field(gt=0, le=86400)
    reason: str = Field(min_length=1)


class BackupManifestRequest(StrictModel):
    backup_type: str
    content_hash: str = Field(min_length=32, max_length=128)
    object_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    encryption_profile: str
    schema_version: str
    audit_checkpoint_hash: str
    storage_locations: list[str] = Field(min_length=1)


class RestoreVerificationRequest(StrictModel):
    status: RestoreStatus
    isolated_environment: bool
    production_credentials_disabled: bool
    external_dispatch_blocked: bool
    checks: dict[str, bool]


class DisasterRecoveryRunRequest(StrictModel):
    plan_version: int = Field(gt=0)
    commander: str
    recovery_site: str
    selected_recovery_point: str | None = None


class DisasterRecoveryPlanRequest(StrictModel):
    plan_key: str = Field(min_length=1, max_length=100)
    authority_role: str = Field(min_length=1, max_length=100)
    step_definitions: list[dict[str, object]] = Field(min_length=1)


class DisasterRecoveryTransitionRequest(StrictModel):
    target: DisasterRecoveryStatus
    selected_recovery_point: str | None = None
    unresolved_workflows: int = Field(ge=0, default=0)
    unresolved_external_effects: int = Field(ge=0, default=0)
    missing_artifacts: int = Field(ge=0, default=0)
