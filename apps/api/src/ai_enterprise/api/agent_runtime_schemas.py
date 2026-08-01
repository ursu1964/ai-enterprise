import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RuntimeCommand(BaseModel):
    correlation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    idempotency_key: str = Field(min_length=1, max_length=200)


class CreateSkillRequest(RuntimeCommand):
    skill_key: str = Field(min_length=3, max_length=120)
    name: str = Field(min_length=3, max_length=200)
    skill_document: dict[str, Any]


class CreateSkillVersionRequest(RuntimeCommand):
    skill_document: dict[str, Any]


class RegisterToolRequest(RuntimeCommand):
    tool_key: str
    version: str
    tool_document: dict[str, Any]


class RegisterModelDeploymentRequest(RuntimeCommand):
    organization_id: uuid.UUID | None = None
    provider_key: str
    model_reference: str
    deployment_class: str = "local"
    context_window: int = Field(gt=0)
    supports_tools: bool = False
    supports_structured_output: bool = True
    maximum_data_classification: str = "internal"
    metadata_document: dict[str, Any] = Field(default_factory=dict)


class ModelHealthRequest(BaseModel):
    available: bool
    detail: str = ""


class CreateRuntimeSessionRequest(RuntimeCommand):
    workflow_type: str
    workflow_run_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    agent_profile_id: uuid.UUID
    agent_profile_version_id: uuid.UUID
    assignment_id: uuid.UUID
    role_version_id: uuid.UUID
    runtime_specification_id: uuid.UUID
    attempt_number: int = Field(default=1, ge=1)


class OrmResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SkillResponse(OrmResult):
    id: uuid.UUID
    organization_id: uuid.UUID
    skill_key: str
    name: str
    status: str
    current_version_id: uuid.UUID | None


class SkillVersionResponse(OrmResult):
    id: uuid.UUID
    skill_id: uuid.UUID
    version_number: int
    skill_document: dict[str, Any]
    skill_hash: str
    approval_status: str


class ToolResponse(OrmResult):
    tool_key: str
    version: str
    tool_document: dict[str, Any]
    tool_hash: str
    status: str


class ModelDeploymentResponse(OrmResult):
    id: uuid.UUID
    provider_key: str
    model_reference: str
    deployment_class: str
    status: str
    health_document: dict[str, Any]


class RuntimeSessionResponse(OrmResult):
    id: uuid.UUID
    workflow_type: str
    workflow_run_id: uuid.UUID
    scope_type: str
    scope_id: uuid.UUID
    agent_profile_id: uuid.UUID
    agent_profile_version_id: uuid.UUID
    assignment_id: uuid.UUID
    role_version_id: uuid.UUID
    runtime_specification_hash: str
    context_manifest_hash: str | None
    selected_model_deployment_id: uuid.UUID | None
    status: str
    attempt_number: int
    created_at: datetime
