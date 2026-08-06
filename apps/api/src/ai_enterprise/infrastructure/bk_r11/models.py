from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class BKR11EvidencePackageModel(Base):
    __tablename__ = "bk_r11_evidence_packages"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "manifest_hash"),
        Index("ix_bk_r11_evidence_packages_project_key", "project_key"),
        Index("ix_bk_r11_evidence_packages_package_id", "package_id"),
        Index("ix_bk_r11_evidence_packages_acceptance_status", "acceptance_status"),
        Index("ix_bk_r11_evidence_packages_manifest_hash", "manifest_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    package_version: Mapped[str] = mapped_column(String(120), nullable=False)
    acceptance_status: Mapped[str] = mapped_column(String(80), nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11EvidenceArtifactModel(Base):
    __tablename__ = "bk_r11_evidence_artifacts"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "evidence_id", "artifact_hash"),
        Index("ix_bk_r11_evidence_artifacts_project_key", "project_key"),
        Index("ix_bk_r11_evidence_artifacts_package_id", "package_id"),
        Index("ix_bk_r11_evidence_artifacts_evidence_id", "evidence_id"),
        Index("ix_bk_r11_evidence_artifacts_evidence_type", "evidence_type"),
        Index("ix_bk_r11_evidence_artifacts_classification", "classification"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(220), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source_system: Mapped[str] = mapped_column(String(160), nullable=False)
    classification: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11AuditRecordModel(Base):
    __tablename__ = "bk_r11_audit_records"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "audit_record_id", "record_hash"),
        Index("ix_bk_r11_audit_records_project_key", "project_key"),
        Index("ix_bk_r11_audit_records_package_id", "package_id"),
        Index("ix_bk_r11_audit_records_stream_id", "stream_id"),
        Index("ix_bk_r11_audit_records_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    audit_record_id: Mapped[str] = mapped_column(String(260), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(220), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11CoverageReportModel(Base):
    __tablename__ = "bk_r11_coverage_reports"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "coverage_hash"),
        Index("ix_bk_r11_coverage_reports_project_key", "project_key"),
        Index("ix_bk_r11_coverage_reports_package_id", "package_id"),
        Index("ix_bk_r11_coverage_reports_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    coverage_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11IntegrityReportModel(Base):
    __tablename__ = "bk_r11_integrity_reports"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "integrity_hash"),
        Index("ix_bk_r11_integrity_reports_project_key", "project_key"),
        Index("ix_bk_r11_integrity_reports_package_id", "package_id"),
        Index("ix_bk_r11_integrity_reports_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11PackageEventModel(Base):
    __tablename__ = "bk_r11_package_events"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "event_id"),
        Index("ix_bk_r11_package_events_project_key", "project_key"),
        Index("ix_bk_r11_package_events_package_id", "package_id"),
        Index("ix_bk_r11_package_events_event_type", "event_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    event_id: Mapped[str] = mapped_column(String(260), nullable=False)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11ArchivePublicationModel(Base):
    __tablename__ = "bk_r11_archive_publications"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "publication_hash"),
        Index("ix_bk_r11_archive_publications_project_key", "project_key"),
        Index("ix_bk_r11_archive_publications_package_id", "package_id"),
        Index("ix_bk_r11_archive_publications_archive_backend", "archive_backend"),
        Index("ix_bk_r11_archive_publications_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    archive_backend: Mapped[str] = mapped_column(String(80), nullable=False)
    archive_uri: Mapped[str] = mapped_column(String(600), nullable=False)
    archive_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    publication_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BKR11ArchiveVerificationModel(Base):
    __tablename__ = "bk_r11_archive_verifications"
    __table_args__ = (
        UniqueConstraint("project_key", "package_id", "verification_hash"),
        Index("ix_bk_r11_archive_verifications_project_key", "project_key"),
        Index("ix_bk_r11_archive_verifications_package_id", "package_id"),
        Index("ix_bk_r11_archive_verifications_archive_backend", "archive_backend"),
        Index("ix_bk_r11_archive_verifications_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_key: Mapped[str] = mapped_column(String(160), nullable=False)
    package_id: Mapped[str] = mapped_column(String(220), nullable=False)
    archive_backend: Mapped[str] = mapped_column(String(80), nullable=False)
    archive_uri: Mapped[str] = mapped_column(String(600), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    verification_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
