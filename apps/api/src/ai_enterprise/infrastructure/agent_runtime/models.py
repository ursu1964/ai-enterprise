import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ai_enterprise.infrastructure.database.models import Base


class SkillModel(Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("organization_id", "skill_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    skill_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SkillVersionModel(Base):
    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("skill_id", "version_number"),
        UniqueConstraint("skill_id", "skill_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    skill_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    skill_hash: Mapped[str] = mapped_column(String(64))
    approval_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CapabilitySkillBindingModel(Base):
    __tablename__ = "capability_skill_bindings"
    capability_key: Mapped[str] = mapped_column(
        ForeignKey("capabilities.capability_key"), primary_key=True
    )
    skill_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skill_versions.id"), primary_key=True
    )
    binding_status: Mapped[str] = mapped_column(String(30))
    policy_version: Mapped[str] = mapped_column(String(40))
    priority: Mapped[int] = mapped_column(Integer, default=100)


class ToolDefinitionModel(Base):
    __tablename__ = "tool_definitions"
    tool_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    tool_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    tool_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelDeploymentModel(Base):
    __tablename__ = "model_deployments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("organizations.id"))
    provider_key: Mapped[str] = mapped_column(String(80))
    model_reference: Mapped[str] = mapped_column(String(200))
    deployment_class: Mapped[str] = mapped_column(String(40))
    context_window: Mapped[int] = mapped_column(Integer)
    supports_tools: Mapped[bool] = mapped_column(Boolean)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean)
    maximum_data_classification: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30))
    metadata_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    health_document: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRoutingPolicyModel(Base):
    __tablename__ = "model_routing_policies"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    version: Mapped[str] = mapped_column(String(40))
    policy_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    policy_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30))


class PromptRegistryModel(Base):
    __tablename__ = "prompt_registries"
    __table_args__ = (UniqueConstraint("organization_id", "prompt_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    prompt_key: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(240))
    owner: Mapped[str] = mapped_column(String(200))
    department: Mapped[str] = mapped_column(String(120))
    applicable_crew: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PromptVersionModel(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("prompt_id", "version_number"),
        UniqueConstraint("prompt_id", "prompt_hash"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    prompt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prompt_registries.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    prompt_layers: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    policy_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    approval_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRuntimeSpecificationModel(Base):
    __tablename__ = "agent_runtime_specifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profiles.id"))
    agent_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_profile_versions.id")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_assignments.id"))
    role_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role_versions.id"))
    specification_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    configuration_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRuntimeSessionModel(Base):
    __tablename__ = "agent_runtime_sessions"
    __table_args__ = (UniqueConstraint("workflow_type", "workflow_run_id", "attempt_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String(100))
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    scope_type: Mapped[str] = mapped_column(String(40))
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    agent_profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_profiles.id"))
    agent_profile_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_profile_versions.id")
    )
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_assignments.id"))
    role_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role_versions.id"))
    runtime_specification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runtime_specifications.id")
    )
    runtime_specification_hash: Mapped[str] = mapped_column(String(64))
    context_manifest_hash: Mapped[str | None] = mapped_column(String(64))
    selected_model_deployment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("model_deployments.id")
    )
    status: Mapped[str] = mapped_column(String(30))
    attempt_number: Mapped[int] = mapped_column(Integer)
    counters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContextManifestModel(Base):
    __tablename__ = "agent_context_manifests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runtime_sessions.id"), unique=True
    )
    policy_version: Mapped[str] = mapped_column(String(80))
    manifest_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    manifest_hash: Mapped[str] = mapped_column(String(64), unique=True)
    total_tokens: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolInvocationModel(Base):
    __tablename__ = "tool_invocations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runtime_sessions.id"))
    tool_key: Mapped[str] = mapped_column(String(160))
    tool_version: Mapped[str] = mapped_column(String(40))
    input_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    input_hash: Mapped[str] = mapped_column(String(64))
    authorization_decision: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30))
    output_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    error_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelInvocationModel(Base):
    __tablename__ = "model_invocations"
    __table_args__ = (UniqueConstraint("runtime_session_id", "invocation_number"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runtime_sessions.id"))
    model_deployment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_deployments.id"))
    invocation_number: Mapped[int] = mapped_column(Integer)
    prompt_manifest_hash: Mapped[str] = mapped_column(String(64))
    context_manifest_hash: Mapped[str] = mapped_column(String(64))
    input_token_count: Mapped[int | None] = mapped_column(Integer)
    output_token_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    finish_reason: Mapped[str | None] = mapped_column(String(60))
    response_hash: Mapped[str | None] = mapped_column(String(64))
    error_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentOutputValidationModel(Base):
    __tablename__ = "agent_output_validations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runtime_sessions.id"))
    attempt_number: Mapped[int] = mapped_column(Integer)
    validation_document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output_document: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    valid: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentEscalationModel(Base):
    __tablename__ = "agent_escalations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    runtime_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runtime_sessions.id"))
    reason_code: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB)
    recommended_action: Mapped[str] = mapped_column(Text)
    required_human_role: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
