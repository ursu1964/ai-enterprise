from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

RUNTIME_TRANSITIONS = {
    "created": {"authorized", "escalated", "cancelled"},
    "authorized": {"context_assembling", "escalated"},
    "context_assembling": {"context_ready", "escalated", "failed"},
    "context_ready": {"model_routing", "escalated"},
    "model_routing": {"running", "escalated", "failed"},
    "running": {"awaiting_tool", "validating_output", "timed_out", "failed"},
    "awaiting_tool": {"running", "escalated", "failed", "timed_out"},
    "validating_output": {"running", "completed", "escalated", "failed"},
    "completed": set(),
    "escalated": set(),
    "failed": set(),
    "cancelled": set(),
    "timed_out": set(),
}


@dataclass(frozen=True)
class AgentRuntimePolicy:
    version: str
    wall_clock_timeout_seconds: int
    maximum_model_calls: int
    maximum_tool_calls: int
    maximum_input_tokens: int
    maximum_output_tokens: int
    maximum_cost_units: int
    maximum_retries: int = 0
    allow_model_fallback: bool = False
    require_structured_output: bool = True


@dataclass
class AgentRuntimeSession:
    id: UUID
    workflow_type: str
    workflow_run_id: UUID
    scope_type: str
    scope_id: UUID
    agent_profile_id: UUID
    agent_profile_version_id: UUID
    assignment_id: UUID
    role_version_id: UUID
    runtime_specification_hash: str
    context_manifest_hash: str = ""
    selected_model_deployment_id: UUID | None = None
    classification: str = "internal"
    status: str = "created"
    attempt_number: int = 1
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_units: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition(self, target: str) -> None:
        if target not in RUNTIME_TRANSITIONS.get(self.status, set()):
            raise ValueError(f"RUNTIME-INVALID-TRANSITION:{self.status}->{target}")
        self.status = target

    def record_model_call(
        self, policy: AgentRuntimePolicy, *, input_tokens: int, output_tokens: int, cost: int = 0
    ) -> None:
        if self.model_calls + 1 > policy.maximum_model_calls:
            raise RuntimeLimitExceeded("RUNTIME-MODEL-CALL-LIMIT")
        if self.input_tokens + input_tokens > policy.maximum_input_tokens:
            raise RuntimeLimitExceeded("RUNTIME-INPUT-TOKEN-LIMIT")
        if self.output_tokens + output_tokens > policy.maximum_output_tokens:
            raise RuntimeLimitExceeded("RUNTIME-OUTPUT-TOKEN-LIMIT")
        if self.cost_units + cost > policy.maximum_cost_units:
            raise RuntimeLimitExceeded("RUNTIME-COST-LIMIT")
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_units += cost

    def record_tool_call(self, policy: AgentRuntimePolicy) -> None:
        if self.tool_calls + 1 > policy.maximum_tool_calls:
            raise RuntimeLimitExceeded("RUNTIME-TOOL-CALL-LIMIT")
        self.tool_calls += 1


class RuntimeLimitExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelInvocationRecord:
    id: UUID
    runtime_session_id: UUID
    model_deployment_id: UUID
    invocation_number: int
    prompt_manifest_hash: str
    context_manifest_hash: str
    status: str
    input_token_count: int | None = None
    output_token_count: int | None = None
    finish_reason: str | None = None
    response_hash: str | None = None
    error_document: dict[str, object] | None = None


@dataclass(frozen=True)
class AgentEscalation:
    id: UUID
    runtime_session_id: UUID
    reason_code: str
    summary: str
    evidence: tuple[dict[str, object], ...]
    recommended_action: str
    required_human_role: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Abstention:
    reason_code: str
    missing_inputs: tuple[str, ...]
    recommended_action: str

    def as_output(self) -> dict[str, object]:
        return {
            "status": "escalation_required",
            "reason_code": self.reason_code,
            "missing_inputs": list(self.missing_inputs),
            "recommended_action": self.recommended_action,
        }
