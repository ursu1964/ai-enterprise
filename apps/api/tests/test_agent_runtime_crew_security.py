from uuid import uuid4

import pytest

from ai_enterprise.domain.agent_runtime.crew import (
    CrewMessage,
    GatewayBackedTool,
    MemoryEntry,
    ToolInvocationDeniedOrFailed,
    redact_secrets,
)
from ai_enterprise.infrastructure.agent_runtime.providers import CrewAIAdapter


class Gateway:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def invoke(self, request):
        self.requests.append(request)
        return self.result


def tool(gateway):
    return GatewayBackedTool(
        gateway, uuid4(), uuid4(), uuid4(), "repository.read", "project", uuid4()
    )


def test_gateway_tool_cannot_bypass_denial():
    gateway = Gateway({"status": "denied", "error": "TOOL-NOT-IN-RUNTIME-MANIFEST"})
    with pytest.raises(ToolInvocationDeniedOrFailed, match="TOOL-NOT-IN-RUNTIME-MANIFEST"):
        tool(gateway).run(path="src/main.py")
    assert gateway.requests[0]["tool_key"] == "repository.read"


def test_gateway_tool_returns_only_structured_output():
    gateway = Gateway({"status": "succeeded", "output": {"tree_hash": "abc"}})
    assert tool(gateway).run() == {"tree_hash": "abc"}


def test_messages_are_typed_hashed_and_not_self_addressed():
    sender, recipient = uuid4(), uuid4()
    message = CrewMessage(
        uuid4(), sender, recipient, "handoff", {"references": ["ARC-1"]}, "internal"
    )
    assert len(message.payload_hash) == 64
    with pytest.raises(ValueError, match="SELF-HANDOFF"):
        CrewMessage(uuid4(), sender, sender, "handoff", {}, "internal")
    with pytest.raises(ValueError, match="TYPE-DENIED"):
        CrewMessage(uuid4(), sender, recipient, "hidden_context", {}, "internal")


def test_unrestricted_private_memory_is_denied_and_secrets_redacted():
    with pytest.raises(ValueError, match="MEMORY-TYPE-DENIED"):
        MemoryEntry("chain_of_thought", "project", uuid4(), "text", "internal")
    assert redact_secrets({"branch": "main", "api_token": "sensitive"}) == {
        "branch": "main",
        "api_token": "[REDACTED]",
    }


def test_crewai_adapter_accepts_only_governed_complete_specification():
    adapter = CrewAIAdapter()
    with pytest.raises(ValueError, match="INCOMPLETE"):
        adapter.build_agent({"role": "architect"}, ())
    agent = adapter.build_agent(
        {
            "role": "architect",
            "goal": "analyze",
            "prompt_bundle": "bounded",
            "model_reference": "local",
            "maximum_iterations": 3,
        },
        (object(),),
    )
    assert agent.maximum_iterations == 3
    assert len(agent.tools) == 1
