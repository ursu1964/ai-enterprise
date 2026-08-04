import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class KnowledgeSourceModel(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (UniqueConstraint("source_type", "source_id", "source_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    source_hash: Mapped[str] = mapped_column(String(64))
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    classification: Mapped[str] = mapped_column(String(30))
    trust_level: Mapped[str] = mapped_column(String(30))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeCandidateModel(Base):
    __tablename__ = "knowledge_candidates"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    candidate_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    classification: Mapped[str] = mapped_column(String(30))
    confidence_band: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    candidate_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    candidate_hash: Mapped[str] = mapped_column(String(64), unique=True)
    proposed_by_actor_type: Mapped[str] = mapped_column(String(30))
    proposed_by_actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    runtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_runtime_sessions.id")
    )
    extraction_skill_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skill_versions.id")
    )
    validation_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeCandidateEvidenceModel(Base):
    __tablename__ = "knowledge_candidate_evidence"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_candidates.id"), primary_key=True
    )
    knowledge_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id"), primary_key=True
    )
    relation: Mapped[str] = mapped_column(String(40), primary_key=True)
    evidence_locator: Mapped[dict[str, Any]] = mapped_column(JSONB)
    quotation_hash: Mapped[str | None] = mapped_column(String(64))


class KnowledgePromotionReviewModel(Base):
    __tablename__ = "knowledge_promotion_reviews"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_candidates.id"))
    decision: Mapped[str] = mapped_column(String(30))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    candidate_hash: Mapped[str] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(40))
    comments: Mapped[str | None] = mapped_column(Text)
    review_scope: Mapped[str] = mapped_column(String(40), default="project")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeItemModel(Base):
    __tablename__ = "knowledge_items"
    __table_args__ = (UniqueConstraint("knowledge_key", "version_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    knowledge_key: Mapped[str] = mapped_column(String(240))
    version_number: Mapped[int] = mapped_column(Integer)
    item_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    classification: Mapped[str] = mapped_column(String(30))
    trust_level: Mapped[str] = mapped_column(String(30))
    temporal_status: Mapped[str] = mapped_column(String(30))
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    evidence_manifest_hash: Mapped[str] = mapped_column(String(64))
    knowledge_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    knowledge_hash: Mapped[str] = mapped_column(String(64), unique=True)
    promoted_from_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_candidates.id")
    )
    promotion_review_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_promotion_reviews.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeItemVersionModel(Base):
    __tablename__ = "knowledge_item_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_items.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    version_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeSupersessionModel(Base):
    __tablename__ = "knowledge_supersessions"
    superseded_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id"), primary_key=True
    )
    superseding_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id"), primary_key=True
    )
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeContradictionModel(Base):
    __tablename__ = "knowledge_contradictions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_items.id"))
    second_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_items.id"))
    contradiction_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    resolution_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeIndexVersionModel(Base):
    __tablename__ = "knowledge_index_versions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    policy_version: Mapped[str] = mapped_column(String(40))
    index_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    index_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeRetrievalSessionModel(Base):
    __tablename__ = "knowledge_retrieval_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runtime_sessions.id"))
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_assignments.id"))
    request_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    request_hash: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(40))
    index_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("knowledge_index_versions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeRetrievalResultModel(Base):
    __tablename__ = "knowledge_retrieval_results"
    retrieval_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_retrieval_sessions.id"), primary_key=True
    )
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_items.id"), primary_key=True
    )
    rank: Mapped[int] = mapped_column(Integer)
    lexical_score: Mapped[str] = mapped_column(String(40))
    semantic_score: Mapped[str | None] = mapped_column(String(40))
    result_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provenance_hash: Mapped[str] = mapped_column(String(64))


class KnowledgeRetrievalManifestModel(Base):
    __tablename__ = "knowledge_retrieval_manifests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    retrieval_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_retrieval_sessions.id"), unique=True
    )
    context_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_context_manifests.id")
    )
    manifest_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AeirModelVersionModel(Base):
    __tablename__ = "aeir_model_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number"),
        CheckConstraint("version_number > 0", name="ck_aeir_model_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    model_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    model_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirObjectModel(Base):
    __tablename__ = "aeir_objects"
    __table_args__ = (
        UniqueConstraint("model_version_id", "object_id"),
        UniqueConstraint("model_version_id", "id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_aeir_object_confidence"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    object_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AeirRelationshipModel(Base):
    __tablename__ = "aeir_relationships"
    __table_args__ = (
        UniqueConstraint("model_version_id", "relationship_id"),
        ForeignKeyConstraint(
            ("model_version_id", "source_object_id"),
            ("aeir_objects.model_version_id", "aeir_objects.id"),
        ),
        ForeignKeyConstraint(
            ("model_version_id", "target_object_id"),
            ("aeir_objects.model_version_id", "aeir_objects.id"),
        ),
        CheckConstraint(
            "source_object_id <> target_object_id", name="ck_aeir_relationship_distinct"
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    relationship_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    target_object_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    relationship_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AeirSourceObjectModel(Base):
    __tablename__ = "aeir_source_objects"
    __table_args__ = (
        UniqueConstraint("storage_provider", "bucket", "object_key"),
        CheckConstraint("size_bytes >= 0", name="ck_aeir_source_size_nonnegative"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    storage_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    bucket: Mapped[str] = mapped_column(String(200), nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirChangeEventModel(Base):
    __tablename__ = "aeir_change_events"
    __table_args__ = (UniqueConstraint("project_id", "sequence"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
