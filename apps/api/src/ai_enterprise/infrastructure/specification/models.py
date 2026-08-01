from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class EngineeringSpecificationModel(Base):
    __tablename__ = "engineering_specifications"
    __table_args__ = (UniqueConstraint("project_id", "specification_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    specification_key: Mapped[str] = mapped_column(String(240))
    specification_type: Mapped[str] = mapped_column(String(60))
    version: Mapped[str] = mapped_column(String(40))
    specification_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    specification_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requirements_hash: Mapped[str] = mapped_column(String(64))
    architecture_hash: Mapped[str] = mapped_column(String(64))
    work_package_hash: Mapped[str] = mapped_column(String(64))
    parent_specification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("engineering_specifications.id")
    )
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpecificationApprovalModel(Base):
    __tablename__ = "engineering_specification_approvals"
    __table_args__ = (UniqueConstraint("specification_id", "specification_hash", "decision"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    specification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_specifications.id"))
    specification_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpecificationGenerationRunModel(Base):
    __tablename__ = "specification_generation_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    specification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_specifications.id"))
    specification_hash: Mapped[str] = mapped_column(String(64))
    generator_key: Mapped[str] = mapped_column(String(120))
    generator_version: Mapped[str] = mapped_column(String(80))
    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    request_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_manifest: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_manifest_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    failure_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    requested_by: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GeneratedEngineeringArtifactModel(Base):
    __tablename__ = "generated_engineering_artifacts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    generation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("specification_generation_runs.id")
    )
    artifact_type: Mapped[str] = mapped_column(String(80))
    repository_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    specification_hash: Mapped[str] = mapped_column(String(64))
    generator_version: Mapped[str] = mapped_column(String(80))
    provenance_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpecificationValidationRunModel(Base):
    __tablename__ = "specification_validation_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    specification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_specifications.id"))
    specification_hash: Mapped[str] = mapped_column(String(64))
    validator_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EngineeringEvidenceNodeModel(Base):
    __tablename__ = "engineering_evidence_nodes"
    __table_args__ = (UniqueConstraint("node_type", "reference_id", "reference_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    node_type: Mapped[str] = mapped_column(String(60))
    reference_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    reference_hash: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str] = mapped_column(String(30))
    node_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    node_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EngineeringEvidenceEdgeModel(Base):
    __tablename__ = "engineering_evidence_edges"
    __table_args__ = (UniqueConstraint("source_node_id", "target_node_id", "relationship"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_evidence_nodes.id"))
    target_node_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_evidence_nodes.id"))
    relationship: Mapped[str] = mapped_column(String(80))
    edge_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    edge_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DriftDetectionRunModel(Base):
    __tablename__ = "engineering_drift_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    specification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_specifications.id"))
    specification_hash: Mapped[str] = mapped_column(String(64))
    repository_commit_hash: Mapped[str] = mapped_column(String(64))
    runtime_deployment_hash: Mapped[str | None] = mapped_column(String(64))
    detector_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    comparison_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    comparison_hash: Mapped[str] = mapped_column(String(64), unique=True)
    requested_by: Mapped[str] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DriftFindingModel(Base):
    __tablename__ = "engineering_drift_findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    drift_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_drift_runs.id"))
    category: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(30))
    expected_hash: Mapped[str] = mapped_column(String(64))
    actual_hash: Mapped[str] = mapped_column(String(64))
    evidence_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    finding_hash: Mapped[str] = mapped_column(String(64), unique=True)
    promotion_blocking: Mapped[bool] = mapped_column(Boolean)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DriftDecisionModel(Base):
    __tablename__ = "engineering_drift_decisions"
    __table_args__ = (UniqueConstraint("finding_id", "finding_hash", "decision"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engineering_drift_findings.id"))
    finding_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[str] = mapped_column(String(200))
    rationale: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
