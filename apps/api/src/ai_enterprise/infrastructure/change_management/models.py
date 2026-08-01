import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
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


class ChangeProposalModel(Base):
    __tablename__ = "change_proposals"
    __table_args__ = (
        CheckConstraint(
            "risk IN ('low', 'medium', 'high', 'critical')",
            name="ck_change_proposal_risk",
        ),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'under_analysis', "
            "'validation_required', 'ready_for_decision', 'approved', "
            "'rejected', 'deferred')",
            name="ck_change_proposal_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    proposed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    sponsor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    desired_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    risk: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    affected_entities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChangeEvidenceModel(Base):
    __tablename__ = "change_evidence"
    __table_args__ = (
        UniqueConstraint(
            "owner_type", "owner_id", "artifact_id", name="uq_change_evidence_owner_artifact"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    owner_type: Mapped[str] = mapped_column(String(40), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    artifact_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChangeSetModel(Base):
    __tablename__ = "change_sets"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version", name="uq_change_set_proposal_version"),
        CheckConstraint("version > 0", name="ck_change_set_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    operations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class ChangeImpactAssessmentModel(Base):
    __tablename__ = "change_impact_assessments"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version", name="uq_change_impact_proposal_version"),
        CheckConstraint("version > 0", name="ck_change_impact_version_positive"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_change_impact_confidence",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_sets.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    assessed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    direct_impacts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    indirect_impacts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    required_approval_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    required_tests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    estimated_blast_radius: Mapped[str] = mapped_column(String(20), nullable=False)
    rollback_complexity: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class ChangeValidationPlanModel(Base):
    __tablename__ = "change_validation_plans"
    __table_args__ = (
        UniqueConstraint("proposal_id", "version", name="uq_change_validation_proposal_version"),
        CheckConstraint("version > 0", name="ck_change_validation_version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    impact_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_impact_assessments.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    requirements: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    rollback_evidence_required: Mapped[bool] = mapped_column(nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class ChangeDecisionModel(Base):
    __tablename__ = "change_decisions"
    __table_args__ = (
        UniqueConstraint("proposal_id", name="uq_change_decision_proposal"),
        CheckConstraint(
            "decision IN ('approved', 'rejected', 'deferred')",
            name="ck_change_decision_value",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_proposals.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    change_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_sets.id", ondelete="RESTRICT"), nullable=False
    )
    impact_assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_impact_assessments.id", ondelete="RESTRICT"), nullable=False
    )
    validation_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("change_validation_plans.id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    decided_by: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    validation_results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
