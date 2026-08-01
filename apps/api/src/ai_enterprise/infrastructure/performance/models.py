from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class PerformanceEvidenceModel(Base):
    __tablename__ = "performance_evidence"
    __table_args__ = (
        UniqueConstraint("workflow_type", "workflow_id", "evidence_type", "evidence_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    workflow_type: Mapped[str] = mapped_column(String(60))
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    evidence_type: Mapped[str] = mapped_column(String(60))
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_profiles.id"))
    crew_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("crew_manifests.id"))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("agent_assignments.id"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    prompt_version: Mapped[str | None] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    evidence_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(String(64), unique=True)
    source_audit_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("audit_events.id"))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PerformanceMetricModel(Base):
    __tablename__ = "performance_metrics"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "metric_key", "evidence_set_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    metric_key: Mapped[str] = mapped_column(String(80))
    numerator: Mapped[int] = mapped_column(Integer)
    denominator: Mapped[int] = mapped_column(Integer)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    window_days: Mapped[int] = mapped_column(Integer)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(40))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AssignmentQualityModel(Base):
    __tablename__ = "assignment_quality_reports"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_assignments.id"))
    quality_band: Mapped[str] = mapped_column(String(30))
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(40))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PerformanceTrendModel(Base):
    __tablename__ = "performance_trends"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    metric_key: Mapped[str] = mapped_column(String(80))
    window_days: Mapped[int] = mapped_column(Integer)
    trend_direction: Mapped[str] = mapped_column(String(20))
    trend_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    trend_hash: Mapped[str] = mapped_column(String(64), unique=True)
    metric_ids: Mapped[list[str]] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CapabilityRecommendationModel(Base):
    __tablename__ = "capability_recommendations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profiles.id"))
    capability_key: Mapped[str] = mapped_column(String(120))
    recommended_level: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    recommendation_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recommendation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CertificationDecisionModel(Base):
    __tablename__ = "capability_certification_decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_recommendations.id")
    )
    decision: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[str] = mapped_column(String(200))
    board_role: Mapped[str] = mapped_column(String(80))
    recommendation_hash: Mapped[str] = mapped_column(String(64))
    rationale: Mapped[str] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CapabilityCertificationModel(Base):
    __tablename__ = "capability_certifications"
    __table_args__ = (UniqueConstraint("agent_profile_id", "capability_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profiles.id"))
    capability_key: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(30))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_recommendations.id")
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_certification_decisions.id")
    )
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    granted_by: Mapped[str] = mapped_column(String(200))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("capability_certifications.id")
    )


class LearningProposalModel(Base):
    __tablename__ = "performance_learning_proposals"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    proposal_type: Mapped[str] = mapped_column(String(60))
    observation: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    target_reference: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    proposal_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    proposal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    proposed_by: Mapped[str] = mapped_column(String(200))
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    review_rationale: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
