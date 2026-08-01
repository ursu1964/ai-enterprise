import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class OrganizationModel(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    policy_set_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrganizationalUnitModel(Base):
    __tablename__ = "organizational_units"
    __table_args__ = (UniqueConstraint("organization_id", "unit_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    parent_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizational_units.id", ondelete="RESTRICT")
    )
    unit_key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    purpose: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoleModel(Base):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "role_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    role_key: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30))


class RoleVersionModel(Base):
    __tablename__ = "role_versions"
    __table_args__ = (
        UniqueConstraint("role_id", "version_number"),
        UniqueConstraint("role_id", "role_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    version_number: Mapped[int] = mapped_column(Integer)
    role_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    role_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CapabilityModel(Base):
    __tablename__ = "capabilities"
    capability_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    category: Mapped[str] = mapped_column(String(60))
    description: Mapped[str] = mapped_column(Text)
    human_only: Mapped[bool] = mapped_column(Boolean, default=False)
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    capability_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(40))


class AgentProfileModel(Base):
    __tablename__ = "agent_profiles"
    __table_args__ = (UniqueConstraint("organization_id", "agent_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    home_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizational_units.id", ondelete="RESTRICT")
    )
    agent_key: Mapped[str] = mapped_column(String(100))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    state_version: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentProfileVersionModel(Base):
    __tablename__ = "agent_profile_versions"
    __table_args__ = (
        UniqueConstraint("agent_profile_id", "version_number"),
        UniqueConstraint("agent_profile_id", "configuration_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_profiles.id", ondelete="RESTRICT")
    )
    version_number: Mapped[int] = mapped_column(Integer)
    configuration_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    configuration_hash: Mapped[str] = mapped_column(String(64))
    approval_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentAssignmentModel(Base):
    __tablename__ = "agent_assignments"
    __table_args__ = (
        Index(
            "ix_agent_assignments_active_scope",
            "agent_profile_id",
            "scope_type",
            "scope_id",
            "status",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_profiles.id", ondelete="RESTRICT")
    )
    agent_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_profile_versions.id", ondelete="RESTRICT")
    )
    role_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("role_versions.id", ondelete="RESTRICT")
    )
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30))
    granted_capabilities: Mapped[list[str]] = mapped_column(JSONB)
    denied_capabilities: Mapped[list[str]] = mapped_column(JSONB)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    assignment_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    assignment_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CrewManifestModel(Base):
    __tablename__ = "crew_manifests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workflow_type: Mapped[str] = mapped_column(String(80))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    artifact_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    policy_version: Mapped[str] = mapped_column(String(80))
    manifest_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationalDecisionModel(Base):
    __tablename__ = "organizational_decisions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    event_type: Mapped[str] = mapped_column(String(150), index=True)
    actor_principal: Mapped[str] = mapped_column(String(200))
    agent_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    profile_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    role_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    capability: Mapped[str | None] = mapped_column(String(120))
    scope_type: Mapped[str | None] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decision: Mapped[str] = mapped_column(String(40))
    policy_versions: Mapped[dict[str, Any]] = mapped_column(JSONB)
    configuration_hashes: Mapped[list[str]] = mapped_column(JSONB)
    correlation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    causation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
