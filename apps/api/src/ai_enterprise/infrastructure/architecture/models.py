import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class ArchitectureRunModel(Base):
    __tablename__ = "architecture_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    requirements_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    requirements_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    crew_version: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    temperature: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    prompt_bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    system_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    audit_hash: Mapped[str | None] = mapped_column(String(64))
    revision_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "architecture_revision_requests.id", use_alter=True, name="fk_arch_run_revision"
        ),
        unique=True,
    )
    parent_architecture_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("architecture_artifacts.id", use_alter=True, name="fk_arch_run_parent"),
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArchitectureExecutionAttemptModel(Base):
    __tablename__ = "architecture_execution_attempts"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_number", name="uq_architecture_attempt_number"),
        UniqueConstraint("idempotency_key", name="uq_architecture_attempt_idempotency"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_runs.id", ondelete="RESTRICT"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_output: Mapped[str | None] = mapped_column(Text)
    raw_output_hash: Mapped[str | None] = mapped_column(String(64))
    validation_report: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(100))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArchitectureArtifactModel(Base):
    __tablename__ = "architecture_artifacts"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_architecture_project_version"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_runs.id", ondelete="RESTRICT"), unique=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    requirements_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("architecture_artifacts.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False)
    structured_content: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArchitectureReviewModel(Base):
    __tablename__ = "architecture_reviews"
    __table_args__ = (
        UniqueConstraint(
            "architecture_artifact_id", "review_round", name="uq_architecture_review_round"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    architecture_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_artifacts.id", ondelete="RESTRICT"), index=True
    )
    review_round: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    reviewer_subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str | None] = mapped_column(String(32))
    comments: Mapped[str | None] = mapped_column(Text)
    reviewed_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArchitectureReviewFindingModel(Base):
    __tablename__ = "architecture_review_findings"
    __table_args__ = (
        UniqueConstraint("review_id", "finding_key", name="uq_architecture_review_finding"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_reviews.id", ondelete="RESTRICT"), index=True
    )
    finding_key: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_change: Mapped[str | None] = mapped_column(Text)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ArchitectureRevisionRequestModel(Base):
    __tablename__ = "architecture_revision_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_artifacts.id", ondelete="RESTRICT"), index=True
    )
    source_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_reviews.id", ondelete="RESTRICT"), unique=True
    )
    source_artifact_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    requirements_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    requested_by_role: Mapped[str] = mapped_column(String(100), nullable=False)
    revision_instructions: Mapped[str] = mapped_column(Text, nullable=False)
    inherited_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    revision_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("architecture_runs.id", ondelete="RESTRICT"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ArchitectureApprovalModel(Base):
    __tablename__ = "architecture_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    architecture_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_artifacts.id", ondelete="RESTRICT"), unique=True, index=True
    )
    approving_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_reviews.id", ondelete="RESTRICT"), unique=True
    )
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(100), nullable=False)
    approver_subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    approved_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
