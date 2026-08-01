import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class JobExecutionAttemptModel(Base):
    __tablename__ = "job_execution_attempts"
    __table_args__ = (UniqueConstraint("job_id", "attempt_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False)
    lease_token: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lease_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queue_wait_ms: Mapped[int | None] = mapped_column(BigInteger)
    execution_ms: Mapped[int | None] = mapped_column(BigInteger)
    failure_class: Mapped[str | None] = mapped_column(String(100))
    failure_code: Mapped[str | None] = mapped_column(String(128))
    failure_message: Mapped[str | None] = mapped_column(Text)
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    revision_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements_revision_cycles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    raw_output_hash: Mapped[str | None] = mapped_column(String(64))
    repair_attempted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    repair_succeeded: Mapped[bool | None] = mapped_column(Boolean)
    validation_errors: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)


class WorkerInstanceModel(Base):
    __tablename__ = "worker_instances"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    worker_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    profile: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
