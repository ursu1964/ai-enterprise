import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RuntimeCommand:
    correlation_id: uuid.UUID
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CreateSkill(RuntimeCommand):
    organization_id: uuid.UUID
    skill_key: str
    name: str


@dataclass(frozen=True, slots=True)
class CreateSkillVersion(RuntimeCommand):
    skill_id: uuid.UUID
    document: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ApproveSkillVersion(RuntimeCommand):
    version_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RegisterToolDefinition(RuntimeCommand):
    tool_key: str
    version: str
    document: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RegisterModelDeployment(RuntimeCommand):
    provider_key: str
    model_reference: str


@dataclass(frozen=True, slots=True)
class StartAgentRuntimeSession(RuntimeCommand):
    session_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AssembleAgentContext(RuntimeCommand):
    session_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RouteAgentModel(RuntimeCommand):
    session_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class InvokeAgentTool(RuntimeCommand):
    session_id: uuid.UUID
    tool_key: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ExecuteAgentRuntime(RuntimeCommand):
    session_id: uuid.UUID
    requested_capability: str
    workflow_input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidateAgentOutput(RuntimeCommand):
    session_id: uuid.UUID
    raw_output: str


@dataclass(frozen=True, slots=True)
class EscalateAgentSession(RuntimeCommand):
    session_id: uuid.UUID
    reason_code: str


@dataclass(frozen=True, slots=True)
class CancelAgentRuntimeSession(RuntimeCommand):
    session_id: uuid.UUID
