"""P9 extended governance declarations; external operations remain adapter-owned."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class RegionModel(Base):
    __tablename__ = "resilience_regions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class RegionOwnershipLeaseModel(Base):
    __tablename__ = "region_ownership_leases"
    __table_args__ = (UniqueConstraint("resource_id", "fencing_token"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    region_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resilience_regions.id"), nullable=False
    )
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    witness_evidence_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResidencyPolicyModel(Base):
    __tablename__ = "data_residency_policies"
    __table_args__ = (UniqueConstraint("classification", "jurisdiction", "policy_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    classification: Mapped[str] = mapped_column(String(80), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_regions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    processing_regions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    provider_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    cross_border_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)


class ExecutionZoneModel(Base):
    __tablename__ = "sovereign_execution_zones"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    policy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class ModelProviderModel(Base):
    __tablename__ = "governed_model_providers"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    regions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    retention_mode: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class ModelDefinitionModel(Base):
    __tablename__ = "governed_model_definitions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("governed_model_providers.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    hosting_region: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_use_cases: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    prohibited_data_classes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evaluation_evidence_hash: Mapped[str | None] = mapped_column(String(128))


class ModelSubstitutionModel(Base):
    __tablename__ = "model_substitution_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    original_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    replacement_model_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    policy_evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CryptoProfileModel(Base):
    __tablename__ = "cryptographic_profiles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class CryptoKeyVersionModel(Base):
    __tablename__ = "cryptographic_key_versions"
    __table_args__ = (UniqueConstraint("key_id", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    key_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cryptographic_profiles.id"), nullable=False
    )
    provider_reference: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SignatureRecordModel(Base):
    __tablename__ = "signature_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    key_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cryptographic_key_versions.id"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuthoritySuccessionModel(Base):
    __tablename__ = "authority_succession_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    primary_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    deputy_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    emergency_group: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)


class EmergencyGrantModel(Base):
    __tablename__ = "emergency_authority_grants"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(200), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    issued_by: Mapped[str] = mapped_column(String(200), nullable=False)
    second_approver: Mapped[str] = mapped_column(String(200), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InstitutionalRunbookModel(Base):
    __tablename__ = "institutional_runbooks"
    __table_args__ = (UniqueConstraint("runbook_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runbook_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    deputy: Mapped[str] = mapped_column(String(200), nullable=False)
    procedure: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class RehearsalModel(Base):
    __tablename__ = "institutional_rehearsals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VendorExitPlanModel(Base):
    __tablename__ = "vendor_exit_plans"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vendor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resilience_services.id"), nullable=False
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    owner: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    rehearsal_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutional_rehearsals.id")
    )


class TechnologySubstitutionModel(Base):
    __tablename__ = "technology_substitution_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    vendor_exit_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendor_exit_plans.id"), nullable=False
    )
    source_adapter: Mapped[str] = mapped_column(String(160), nullable=False)
    target_adapter: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)


class ResilienceExperimentModel(Base):
    __tablename__ = "resilience_experiments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    injection: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    safety_limits: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    abort_conditions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(200))
    provider_evidence_hash: Mapped[str | None] = mapped_column(String(128))


class ArtifactMigrationModel(Base):
    __tablename__ = "artifact_migration_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    target_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id"), nullable=False
    )
    source_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    target_schema_version: Mapped[str] = mapped_column(String(100), nullable=False)
    transformation_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    verified_by: Mapped[str] = mapped_column(String(200), nullable=False)


class ArchiveVerificationModel(Base):
    __tablename__ = "archive_verification_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    archive_location: Mapped[str] = mapped_column(String(300), nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_evidence_hash: Mapped[str | None] = mapped_column(String(128))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrisisActivationModel(Base):
    __tablename__ = "crisis_mode_activations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    declared_by: Mapped[str] = mapped_column(String(200), nullable=False)
    second_approver: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    prohibited_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    integrity_reviewed_by: Mapped[str | None] = mapped_column(String(200))
    authority_reviewed_by: Mapped[str | None] = mapped_column(String(200))
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class InstitutionalGovernanceRecordModel(Base):
    __tablename__ = "institutional_governance_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    record_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider_evidence_hash: Mapped[str | None] = mapped_column(String(128))
    recorded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
