import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class RequirementsRevisionRequestModel(Base):
    __tablename__ = "requirements_revision_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    requirements_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crew_runs.id", ondelete="RESTRICT"), index=True
    )
    source_artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    source_review_decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("approvals.id", ondelete="RESTRICT"), unique=True
    )
    requested_by: Mapped[str] = mapped_column(String(200), nullable=False)
    feedback_summary: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    feedback_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RequirementsRevisionCycleModel(Base):
    __tablename__ = "requirements_revision_cycles"
    __table_args__ = (
        UniqueConstraint(
            "requirements_run_id", "cycle_number", name="uq_requirements_revision_cycle_number"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    requirements_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crew_runs.id", ondelete="RESTRICT"), index=True
    )
    revision_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirements_revision_requests.id", ondelete="RESTRICT"), unique=True
    )
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resulting_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), unique=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RequirementsArtifactLineageModel(Base):
    __tablename__ = "requirements_artifact_lineage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT"), unique=True
    )
    revision_cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements_revision_cycles.id", ondelete="RESTRICT"), index=True
    )
    previous_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_feedback_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
