import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class RepositorySnapshotModel(Base):
    __tablename__ = "repository_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "repository_uri", "base_commit_sha"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    repository_uri: Mapped[str] = mapped_column(Text, nullable=False)
    base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    tree_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RepositoryIndexModel(Base):
    __tablename__ = "repository_indexes"
    __table_args__ = (UniqueConstraint("snapshot_id", "index_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_snapshots.id", ondelete="RESTRICT"), index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    index_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    index_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecompositionRunModel(Base):
    __tablename__ = "work_package_decomposition_runs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    requirements_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    architecture_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("architecture_artifacts.id", ondelete="RESTRICT")
    )
    repository_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_snapshots.id", ondelete="RESTRICT")
    )
    repository_index_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repository_indexes.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    crew_definition_version: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_decomposition_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_package_decomposition_runs.id", ondelete="RESTRICT")
    )
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "work_package_decomposition_artifacts.id",
            use_alter=True,
            name="fk_decomposition_run_parent_artifact",
        )
    )
    revision_reason: Mapped[str | None] = mapped_column(Text)
    review_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CandidateOutputModel(Base):
    __tablename__ = "work_package_candidate_outputs"
    __table_args__ = (UniqueConstraint("decomposition_run_id", "attempt_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decomposition_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_runs.id", ondelete="RESTRICT"), index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    raw_output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecompositionArtifactModel(Base):
    __tablename__ = "work_package_decomposition_artifacts"
    __table_args__ = (UniqueConstraint("decomposition_run_id", "artifact_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decomposition_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_runs.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    graph_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkPackageModel(Base):
    __tablename__ = "decomposition_work_packages"
    __table_args__ = (
        UniqueConstraint("decomposition_artifact_id", "package_key"),
        UniqueConstraint("decomposition_artifact_id", "sequence_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    decomposition_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_artifacts.id", ondelete="RESTRICT"), index=True
    )
    package_key: Mapped[str] = mapped_column(String(160), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    package_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    package_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkPackageDependencyModel(Base):
    __tablename__ = "work_package_dependencies"
    decomposition_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_artifacts.id", ondelete="RESTRICT"), primary_key=True
    )
    predecessor_package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decomposition_work_packages.id", ondelete="RESTRICT"), primary_key=True
    )
    successor_package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decomposition_work_packages.id", ondelete="RESTRICT"), primary_key=True
    )
    dependency_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)


class ValidationFindingModel(Base):
    __tablename__ = "decomposition_validation_findings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decomposition_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_artifacts.id", ondelete="RESTRICT"), index=True
    )
    validator_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    package_key: Mapped[str | None] = mapped_column(String(160))
    path: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecompositionReviewModel(Base):
    __tablename__ = "decomposition_reviews"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decomposition_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_artifacts.id", ondelete="RESTRICT"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(200), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    comments: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecompositionApprovalModel(Base):
    __tablename__ = "decomposition_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    decomposition_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_package_decomposition_artifacts.id", ondelete="RESTRICT"), unique=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decomposition_reviews.id", ondelete="RESTRICT"), unique=True
    )
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
