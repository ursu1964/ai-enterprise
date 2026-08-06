from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class R21ProjectCompilationModel(Base):
    __tablename__ = "r21_project_compilations"
    __table_args__ = (
        UniqueConstraint("project_key", "compilation_hash"),
        Index("ix_r21_project_compilations_project_key", "project_key"),
        Index("ix_r21_project_compilations_manifest_hash", "manifest_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    compilation_id: Mapped[str] = mapped_column(String(160), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_version: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    compilation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ExecutionPlanModel(Base):
    __tablename__ = "r21_execution_plans"
    __table_args__ = (
        UniqueConstraint("project_key", "execution_plan_id", "plan_hash"),
        UniqueConstraint("project_key", "plan_hash"),
        Index("ix_r21_execution_plans_project_key", "project_key"),
        Index("ix_r21_execution_plans_execution_plan_id", "execution_plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_plan_id: Mapped[str] = mapped_column(String(200), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_version: Mapped[str] = mapped_column(String(80), nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ExecutionModel(Base):
    __tablename__ = "r21_executions"
    __table_args__ = (
        UniqueConstraint("project_key", "execution_id", "execution_hash"),
        UniqueConstraint("project_key", "execution_hash"),
        Index("ix_r21_executions_project_key", "project_key"),
        Index("ix_r21_executions_execution_id", "execution_id"),
        Index("ix_r21_executions_execution_plan_id", "execution_plan_id"),
        Index("ix_r21_executions_project_state", "project_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    execution_plan_id: Mapped[str] = mapped_column(String(200), nullable=False)
    project_state: Mapped[str] = mapped_column(String(80), nullable=False)
    execution_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ExecutionCheckpointModel(Base):
    __tablename__ = "r21_execution_checkpoints"
    __table_args__ = (
        Index("ix_r21_execution_checkpoints_execution_id", "execution_id"),
        Index("ix_r21_execution_checkpoints_project_key", "project_key"),
        Index("ix_r21_execution_checkpoints_project_state", "project_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(200), nullable=False)
    project_state: Mapped[str] = mapped_column(String(80), nullable=False)
    checkpoint_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21WorkPackageRecordModel(Base):
    __tablename__ = "r21_work_packages"
    __table_args__ = (
        Index("ix_r21_work_packages_execution_id", "execution_id"),
        Index("ix_r21_work_packages_work_package_id", "work_package_id"),
        Index("ix_r21_work_packages_state", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    work_package_id: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ApprovalGateRecordModel(Base):
    __tablename__ = "r21_approval_gates"
    __table_args__ = (
        Index("ix_r21_approval_gates_execution_id", "execution_id"),
        Index("ix_r21_approval_gates_gate_id", "gate_id"),
        Index("ix_r21_approval_gates_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    gate_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    gate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ApprovalDecisionRecordModel(Base):
    __tablename__ = "r21_approval_decisions"
    __table_args__ = (
        Index("ix_r21_approval_decisions_execution_id", "execution_id"),
        Index("ix_r21_approval_decisions_gate_id", "gate_id"),
        Index("ix_r21_approval_decisions_actor_role", "actor_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    gate_id: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_id: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(120), nullable=False)
    decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21ExecutionEventRecordModel(Base):
    __tablename__ = "r21_execution_events"
    __table_args__ = (
        Index("ix_r21_execution_events_execution_id", "execution_id"),
        Index("ix_r21_execution_events_event_type", "event_type"),
        Index("ix_r21_execution_events_project_key", "project_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    checksum: Mapped[str] = mapped_column(String(80), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21EvidenceRecordModel(Base):
    __tablename__ = "r21_evidence_records"
    __table_args__ = (
        Index("ix_r21_evidence_records_execution_id", "execution_id"),
        Index("ix_r21_evidence_records_entity_id", "entity_id"),
        Index("ix_r21_evidence_records_evidence_type", "evidence_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(200), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R21IdempotencyRecordModel(Base):
    __tablename__ = "r21_idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "idempotency_key"),
        Index("ix_r21_idempotency_records_project_key", "project_key"),
        Index("ix_r21_idempotency_records_execution_id", "execution_id"),
        Index("ix_r21_idempotency_records_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scope: Mapped[str] = mapped_column(String(160), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
