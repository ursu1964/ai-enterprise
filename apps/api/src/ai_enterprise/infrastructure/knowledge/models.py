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
        UniqueConstraint("project_id", "model_sha256"),
        CheckConstraint("version_number > 0", name="ck_aeir_model_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    model_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
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
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    truth_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    object_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    relationship_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    object_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)


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
    lifecycle_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    truth_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    valid_from: Mapped[str] = mapped_column(String(10), nullable=False)
    valid_to: Mapped[str | None] = mapped_column(String(10))
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


class AeirProjectSnapshotModel(Base):
    __tablename__ = "aeir_project_snapshots"
    __table_args__ = (
        UniqueConstraint("project_id", "snapshot_id"),
        UniqueConstraint("project_id", "snapshot_sha256"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'archived')",
            name="ck_aeir_project_snapshot_status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False)
    aepm_version: Mapped[str] = mapped_column(String(20), nullable=False)
    aeir_version: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    object_versions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    snapshot_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirObjectVersionModel(Base):
    __tablename__ = "aeir_object_versions"
    __table_args__ = (
        UniqueConstraint("object_row_id", "version_number"),
        UniqueConstraint("object_version_hash"),
        CheckConstraint("version_number > 0", name="ck_aeir_object_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    object_row_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aeir_objects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    object_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirRelationshipVersionModel(Base):
    __tablename__ = "aeir_relationship_versions"
    __table_args__ = (
        UniqueConstraint("relationship_row_id", "version_number"),
        UniqueConstraint("relationship_version_hash"),
        CheckConstraint("version_number > 0", name="ck_aeir_relationship_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    relationship_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_relationships.id"), index=True
    )
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    relationship_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    relationship_version_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirEvidenceModel(Base):
    __tablename__ = "aeir_evidence"
    __table_args__ = (
        UniqueConstraint("project_id", "evidence_hash"),
        CheckConstraint(
            "object_row_id IS NOT NULL OR relationship_row_id IS NOT NULL",
            name="ck_aeir_evidence_target_present",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    object_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_objects.id"), index=True
    )
    relationship_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_relationships.id"), index=True
    )
    evidence_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    source_ref: Mapped[str | None] = mapped_column(String(120), index=True)
    evidence_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirObjectSourceLinkModel(Base):
    __tablename__ = "aeir_object_source_links"
    __table_args__ = (
        UniqueConstraint("project_id", "link_hash"),
        UniqueConstraint("object_row_id", "source_ref", "link_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    object_row_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aeir_objects.id"), index=True)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    link_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    link_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirRelationshipSourceLinkModel(Base):
    __tablename__ = "aeir_relationship_source_links"
    __table_args__ = (
        UniqueConstraint("project_id", "link_hash"),
        UniqueConstraint("relationship_row_id", "source_ref", "link_type"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    relationship_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_relationships.id"), index=True
    )
    relationship_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    link_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    link_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirValidationRuleModel(Base):
    __tablename__ = "aeir_validation_rules"
    __table_args__ = (UniqueConstraint("rule_id", "rule_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(40), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    rule_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirValidationFindingModel(Base):
    __tablename__ = "aeir_validation_findings"
    __table_args__ = (
        UniqueConstraint("snapshot_row_id", "finding_id"),
        UniqueConstraint("finding_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_project_snapshots.id"), index=True
    )
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    rule_row_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("aeir_validation_rules.id"))
    finding_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    blocking: Mapped[bool] = mapped_column(nullable=False)
    object_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    finding_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    finding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirClarificationQuestionModel(Base):
    __tablename__ = "aeir_clarification_questions"
    __table_args__ = (
        UniqueConstraint("snapshot_row_id", "question_id"),
        UniqueConstraint("question_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_project_snapshots.id"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(80), nullable=False)
    section: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    required: Mapped[bool] = mapped_column(nullable=False)
    target_object_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    question_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirClarificationAnswerModel(Base):
    __tablename__ = "aeir_clarification_answers"
    __table_args__ = (
        UniqueConstraint("question_row_id", "answer_hash"),
        UniqueConstraint("answer_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    question_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_clarification_questions.id"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    respondent_id: Mapped[str] = mapped_column(String(200), nullable=False)
    resolution: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    answer_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirDecisionModel(Base):
    __tablename__ = "aeir_decisions"
    __table_args__ = (UniqueConstraint("decision_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_project_snapshots.id"), index=True
    )
    object_id: Mapped[str | None] = mapped_column(String(64), index=True)
    decision_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200), nullable=False)
    decision_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirAiOperationModel(Base):
    __tablename__ = "aeir_ai_operations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    model_provider: Mapped[str] = mapped_column(String(200), nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_source_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    review_required: Mapped[bool] = mapped_column(nullable=False)
    operation_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    operation_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    generated_at: Mapped[str] = mapped_column(String(40), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirArtifactVersionModel(Base):
    __tablename__ = "aeir_artifact_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "artifact_type", "version_number"),
        UniqueConstraint("project_id", "artifact_hash"),
        CheckConstraint("version_number > 0", name="ck_aeir_artifact_version_positive"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_project_snapshots.id"), index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    compiler_id: Mapped[str] = mapped_column(String(120), nullable=False)
    compiler_version: Mapped[str] = mapped_column(String(40), nullable=False)
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    compilation_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    output_format: Mapped[str] = mapped_column(String(30), nullable=False)
    artifact_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AeirArtifactTraceLinkModel(Base):
    __tablename__ = "aeir_artifact_trace_links"
    __table_args__ = (
        UniqueConstraint("artifact_version_id", "artifact_section_id", "object_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    artifact_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_artifact_versions.id"), index=True
    )
    artifact_section_id: Mapped[str] = mapped_column(String(160), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    relationship_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trace_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    trace_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trace_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class R4SourceNormalizationModel(Base):
    __tablename__ = "r4_source_normalizations"
    __table_args__ = (
        UniqueConstraint("source_row_id", "normalization_version"),
        UniqueConstraint("project_id", "checksum"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    source_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_source_objects.id"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    normalization_version: Mapped[str] = mapped_column(String(40), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4SourceSegmentModel(Base):
    __tablename__ = "r4_source_segments"
    __table_args__ = (
        UniqueConstraint("normalization_id", "sequence"),
        UniqueConstraint("project_id", "segment_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    normalization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_source_normalizations.id"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    heading_path: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)


class R4PromptVersionModel(Base):
    __tablename__ = "r4_prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "prompt_version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    system_instruction_ref: Mapped[str] = mapped_column(Text, nullable=False)
    task_template_ref: Mapped[str] = mapped_column(Text, nullable=False)
    response_schema_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    prompt_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4AiOperationModel(Base):
    __tablename__ = "r4_ai_operations"
    __table_args__ = (
        UniqueConstraint("project_id", "operation_id"),
        UniqueConstraint("project_id", "operation_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    operation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_id: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    response_schema_id: Mapped[str] = mapped_column(String(120), nullable=False)
    response_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    segment_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    operation_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    operation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    review_required: Mapped[bool] = mapped_column(nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4AiUsageRecordModel(Base):
    __tablename__ = "r4_ai_usage_records"
    __table_args__ = (UniqueConstraint("operation_row_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    usage_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class R4AiOperationFailureModel(Base):
    __tablename__ = "r4_ai_operation_failures"
    __table_args__ = (UniqueConstraint("project_id", "operation_id", "retry_count"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    operation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    failure_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    final_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    error_summary: Mapped[str] = mapped_column(Text, nullable=False)
    failure_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4CandidateObjectModel(Base):
    __tablename__ = "r4_candidate_objects"
    __table_args__ = (
        UniqueConstraint("project_id", "candidate_id"),
        UniqueConstraint("project_id", "candidate_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    proposed_object_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    proposed_object_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    truth_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    candidate_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    schema_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    deterministic_validation_status: Mapped[str] = mapped_column(String(60), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4CandidateRelationshipModel(Base):
    __tablename__ = "r4_candidate_relationships"
    __table_args__ = (
        UniqueConstraint("project_id", "candidate_id"),
        UniqueConstraint("project_id", "candidate_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_candidate_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    target_candidate_ref: Mapped[str] = mapped_column(String(80), nullable=False)
    truth_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    candidate_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    schema_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class R4CandidateSourceLinkModel(Base):
    __tablename__ = "r4_candidate_source_links"
    __table_args__ = (
        UniqueConstraint("project_id", "candidate_id", "source_id", "segment_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    support_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    quoted_fragment: Mapped[str | None] = mapped_column(Text)
    link_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class R4CandidateValidationResultModel(Base):
    __tablename__ = "r4_candidate_validation_results"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    findings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class R4UncertaintyRecordModel(Base):
    __tablename__ = "r4_uncertainty_records"
    __table_args__ = (UniqueConstraint("project_id", "record_id", "record_type"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    record_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    blocking: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class R4ClarificationQuestionModel(Base):
    __tablename__ = "r4_clarification_questions"
    __table_args__ = (UniqueConstraint("project_id", "question_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    ai_operation_row_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r4_ai_operations.id"), index=True
    )
    question_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    origin_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    origin_ref: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    blocking: Mapped[bool] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    question_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class R4CandidateReviewModel(Base):
    __tablename__ = "r4_candidate_reviews"
    __table_args__ = (UniqueConstraint("project_id", "review_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    review_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    review_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    review_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4CandidatePromotionModel(Base):
    __tablename__ = "r4_candidate_promotions"
    __table_args__ = (UniqueConstraint("project_id", "candidate_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    candidate_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    canonical_object_id: Mapped[str | None] = mapped_column(String(80), index=True)
    canonical_relationship_id: Mapped[str | None] = mapped_column(String(80), index=True)
    promoted_by: Mapped[str] = mapped_column(String(200), nullable=False)
    promotion_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    promotion_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R4AiProvenanceLinkModel(Base):
    __tablename__ = "r4_ai_provenance_links"
    __table_args__ = (
        UniqueConstraint("project_id", "entity_type", "entity_id", "ai_operation_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    ai_operation_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_segment_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    derivation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    provenance_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class R4EvaluationRecordModel(Base):
    __tablename__ = "r4_evaluation_records"
    __table_args__ = (UniqueConstraint("case_id", "run_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    case_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False, index=True)
    result_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R5TransformationRunModel(Base):
    __tablename__ = "r5_transformation_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "run_hash"),
        UniqueConstraint("project_id", "plan_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("aeir_model_versions.id"), index=True
    )
    snapshot_row_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("aeir_project_snapshots.id"), index=True
    )
    source_model_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    template_pack_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_stack: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blocking_finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    run_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R5ArtifactSpecModel(Base):
    __tablename__ = "r5_artifact_specs"
    __table_args__ = (
        UniqueConstraint("transformation_run_id", "artifact_key"),
        UniqueConstraint("project_id", "artifact_spec_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    transformation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r5_transformation_runs.id"), index=True
    )
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    artifact_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_object_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_object_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    depends_on_object_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    artifact_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provenance_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    artifact_spec_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class R5GeneratedArtifactModel(Base):
    __tablename__ = "r5_generated_artifacts"
    __table_args__ = (
        UniqueConstraint("transformation_run_id", "artifact_key"),
        UniqueConstraint("project_id", "generated_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    transformation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r5_transformation_runs.id"), index=True
    )
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    artifact_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_artifact_spec_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    generated_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class R5ExportBundleModel(Base):
    __tablename__ = "r5_export_bundles"
    __table_args__ = (
        UniqueConstraint("transformation_run_id"),
        UniqueConstraint("project_id", "bundle_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    transformation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r5_transformation_runs.id"), index=True
    )
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_model_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_snapshot_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    registry_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    template_pack_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    bundle_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R5VerificationReportModel(Base):
    __tablename__ = "r5_verification_reports"
    __table_args__ = (UniqueConstraint("transformation_run_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    transformation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r5_transformation_runs.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blocking_finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6GenerationBuildModel(Base):
    __tablename__ = "r6_generation_builds"
    __table_args__ = (
        UniqueConstraint("r5_export_bundle_id", "generator_pack_id", "generator_pack_version"),
        UniqueConstraint("project_id", "build_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    r5_export_bundle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r5_export_bundles.id"), index=True
    )
    r5_export_bundle_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    generator_pack_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    generator_pack_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    artifact_count: Mapped[int] = mapped_column(Integer, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    build_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6GeneratedFileModel(Base):
    __tablename__ = "r6_generated_files"
    __table_args__ = (
        UniqueConstraint("generation_build_id", "relative_path"),
        UniqueConstraint("project_id", "file_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    file_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    artifact_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    generator_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    template_ref: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    lifecycle_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class R6ValidationReportModel(Base):
    __tablename__ = "r6_validation_reports"
    __table_args__ = (UniqueConstraint("generation_build_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    blocking_finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6LifecycleEventModel(Base):
    __tablename__ = "r6_lifecycle_events"
    __table_args__ = (
        UniqueConstraint("generation_build_id", "event_id"),
        UniqueConstraint("project_id", "event_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    build_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    to_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    policy_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6InstalledGeneratorPackModel(Base):
    __tablename__ = "r6_installed_generator_packs"
    __table_args__ = (
        UniqueConstraint("project_id", "pack_id", "version"),
        UniqueConstraint("project_id", "installation_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    installation_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    pack_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    technology_stack: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_targets: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    validation_gates: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    repository_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    pack_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    installation_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    installation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    installed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6ParallelGenerationPlanModel(Base):
    __tablename__ = "r6_parallel_generation_plans"
    __table_args__ = (
        UniqueConstraint("generation_build_id", "plan_id"),
        UniqueConstraint("project_id", "plan_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    plan_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    generator_pack_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    max_parallelism: Mapped[int] = mapped_column(Integer, nullable=False)
    lanes_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6ValidationGateRunModel(Base):
    __tablename__ = "r6_validation_gate_runs"
    __table_args__ = (
        UniqueConstraint("generation_build_id", "gate_run_id"),
        UniqueConstraint("project_id", "gate_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    gate_run_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    gate_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    command: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gate_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    gate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R6ArtifactRepositoryPublicationModel(Base):
    __tablename__ = "r6_artifact_repository_publications"
    __table_args__ = (
        UniqueConstraint("generation_build_id", "publication_id"),
        UniqueConstraint("project_id", "publication_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    publication_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    repository_kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    repository_ref: Mapped[str] = mapped_column(String(300), nullable=False)
    version_ref: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_address: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publication_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    publication_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeDeploymentModel(Base):
    __tablename__ = "r7_runtime_deployments"
    __table_args__ = (
        UniqueConstraint("r6_generation_build_id", "environment", "service_identity"),
        UniqueConstraint("project_id", "deployment_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    r6_generation_build_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r6_generation_builds.id"), index=True
    )
    deployment_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    service_identity: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    application_version: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    template_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    generator_pack_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    generator_pack_version: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    deployment_location: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    endpoint_urls: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    dependency_service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    deployment_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    deployment_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7HealthReportModel(Base):
    __tablename__ = "r7_health_reports"
    __table_args__ = (UniqueConstraint("runtime_deployment_id", "report_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    checks_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metrics_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeEventModel(Base):
    __tablename__ = "r7_runtime_events"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "event_id"),
        UniqueConstraint("project_id", "event_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    event_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    context_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_rule_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7CompatibilityReportModel(Base):
    __tablename__ = "r7_compatibility_reports"
    __table_args__ = (UniqueConstraint("runtime_deployment_id", "report_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7WorkflowInstanceModel(Base):
    __tablename__ = "r7_workflow_instances"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "workflow_instance_id", "instance_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    workflow_instance_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    workflow_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    previous_state: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    current_state: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    context_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    workflow_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    instance_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeErrorModel(Base):
    __tablename__ = "r7_runtime_errors"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "error_id"),
        UniqueConstraint("project_id", "error_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    error_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recovery_guidance: Mapped[str] = mapped_column(Text, nullable=False)
    context_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RecoveryActionModel(Base):
    __tablename__ = "r7_recovery_actions"
    __table_args__ = (
        UniqueConstraint("runtime_error_id", "recovery_id"),
        UniqueConstraint("project_id", "action_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_error_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_errors.id"), index=True
    )
    recovery_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    strategy: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    policy_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    action_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    action_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7DigitalTwinSnapshotModel(Base):
    __tablename__ = "r7_digital_twin_snapshots"
    __table_args__ = (UniqueConstraint("runtime_deployment_id", "snapshot_hash"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    snapshot_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    health_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    topology_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metrics_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    configuration_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeProviderModel(Base):
    __tablename__ = "r7_runtime_providers"
    __table_args__ = (
        UniqueConstraint("project_id", "kind", "name", "version"),
        UniqueConstraint("project_id", "provider_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    provider_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    endpoint_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    configuration_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    provider_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7PolicyEvaluationModel(Base):
    __tablename__ = "r7_policy_evaluations"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "evaluation_id"),
        UniqueConstraint("project_id", "evaluation_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    runtime_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("r7_runtime_providers.id"), nullable=True, index=True
    )
    evaluation_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    matched_policies: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    context_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluation_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    evaluation_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7EventDispatchModel(Base):
    __tablename__ = "r7_event_dispatches"
    __table_args__ = (
        UniqueConstraint("runtime_event_id", "dispatch_id"),
        UniqueConstraint("project_id", "dispatch_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_events.id"), index=True
    )
    runtime_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_providers.id"), index=True
    )
    dispatch_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subscriber_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    dispatch_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dispatch_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7DeploymentRuntimeSyncModel(Base):
    __tablename__ = "r7_deployment_runtime_syncs"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "sync_id"),
        UniqueConstraint("project_id", "sync_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    runtime_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_providers.id"), index=True
    )
    sync_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    runtime_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    sync_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeAiRequestModel(Base):
    __tablename__ = "r7_runtime_ai_requests"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "ai_request_id"),
        UniqueConstraint("project_id", "request_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    runtime_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_providers.id"), index=True
    )
    policy_evaluation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_policy_evaluations.id"), index=True
    )
    ai_request_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    context_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7PluginBindingModel(Base):
    __tablename__ = "r7_plugin_bindings"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "binding_id"),
        UniqueConstraint("project_id", "binding_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    runtime_provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_providers.id"), index=True
    )
    binding_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    plugin_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    plugin_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    compatibility_status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    requested_capabilities: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    binding_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeConfigurationSnapshotModel(Base):
    __tablename__ = "r7_runtime_configuration_snapshots"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "configuration_id"),
        UniqueConstraint("project_id", "configuration_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    configuration_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    manifest_version: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    configuration_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    feature_flags: Mapped[dict[str, bool]] = mapped_column(JSONB, nullable=False)
    sensitive_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeAuditRecordModel(Base):
    __tablename__ = "r7_runtime_audit_records"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "audit_id"),
        UniqueConstraint("project_id", "audit_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    audit_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    affected_object: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    previous_value_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_value_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    manifest_rule_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    audit_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    audit_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeTelemetryBatchModel(Base):
    __tablename__ = "r7_runtime_telemetry_batches"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "telemetry_id"),
        UniqueConstraint("project_id", "telemetry_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    telemetry_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    metrics_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trace_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    log_signatures: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    performance_indicators: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    telemetry_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    telemetry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeGovernanceTraceModel(Base):
    __tablename__ = "r7_runtime_governance_traces"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "governance_trace_id"),
        UniqueConstraint("project_id", "trace_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    governance_trace_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    runtime_action_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_rule_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    registry_rule_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    manifest_object_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    requirement_ref: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    trace_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    trace_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeSynchronizationReportModel(Base):
    __tablename__ = "r7_runtime_synchronization_reports"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "synchronization_id"),
        UniqueConstraint("project_id", "report_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    synchronization_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    findings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    observed_runtime_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R7RuntimeUpgradePlanModel(Base):
    __tablename__ = "r7_runtime_upgrade_plans"
    __table_args__ = (
        UniqueConstraint("runtime_deployment_id", "upgrade_plan_id"),
        UniqueConstraint("project_id", "plan_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runtime_deployment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_deployments.id"), index=True
    )
    synchronization_report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("r7_runtime_synchronization_reports.id"), index=True
    )
    upgrade_plan_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    blocked_by: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    steps_document: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    plan_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    plan_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R8GovernanceEvolutionRecordModel(Base):
    __tablename__ = "r8_governance_evolution_records"
    __table_args__ = (
        UniqueConstraint("project_id", "record_type", "record_id", "record_hash"),
        UniqueConstraint("project_id", "record_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    lifecycle_state: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    approval_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    parent_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    record_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R9KernelRecordModel(Base):
    __tablename__ = "r9_kernel_records"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_id", "record_type", "record_id", "record_hash"),
        UniqueConstraint("record_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    scope_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    object_identity: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    parent_record_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    record_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R10ExperienceRecordModel(Base):
    __tablename__ = "r10_experience_records"
    __table_args__ = (
        UniqueConstraint("project_id", "record_type", "record_id", "record_hash"),
        UniqueConstraint("project_id", "record_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    object_ref: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    record_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class R11IntegrationRecordModel(Base):
    __tablename__ = "r11_integration_records"
    __table_args__ = (
        UniqueConstraint("project_id", "record_type", "record_id", "record_hash"),
        UniqueConstraint("project_id", "record_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    integration_ref: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    lifecycle_state: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    health_status: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    record_document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
