from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class BKR10VerificationCampaignModel(Base):
    __tablename__ = "bk_r10_verification_campaigns"
    __table_args__ = (
        UniqueConstraint("project_key", "campaign_id", "content_hash"),
        Index("ix_bk_r10_verification_campaigns_project_key", "project_key"),
        Index("ix_bk_r10_verification_campaigns_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_campaigns_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    implementation_result_id: Mapped[str] = mapped_column(String(220), nullable=False)
    verification_handoff_id: Mapped[str] = mapped_column(String(220), nullable=False)
    repository_revision: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    criticality: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationObligationModel(Base):
    __tablename__ = "bk_r10_verification_obligations"
    __table_args__ = (
        UniqueConstraint("project_key", "obligation_id", "campaign_id"),
        Index("ix_bk_r10_verification_obligations_project_key", "project_key"),
        Index("ix_bk_r10_verification_obligations_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_obligations_requirement_id", "requirement_id"),
        Index("ix_bk_r10_verification_obligations_status", "status"),
        Index("ix_bk_r10_verification_obligations_mandatory", "mandatory"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    obligation_id: Mapped[str] = mapped_column(String(220), nullable=False)
    requirement_id: Mapped[str | None] = mapped_column(String(220), nullable=True)
    obligation_type: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(120), nullable=False)
    criticality: Mapped[str] = mapped_column(String(80), nullable=False)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationProcedureModel(Base):
    __tablename__ = "bk_r10_verification_procedures"
    __table_args__ = (
        UniqueConstraint("project_key", "procedure_id", "campaign_id"),
        Index("ix_bk_r10_verification_procedures_project_key", "project_key"),
        Index("ix_bk_r10_verification_procedures_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_procedures_procedure_id", "procedure_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    procedure_id: Mapped[str] = mapped_column(String(220), nullable=False)
    procedure_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationEnvironmentModel(Base):
    __tablename__ = "bk_r10_verification_environments"
    __table_args__ = (
        UniqueConstraint("project_key", "environment_id", "campaign_id", "environment_hash"),
        Index("ix_bk_r10_verification_environments_project_key", "project_key"),
        Index("ix_bk_r10_verification_environments_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_environments_integrity_status", "integrity_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(220), nullable=False)
    environment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    environment_profile: Mapped[str] = mapped_column(String(160), nullable=False)
    repository_revision: Mapped[str] = mapped_column(String(220), nullable=False)
    integrity_status: Mapped[str] = mapped_column(String(80), nullable=False)
    environment_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationExecutionModel(Base):
    __tablename__ = "bk_r10_verification_executions"
    __table_args__ = (
        UniqueConstraint("project_key", "execution_id", "execution_hash"),
        Index("ix_bk_r10_verification_executions_project_key", "project_key"),
        Index("ix_bk_r10_verification_executions_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_executions_procedure_id", "procedure_id"),
        Index("ix_bk_r10_verification_executions_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(220), nullable=False)
    procedure_id: Mapped[str] = mapped_column(String(220), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationResultModel(Base):
    __tablename__ = "bk_r10_verification_results"
    __table_args__ = (
        UniqueConstraint("project_key", "result_id", "content_hash"),
        Index("ix_bk_r10_verification_results_project_key", "project_key"),
        Index("ix_bk_r10_verification_results_execution_id", "execution_id"),
        Index("ix_bk_r10_verification_results_verdict", "verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    result_id: Mapped[str] = mapped_column(String(220), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(220), nullable=False)
    verdict: Mapped[str] = mapped_column(String(80), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationFindingModel(Base):
    __tablename__ = "bk_r10_verification_findings"
    __table_args__ = (
        UniqueConstraint("project_key", "finding_id", "finding_hash"),
        Index("ix_bk_r10_verification_findings_project_key", "project_key"),
        Index("ix_bk_r10_verification_findings_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_findings_finding_type", "finding_type"),
        Index("ix_bk_r10_verification_findings_severity", "severity"),
        Index("ix_bk_r10_verification_findings_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(220), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    finding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10VerificationWaiverModel(Base):
    __tablename__ = "bk_r10_verification_waivers"
    __table_args__ = (
        UniqueConstraint("project_key", "waiver_id", "waiver_hash"),
        Index("ix_bk_r10_verification_waivers_project_key", "project_key"),
        Index("ix_bk_r10_verification_waivers_campaign_id", "campaign_id"),
        Index("ix_bk_r10_verification_waivers_obligation_id", "obligation_id"),
        Index("ix_bk_r10_verification_waivers_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    waiver_id: Mapped[str] = mapped_column(String(220), nullable=False)
    obligation_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    waiver_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10CoverageAssessmentModel(Base):
    __tablename__ = "bk_r10_coverage_assessments"
    __table_args__ = (
        UniqueConstraint("project_key", "coverage_assessment_id", "coverage_hash"),
        Index("ix_bk_r10_coverage_assessments_project_key", "project_key"),
        Index("ix_bk_r10_coverage_assessments_campaign_id", "campaign_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    coverage_assessment_id: Mapped[str] = mapped_column(String(220), nullable=False)
    coverage_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10CampaignVerdictModel(Base):
    __tablename__ = "bk_r10_campaign_verdicts"
    __table_args__ = (
        UniqueConstraint("project_key", "verdict_id", "verdict_hash"),
        Index("ix_bk_r10_campaign_verdicts_project_key", "project_key"),
        Index("ix_bk_r10_campaign_verdicts_campaign_id", "campaign_id"),
        Index("ix_bk_r10_campaign_verdicts_final_verdict", "final_verdict"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    verdict_id: Mapped[str] = mapped_column(String(220), nullable=False)
    final_verdict: Mapped[str] = mapped_column(String(80), nullable=False)
    verdict_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10SatisfactionRecommendationModel(Base):
    __tablename__ = "bk_r10_satisfaction_recommendations"
    __table_args__ = (
        UniqueConstraint("project_key", "recommendation_id", "recommendation_hash"),
        Index("ix_bk_r10_satisfaction_recommendations_project_key", "project_key"),
        Index("ix_bk_r10_satisfaction_recommendations_campaign_id", "campaign_id"),
        Index("ix_bk_r10_satisfaction_recommendations_requirement_id", "requirement_id"),
        Index("ix_bk_r10_satisfaction_recommendations_recommendation", "recommendation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    recommendation_id: Mapped[str] = mapped_column(String(220), nullable=False)
    requirement_id: Mapped[str] = mapped_column(String(220), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(80), nullable=False)
    recommendation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR10DomainEventModel(Base):
    __tablename__ = "bk_r10_domain_events"
    __table_args__ = (
        UniqueConstraint("project_key", "event_id"),
        Index("ix_bk_r10_domain_events_project_key", "project_key"),
        Index("ix_bk_r10_domain_events_campaign_id", "campaign_id"),
        Index("ix_bk_r10_domain_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_key: Mapped[str] = mapped_column(String(160), nullable=False)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    campaign_id: Mapped[str] = mapped_column(String(220), nullable=False)
    event_id: Mapped[str] = mapped_column(String(220), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
