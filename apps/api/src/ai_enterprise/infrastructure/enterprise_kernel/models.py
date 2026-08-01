import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class EnterpriseResourceModel(Base):
    __tablename__ = "enterprise_resources"
    __table_args__ = (
        UniqueConstraint("organization_id", "resource_key", name="uq_enterprise_resource_key"),
        UniqueConstraint("id", "version", name="uq_enterprise_resource_identity_version"),
        CheckConstraint("version > 0", name="ck_enterprise_resource_version_positive"),
        CheckConstraint(
            "state IN ('registered', 'active', 'suspended', 'retired')",
            name="ck_enterprise_resource_state",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_key: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    access_policy_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    governance_policy_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    retention_policy_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    semantic_relations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    resource_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    registered_by: Mapped[str] = mapped_column(String(200), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class EnterpriseResourceAuditModel(Base):
    __tablename__ = "enterprise_resource_audit"
    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "event_type",
            "payload_hash",
            name="uq_enterprise_resource_audit_payload",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str | None] = mapped_column(Text)
    signature_key_id: Mapped[str | None] = mapped_column(String(200))


class EnterpriseScheduleModel(Base):
    __tablename__ = "enterprise_schedules"
    __table_args__ = (
        UniqueConstraint("organization_id", "schedule_key", name="uq_enterprise_schedule_key"),
        CheckConstraint(
            "priority >= 0 AND priority <= 100", name="ck_enterprise_schedule_priority"
        ),
        CheckConstraint(
            "state IN ('queued', 'blocked', 'dispatchable', 'cancelled')",
            name="ck_enterprise_schedule_state",
        ),
        CheckConstraint(
            "target_resource_version > 0",
            name="ck_enterprise_schedule_target_version_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    schedule_key: Mapped[str] = mapped_column(String(200), nullable=False)
    work_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    target_resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_resource_version: Mapped[int] = mapped_column(Integer, nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    required_approval_gate_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    capability_requirements: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    resource_claims: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    scheduled_by: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
