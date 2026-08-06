from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class R22ArtifactRegistryModel(Base):
    __tablename__ = "r22_artifact_registries"
    __table_args__ = (
        UniqueConstraint("project_key", "tenant_key", "registry_hash"),
        Index("ix_r22_artifact_registries_project_key", "project_key"),
        Index("ix_r22_artifact_registries_tenant_key", "tenant_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    registry_id: Mapped[str] = mapped_column(String(200), nullable=False)
    registry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22ArtifactModel(Base):
    __tablename__ = "r22_artifacts"
    __table_args__ = (
        UniqueConstraint("tenant_key", "artifact_id", "artifact_hash"),
        Index("ix_r22_artifacts_project_key", "project_key"),
        Index("ix_r22_artifacts_artifact_id", "artifact_id"),
        Index("ix_r22_artifacts_artifact_class", "artifact_class"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(220), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_class: Mapped[str] = mapped_column(String(80), nullable=False)
    current_version_id: Mapped[str] = mapped_column(String(220), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22ArtifactVersionModel(Base):
    __tablename__ = "r22_artifact_versions"
    __table_args__ = (
        UniqueConstraint("tenant_key", "artifact_version_id", "version_hash"),
        Index("ix_r22_artifact_versions_project_key", "project_key"),
        Index("ix_r22_artifact_versions_artifact_id", "artifact_id"),
        Index("ix_r22_artifact_versions_lifecycle_state", "lifecycle_state"),
        Index("ix_r22_artifact_versions_checksum", "checksum"),
        Index("ix_r22_artifact_versions_classification", "classification"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(220), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(String(220), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(80), nullable=False)
    validation_state: Mapped[str] = mapped_column(String(80), nullable=False)
    freshness_state: Mapped[str] = mapped_column(String(80), nullable=False)
    integrity_state: Mapped[str] = mapped_column(String(80), nullable=False)
    governance_state: Mapped[str] = mapped_column(String(80), nullable=False)
    checksum: Mapped[str] = mapped_column(String(96), nullable=False)
    content_address: Mapped[str] = mapped_column(String(220), nullable=False)
    classification: Mapped[str] = mapped_column(String(80), nullable=False)
    version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22ProvenanceRecordModel(Base):
    __tablename__ = "r22_provenance_records"
    __table_args__ = (
        UniqueConstraint("tenant_key", "provenance_id", "provenance_hash"),
        Index("ix_r22_provenance_records_project_key", "project_key"),
        Index("ix_r22_provenance_records_subject_id", "subject_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    provenance_id: Mapped[str] = mapped_column(String(220), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(220), nullable=False)
    provenance_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22TraceRelationshipModel(Base):
    __tablename__ = "r22_trace_relationships"
    __table_args__ = (
        UniqueConstraint("tenant_key", "relationship_id", "relationship_hash"),
        Index("ix_r22_trace_relationships_project_key", "project_key"),
        Index("ix_r22_trace_relationships_source_id", "source_id"),
        Index("ix_r22_trace_relationships_target_id", "target_id"),
        Index("ix_r22_trace_relationships_relationship_type", "relationship_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_id: Mapped[str] = mapped_column(String(220), nullable=False)
    source_id: Mapped[str] = mapped_column(String(220), nullable=False)
    target_id: Mapped[str] = mapped_column(String(220), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    relationship_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22EvidenceRecordModel(Base):
    __tablename__ = "r22_evidence_records"
    __table_args__ = (
        UniqueConstraint("tenant_key", "evidence_id", "evidence_hash"),
        Index("ix_r22_evidence_records_project_key", "project_key"),
        Index("ix_r22_evidence_records_subject_id", "subject_id"),
        Index("ix_r22_evidence_records_claim_id", "claim_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(220), nullable=False)
    claim_id: Mapped[str | None] = mapped_column(String(220), nullable=True)
    subject_id: Mapped[str] = mapped_column(String(220), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22ValidationResultModel(Base):
    __tablename__ = "r22_validation_results"
    __table_args__ = (
        UniqueConstraint("tenant_key", "validation_id", "validation_hash"),
        Index("ix_r22_validation_results_project_key", "project_key"),
        Index("ix_r22_validation_results_artifact_version_id", "artifact_version_id"),
        Index("ix_r22_validation_results_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(220), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    validation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22FindingModel(Base):
    __tablename__ = "r22_findings"
    __table_args__ = (
        UniqueConstraint("tenant_key", "finding_id", "finding_hash"),
        Index("ix_r22_findings_project_key", "project_key"),
        Index("ix_r22_findings_artifact_version_id", "artifact_version_id"),
        Index("ix_r22_findings_state", "state"),
        Index("ix_r22_findings_severity", "severity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(220), nullable=False)
    artifact_version_id: Mapped[str] = mapped_column(String(220), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(80), nullable=False)
    finding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R22ArtifactEventModel(Base):
    __tablename__ = "r22_artifact_events"
    __table_args__ = (
        UniqueConstraint("tenant_key", "event_id"),
        Index("ix_r22_artifact_events_project_key", "project_key"),
        Index("ix_r22_artifact_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_key: Mapped[str] = mapped_column(String(160), nullable=False)
    event_id: Mapped[str] = mapped_column(String(220), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    checksum: Mapped[str] = mapped_column(String(96), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
