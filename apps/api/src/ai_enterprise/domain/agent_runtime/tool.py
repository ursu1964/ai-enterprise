from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json

from .enums import RegistryStatus, ToolSideEffect

PROHIBITED_AGENT_SIDE_EFFECTS = frozenset(
    {"authoritative_state_write", "human_approval_write", "production_external_effect"}
)


@dataclass(frozen=True)
class ToolDefinition:
    key: str
    version: str
    description: str
    required_capability: str
    required_permission: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effect_class: ToolSideEffect | str
    risk_level: str
    timeout_seconds: int
    status: RegistryStatus
    definition_hash: str
    argument_policy: dict[str, Any]

    def canonical_document(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "version": self.version,
            "description": self.description,
            "required_capability": self.required_capability,
            "required_permission": self.required_permission,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "side_effect_class": str(self.side_effect_class),
            "risk_level": self.risk_level,
            "timeout_seconds": self.timeout_seconds,
            "argument_policy": self.argument_policy,
        }

    def calculated_hash(self) -> str:
        return hash_json(self.canonical_document())

    @property
    def is_active(self) -> bool:
        return (
            self.status is RegistryStatus.APPROVED
            and self.definition_hash == self.calculated_hash()
            and self.timeout_seconds > 0
            and str(self.side_effect_class) not in PROHIBITED_AGENT_SIDE_EFFECTS
        )


@dataclass(frozen=True)
class ToolInvocationRequest:
    runtime_session_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    tool_key: str
    arguments: dict[str, Any]
    scope_type: str
    scope_id: UUID


@dataclass(frozen=True)
class ToolInvocationResult:
    invocation_id: UUID
    status: str
    output: dict[str, Any] | None
    output_hash: str | None
    error: dict[str, Any] | None
