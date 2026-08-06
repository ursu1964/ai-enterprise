import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)

    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    repository_path: Mapped[str] = mapped_column(Text, nullable=False)
    repository_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_branch: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="main",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    runs: Mapped[list["CrewRunModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )

    artifacts: Mapped[list["ArtifactModel"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class CrewRunModel(Base):
    __tablename__ = "crew_runs"
    __table_args__ = (
        Index("ix_crew_runs_project_created_at", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    crew_name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)

    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    error_message: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["ProjectModel"] = relationship(back_populates="runs")


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crew_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    artifact_type: Mapped[str] = mapped_column(String(120), nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped["ProjectModel"] = relationship(back_populates="artifacts")


class ApprovalModel(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(200), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_project_created_at", "project_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crew_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    job_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    lease_owner: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    lease_token: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_failure_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class WorkPackageModel(Base):
    __tablename__ = "work_packages"
    __table_args__ = (
        Index("ix_work_packages_project_created_at", "project_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    planning_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crew_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )

    status: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    objective: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    repository_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    base_commit_sha: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_requirements_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    source_requirements_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    source_architecture_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    source_architecture_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    contract: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    contract_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExecutionRunModel(Base):
    __tablename__ = "execution_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_execution_run_project_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    work_package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    approval_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approvals.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        index=True,
    )

    base_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    base_tree_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patch_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="generated", server_default="generated"
    )
    parent_execution_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=True
    )
    revision_source_review_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "patch_review_runs.id",
            ondelete="RESTRICT",
            name="fk_execution_run_revision_source_review",
            use_alter=True,
        ),
        nullable=True,
    )
    root_execution_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=True
    )
    lineage_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    container_image: Mapped[str] = mapped_column(Text, nullable=False)
    container_image_digest: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    implementation_exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    cpu_limit: Mapped[float] = mapped_column(
        Numeric(precision=6, scale=3),
        nullable=False,
    )
    memory_limit_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    pids_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    network_disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    runtime_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    changed_files: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    changed_file_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    insertions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deletions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    patch_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    log_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )

    patch_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ExecutionTestResultModel(Base):
    __tablename__ = "execution_test_results"
    __table_args__ = (
        UniqueConstraint(
            "execution_run_id",
            "sequence",
            name="uq_execution_test_result_sequence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    command: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    stdout_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    stderr_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ExecutionEventModel(Base):
    __tablename__ = "execution_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PatchReviewRunModel(Base):
    __tablename__ = "patch_review_runs"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_patch_review_project_idempotency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    work_package_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_packages.id", ondelete="RESTRICT"),
        nullable=False,
    )

    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    patch_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="pending",
        index=True,
    )

    base_commit: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_patch_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    actual_patch_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    container_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    review_image: Mapped[str] = mapped_column(Text, nullable=False)
    review_image_digest: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    decision_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    review_report_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    log_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    failure_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    failure_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    resulting_tree_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    review_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PatchReviewFindingModel(Base):
    __tablename__ = "patch_review_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patch_review_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="open",
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    line_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PatchReviewCheckModel(Base):
    __tablename__ = "patch_review_checks"
    __table_args__ = (
        UniqueConstraint(
            "patch_review_run_id",
            "sequence",
            name="uq_patch_review_check_sequence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patch_review_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    check_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    command: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    stdout_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )
    stderr_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class PatchReviewEventModel(Base):
    __tablename__ = "patch_review_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    patch_review_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_review_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ExecutionRunRevisionFindingModel(Base):
    __tablename__ = "execution_run_revision_findings"

    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), primary_key=True
    )
    review_finding_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patch_review_findings.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class IntegrationEligibilityModel(Base):
    __tablename__ = "integration_eligibilities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    patch_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    base_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    accepted_review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("patch_review_runs.id", ondelete="RESTRICT"), nullable=True
    )
    failure_reasons: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntegrationApprovalModel(Base):
    __tablename__ = "integration_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    eligibility_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_eligibilities.id", ondelete="RESTRICT"), nullable=False
    )
    approver_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    approver_role: Mapped[str] = mapped_column(String(80), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    repository_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    approved_patch_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_base_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_test_commands: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    approved_test_commands_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntegrationAttemptModel(Base):
    __tablename__ = "integration_attempts"
    __table_args__ = (
        UniqueConstraint(
            "execution_run_id", "attempt_number", name="uq_integration_attempt_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    execution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("execution_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    integration_approval_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_approvals.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_patch_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_base_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_base_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    actual_base_commit_sha: Mapped[str | None] = mapped_column(String(64))
    actual_base_tree_sha: Mapped[str | None] = mapped_column(String(64))
    resulting_tree_sha: Mapped[str | None] = mapped_column(String(64))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(200))
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntegrationAttemptRunModel(Base):
    __tablename__ = "integration_attempt_runs"
    __table_args__ = (
        UniqueConstraint("integration_attempt_id", "run_number", name="uq_integration_run_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    integration_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(80))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationStageExecutionModel(Base):
    __tablename__ = "integration_stage_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "stage_name", "stage_attempt", name="uq_integration_stage_run"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_attempt_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_binding_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    failure_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)


class CommitPlanModel(Base):
    __tablename__ = "commit_plans"
    __table_args__ = (
        UniqueConstraint("attempt_kind", "attempt_id", name="uq_commit_plan_attempt"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    attempt_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    author_email: Mapped[str] = mapped_column(String(320), nullable=False)
    author_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    committer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    committer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    committer_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    message_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IntegrationCommitModel(Base):
    __tablename__ = "integration_commits"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    integration_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_attempts.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RollbackRecordModel(Base):
    __tablename__ = "rollback_records"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    integration_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_attempts.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    integration_commit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_commits.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    integration_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    changed_paths: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    changed_paths_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    inverse_diff_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), nullable=False
    )
    inverse_diff_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    original_patch_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_test_commands: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    approved_test_commands_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    external_side_effects_declared: Mapped[bool] = mapped_column(Boolean, nullable=False)
    database_change_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    deployment_change_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recovery_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rollback_binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryIncidentModel(Base):
    __tablename__ = "recovery_incidents"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    integration_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rollback_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollback_records.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    reported_by: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)
    affected_environment: Mapped[str] = mapped_column(String(120), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryAssessmentModel(Base):
    __tablename__ = "recovery_assessments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_incidents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rollback_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollback_records.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(60), nullable=False)
    recommended_strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_remote_head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_commit_is_ancestor: Mapped[bool] = mapped_column(Boolean, nullable=False)
    direct_revert_possible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    database_coordination_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    external_coordination_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    required_test_commands: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    assessment_policy_version: Mapped[str] = mapped_column(String(80), nullable=False)
    assessment_binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RollbackApprovalModel(Base):
    __tablename__ = "rollback_approvals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recovery_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_assessments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rollback_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollback_records.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    recovery_strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    expected_remote_head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    required_test_commands: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    required_test_commands_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    approver_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryAttemptModel(Base):
    __tablename__ = "recovery_attempts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rollback_approval_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollback_approvals.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    recovery_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_assessments.id", ondelete="RESTRICT"), nullable=False
    )
    rollback_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollback_records.id", ondelete="RESTRICT"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    target_branch: Mapped[str] = mapped_column(String(200), nullable=False)
    expected_remote_head_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    recovery_strategy: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(80))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_message: Mapped[str | None] = mapped_column(Text)
    worker_id: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    push_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryAttemptRunModel(Base):
    __tablename__ = "recovery_attempt_runs"
    __table_args__ = (
        UniqueConstraint("recovery_attempt_id", "run_number", name="uq_recovery_run_number"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recovery_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(80), nullable=False)
    claim_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(80))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecoveryStageExecutionModel(Base):
    __tablename__ = "recovery_stage_executions"
    __table_args__ = (
        UniqueConstraint("run_id", "stage_name", "stage_attempt", name="uq_recovery_stage_run"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_attempt_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    stage_name: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    input_binding_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    output_binding_sha256: Mapped[str | None] = mapped_column(String(64))
    evidence_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    failure_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)


class RecoveryTestRunModel(Base):
    __tablename__ = "recovery_test_runs"
    __table_args__ = (
        UniqueConstraint("recovery_attempt_id", "command_index", name="uq_recovery_test_command"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recovery_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_attempts.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    command_index: Mapped[int] = mapped_column(Integer, nullable=False)
    command: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    stdout_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    stderr_artifact_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("artifacts.id"))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryCommitModel(Base):
    __tablename__ = "recovery_commits"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recovery_attempt_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_attempts.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    reverted_integration_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    commit_message_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    author_name: Mapped[str] = mapped_column(String(200), nullable=False)
    author_email: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RecoveryRemoteVerificationModel(Base):
    __tablename__ = "recovery_remote_verifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recovery_commit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recovery_commits.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    remote_commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_tree_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    remote_parent_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    integration_commit_in_history: Mapped[bool] = mapped_column(Boolean, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BlueprintAssetModel(Base):
    __tablename__ = "blueprint_assets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "blueprint_key",
            "version",
            name="uq_blueprint_asset_org_key_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    blueprint_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    lifecycle: Mapped[str] = mapped_column(
        String(40), nullable=False, default="proposed", index=True
    )
    source_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_phase: Mapped[str] = mapped_column(String(80), nullable=False)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("blueprint_assets.id", ondelete="RESTRICT")
    )
    pattern: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    economic_proof: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    recommended_use: Mapped[str] = mapped_column(Text, nullable=False)
    reuse_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BlueprintDecisionModel(Base):
    __tablename__ = "blueprint_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("blueprint_assets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    previous_lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(40), nullable=False)
    reviewer: Mapped[str] = mapped_column(String(200), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
