from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from ai_enterprise.domain.hashing import hash_json

ALLOWED_MESSAGE_TYPES = {
    "analysis_result",
    "question",
    "evidence_request",
    "candidate_proposal",
    "review_finding",
    "handoff",
    "escalation",
}
FORBIDDEN_MEMORY_TYPES = {"chain_of_thought", "raw_transcript", "secret", "speculation"}


class ToolGatewayPort(Protocol):
    def invoke(self, request: dict[str, object]) -> dict[str, object]: ...


class ToolInvocationDeniedOrFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class GatewayBackedTool:
    gateway: ToolGatewayPort
    runtime_session_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    tool_key: str
    scope_type: str
    scope_id: UUID

    def run(self, **arguments: object) -> dict[str, object]:
        result = self.gateway.invoke(
            {
                "runtime_session_id": self.runtime_session_id,
                "agent_profile_version_id": self.agent_profile_version_id,
                "assignment_id": self.assignment_id,
                "tool_key": self.tool_key,
                "arguments": arguments,
                "scope_type": self.scope_type,
                "scope_id": self.scope_id,
            }
        )
        if result.get("status") != "succeeded":
            raise ToolInvocationDeniedOrFailed(str(result.get("error", "TOOL-INVOCATION-FAILED")))
        output = result.get("output")
        if not isinstance(output, dict):
            raise ToolInvocationDeniedOrFailed("TOOL-OUTPUT-CONTRACT-VIOLATION")
        return output


@dataclass(frozen=True)
class CrewMessage:
    crew_run_id: UUID
    sender_agent_version_id: UUID
    recipient_agent_version_id: UUID
    message_type: str
    payload: dict[str, object]
    classification: str
    created_at: datetime = datetime.now(UTC)

    def __post_init__(self) -> None:
        if self.message_type not in ALLOWED_MESSAGE_TYPES:
            raise ValueError("CREW-MESSAGE-TYPE-DENIED")
        if self.sender_agent_version_id == self.recipient_agent_version_id:
            raise ValueError("CREW-SELF-HANDOFF-DENIED")

    @property
    def payload_hash(self) -> str:
        return hash_json(self.payload)


@dataclass(frozen=True)
class MemoryEntry:
    memory_type: str
    scope_type: str
    scope_id: UUID
    content_reference: str
    classification: str
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.memory_type in FORBIDDEN_MEMORY_TYPES:
            raise ValueError("MEMORY-TYPE-DENIED")
        if self.memory_type not in {
            "session",
            "assignment",
            "project",
            "role",
            "organization",
            "artifact_evidence",
            "curated_lesson",
        }:
            raise ValueError("MEMORY-TYPE-UNKNOWN")


def redact_secrets(value: dict[str, object]) -> dict[str, object]:
    secret_markers = ("password", "secret", "token", "credential", "api_key", "private_key")
    return {
        key: "[REDACTED]" if any(marker in key.lower() for marker in secret_markers) else item
        for key, item in value.items()
    }
