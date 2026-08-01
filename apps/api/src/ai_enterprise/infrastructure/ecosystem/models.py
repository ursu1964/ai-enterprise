from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class EcosystemEntityModel(Base):
    __tablename__ = "ecosystem_entities"
    __table_args__ = (UniqueConstraint("organization_id", "entity_type", "entity_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_key: Mapped[str] = mapped_column(String(240))
    display_name: Mapped[str] = mapped_column(String(240))
    entity_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    entity_hash: Mapped[str] = mapped_column(String(64), unique=True)
    classification: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EcosystemAssetModel(Base):
    __tablename__ = "ecosystem_assets"
    __table_args__ = (UniqueConstraint("organization_id", "asset_type", "asset_key", "version"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_entities.id"))
    asset_type: Mapped[str] = mapped_column(String(60))
    asset_key: Mapped[str] = mapped_column(String(240))
    version: Mapped[str] = mapped_column(String(80))
    asset_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    asset_hash: Mapped[str] = mapped_column(String(64), unique=True)
    evidence_manifest: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(String(64))
    parent_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ecosystem_assets.id"))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EcosystemApprovalModel(Base):
    __tablename__ = "ecosystem_approvals"
    __table_args__ = (UniqueConstraint("asset_id", "asset_hash", "decision"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_assets.id"))
    asset_hash: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(30))
    decided_by: Mapped[str] = mapped_column(String(200))
    board_role: Mapped[str] = mapped_column(String(80))
    rationale: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EcosystemGatewayInvocationModel(Base):
    __tablename__ = "ecosystem_gateway_invocations"
    __table_args__ = (UniqueConstraint("organization_id", "connector_asset_id", "request_nonce"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    connector_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_assets.id"))
    contract_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_assets.id"))
    direction: Mapped[str] = mapped_column(String(20))
    operation: Mapped[str] = mapped_column(String(160))
    identity_reference: Mapped[str] = mapped_column(String(240))
    request_nonce: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_hash: Mapped[str | None] = mapped_column(String(64))
    policy_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30))
    evidence_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    invocation_hash: Mapped[str] = mapped_column(String(64), unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EcosystemEdgeModel(Base):
    __tablename__ = "ecosystem_edges"
    __table_args__ = (UniqueConstraint("source_entity_id", "target_entity_id", "relationship"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    source_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_entities.id"))
    target_entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ecosystem_entities.id"))
    relationship: Mapped[str] = mapped_column(String(60))
    edge_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    edge_hash: Mapped[str] = mapped_column(String(64), unique=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
