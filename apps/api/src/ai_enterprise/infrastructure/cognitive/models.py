from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class CognitiveRecordModel(Base):
    __tablename__ = "cognitive_records"
    __table_args__ = (UniqueConstraint("organization_id", "record_type", "record_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    record_type: Mapped[str] = mapped_column(String(60))
    record_key: Mapped[str] = mapped_column(String(240))
    version: Mapped[str] = mapped_column(String(40))
    record_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    record_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    classification: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    parent_record_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cognitive_records.id"))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CognitiveDecisionModel(Base):
    __tablename__ = "cognitive_decisions"
    __table_args__ = (UniqueConstraint("organization_id", "record_id", "decision_nonce"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cognitive_records.id"))
    record_hash: Mapped[str] = mapped_column(String(64))
    decision_nonce: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    decision: Mapped[str] = mapped_column(String(30))
    rationale: Mapped[str] = mapped_column(Text)
    decided_by: Mapped[str] = mapped_column(String(200))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CognitiveLinkModel(Base):
    __tablename__ = "cognitive_links"
    __table_args__ = (UniqueConstraint("source_record_id", "target_record_id", "relationship"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    source_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cognitive_records.id"))
    target_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cognitive_records.id"))
    relationship: Mapped[str] = mapped_column(String(60))
    link_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
