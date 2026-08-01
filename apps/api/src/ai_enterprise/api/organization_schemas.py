import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CommandMetadata(BaseModel):
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    causation_id: uuid.UUID | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_version: int | None = Field(default=None, ge=0)


class CreateOrganizationRequest(CommandMetadata):
    organization_key: str
    name: str
    policy_set_id: uuid.UUID


class CreateUnitRequest(CommandMetadata):
    unit_key: str
    name: str
    purpose: str
    parent_unit_id: uuid.UUID | None = None


class CreateRoleRequest(CommandMetadata):
    role_key: str
    name: str
    role_document: dict[str, Any]


class CreateVersionRequest(CommandMetadata):
    document: dict[str, Any]


class CreateAgentRequest(CommandMetadata):
    home_unit_id: uuid.UUID
    agent_key: str
    display_name: str


class CreateAssignmentRequest(CommandMetadata):
    agent_profile_version_id: uuid.UUID
    role_version_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    granted_capabilities: list[str] = Field(default_factory=list)
    denied_capabilities: list[str] = Field(default_factory=list)
    valid_from: datetime
    valid_until: datetime | None = None
    assignment_document: dict[str, Any] = Field(default_factory=dict)


class TransitionRequest(CommandMetadata):
    reason: str | None = None


class AuthorityEvaluationRequest(BaseModel):
    actor_id: uuid.UUID
    capability: str
    scope_type: str
    scope_id: uuid.UUID
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class AuthorityEvaluationResponse(BaseModel):
    allowed: bool
    decision: str
    reasons: list[dict[str, str]]
    assignment_id: uuid.UUID | None = None
    agent_profile_version_id: uuid.UUID | None = None
    role_version_id: uuid.UUID | None = None


class ComposeCrewRequest(BaseModel):
    workflow_type: str
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    policy_version: str
    organization_id: uuid.UUID | None = None
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class OrmResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class OrganizationResponse(OrmResponse):
    organization_key: str
    name: str
    status: str
    policy_set_id: uuid.UUID
    version: int


class UnitResponse(OrmResponse):
    organization_id: uuid.UUID
    parent_unit_id: uuid.UUID | None
    unit_key: str
    name: str
    purpose: str
    status: str


class RoleVersionResponse(OrmResponse):
    role_id: uuid.UUID
    version_number: int
    role_document: dict[str, Any]
    role_hash: str
    status: str


class RoleResponse(OrmResponse):
    organization_id: uuid.UUID
    role_key: str
    name: str
    current_version_id: uuid.UUID | None
    status: str


class AgentVersionResponse(OrmResponse):
    agent_profile_id: uuid.UUID
    version_number: int
    configuration_document: dict[str, Any]
    configuration_hash: str
    approval_status: str


class AgentResponse(OrmResponse):
    organization_id: uuid.UUID
    home_unit_id: uuid.UUID
    agent_key: str
    display_name: str
    status: str
    current_version_id: uuid.UUID | None
    state_version: int


class AssignmentResponse(OrmResponse):
    organization_id: uuid.UUID
    agent_profile_id: uuid.UUID
    agent_profile_version_id: uuid.UUID
    role_version_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    status: str
    granted_capabilities: list[str]
    denied_capabilities: list[str]
    valid_from: datetime
    valid_until: datetime | None
    assignment_hash: str


class CrewManifestResponse(OrmResponse):
    organization_id: uuid.UUID
    workflow_type: str
    project_id: uuid.UUID
    artifact_id: uuid.UUID
    policy_version: str
    manifest_document: dict[str, Any]
    manifest_hash: str
