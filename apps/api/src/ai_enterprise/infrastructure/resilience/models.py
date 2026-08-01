"""P9-M1 ORM declarations.

These tables intentionally have no migration until the P4 migration head is fixed.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class ResilienceServiceModel(Base):
    __tablename__ = "resilience_services"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    service_type: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    primary_owner: Mapped[str] = mapped_column(String(200), nullable=False)
    deputy_owner: Mapped[str] = mapped_column(String(200), nullable=False)


class RecoveryObjectiveModel(Base):
    __tablename__ = "resilience_recovery_objectives"
    __table_args__ = (UniqueConstraint("service_id", "policy_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resilience_services.id"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(20), nullable=False)
    rto_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    rpo_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    mtpd_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    work_recovery_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ServiceDependencyModel(Base):
    __tablename__ = "resilience_service_dependencies"
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resilience_services.id"), primary_key=True
    )
    dependency_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resilience_services.id"), primary_key=True
    )
    requirement: Mapped[str] = mapped_column(String(40), nullable=False)
    fail_open_prohibited: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ContinuityActivationModel(Base):
    __tablename__ = "continuity_activations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    mode: Mapped[str] = mapped_column(String(60), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    prohibited_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    activated_by: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_reviewed_by: Mapped[str | None] = mapped_column(String(200))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CapabilityDecisionModel(Base):
    __tablename__ = "continuity_capability_decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    capability: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(200))
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    policy_versions: Mapped[list[int]] = mapped_column(JSONB, nullable=False)
    activation_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BackupManifestModel(Base):
    __tablename__ = "backup_manifests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    backup_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    encryption_profile: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    audit_checkpoint_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_locations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RestoreVerificationModel(Base):
    __tablename__ = "restore_verifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    backup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("backup_manifests.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    isolated_environment: Mapped[bool] = mapped_column(Boolean, nullable=False)
    production_credentials_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    external_dispatch_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DisasterRecoveryRunModel(Base):
    __tablename__ = "disaster_recovery_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    commander: Mapped[str] = mapped_column(String(200), nullable=False)
    recovery_site: Mapped[str] = mapped_column(String(200), nullable=False)
    selected_recovery_point: Mapped[str | None] = mapped_column(String(200))
    unresolved_workflows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unresolved_external_effects: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_artifacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exit_reviewed_by: Mapped[str | None] = mapped_column(String(200))


class DisasterRecoveryPlanModel(Base):
    __tablename__ = "disaster_recovery_plans"
    __table_args__ = (UniqueConstraint("plan_key", "plan_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    plan_key: Mapped[str] = mapped_column(String(100), nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    authority_role: Mapped[str] = mapped_column(String(100), nullable=False)
    step_definitions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DisasterRecoveryStepModel(Base):
    __tablename__ = "disaster_recovery_steps"
    __table_args__ = (UniqueConstraint("run_id", "step_key", "attempt_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("disaster_recovery_runs.id"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_binding_sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    output_binding_sha256: Mapped[str | None] = mapped_column(String(128))
    evidence_artifact_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(128))
