from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class EnterpriseImprovementModel(Base):
    __tablename__ = "enterprise_improvements"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    improvement_key: Mapped[str] = mapped_column(String(240), unique=True)
    category: Mapped[str] = mapped_column(String(60))
    origin: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(240))
    expected_benefit: Mapped[str] = mapped_column(Text)
    risk_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dependencies: Mapped[list[str]] = mapped_column(ARRAY(String(240)))
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    proposal_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    proposal_hash: Mapped[str] = mapped_column(String(64), unique=True)
    proposed_by: Mapped[str] = mapped_column(String(200))
    proposed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnterpriseEvolutionArtifactModel(Base):
    __tablename__ = "enterprise_evolution_artifacts"
    __table_args__ = (UniqueConstraint("artifact_type", "artifact_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    improvement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_improvements.id")
    )
    artifact_type: Mapped[str] = mapped_column(String(60))
    artifact_key: Mapped[str] = mapped_column(String(240))
    version: Mapped[str] = mapped_column(String(40))
    artifact_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    artifact_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    parent_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_evolution_artifacts.id")
    )
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnterpriseEvolutionDecisionModel(Base):
    __tablename__ = "enterprise_evolution_decisions"
    __table_args__ = (UniqueConstraint("target_type", "target_id", "target_hash", "decision"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    target_type: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    target_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[str] = mapped_column(String(200))
    board_role: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EnterpriseImprovementTransitionModel(Base):
    __tablename__ = "enterprise_improvement_transitions"
    __table_args__ = (UniqueConstraint("improvement_id", "sequence"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    improvement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enterprise_improvements.id"))
    sequence: Mapped[int] = mapped_column(Integer)
    from_state: Mapped[str | None] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    evidence_artifact_ids: Mapped[list[str]] = mapped_column(JSONB)
    evidence_set_hash: Mapped[str] = mapped_column(String(64))
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_evolution_decisions.id")
    )
    transitioned_by: Mapped[str] = mapped_column(String(200))
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
