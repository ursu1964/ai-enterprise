from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from urllib.request import Request, urlopen

from ai_enterprise.domain.agent_runtime.models import ModelGenerationResult


@dataclass(frozen=True)
class OllamaModelProvider:
    endpoint: str
    timeout_seconds: float = 120.0
    opener: Callable[..., object] = urlopen

    def generate(
        self,
        *,
        model_reference: str,
        messages: tuple[dict[str, object], ...],
        tools: tuple[dict[str, object], ...],
        output_schema: dict[str, object],
        runtime_limits: dict[str, int],
    ) -> ModelGenerationResult:
        payload = json.dumps(
            {
                "model": model_reference,
                "messages": messages,
                "tools": tools,
                "format": output_schema,
                "stream": False,
            }
        ).encode()
        request = Request(
            f"{self.endpoint.rstrip('/')}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = min(
            float(runtime_limits.get("wall_clock_timeout_seconds", int(self.timeout_seconds))),
            self.timeout_seconds,
        )
        response = self.opener(request, timeout=timeout)
        body = json.loads(response.read().decode("utf-8"))  # type: ignore[attr-defined]
        content = body.get("message", {}).get("content")
        if not isinstance(content, str):
            raise RuntimeError("OLLAMA-INVALID-RESPONSE")
        return ModelGenerationResult(
            output=content,
            input_token_count=int(body.get("prompt_eval_count", 0)),
            output_token_count=int(body.get("eval_count", 0)),
            finish_reason=str(body.get("done_reason", "stop")),
        )


@dataclass(frozen=True)
class GovernedCrewAIAgent:
    role: str
    goal: str
    backstory: str
    tools: tuple[object, ...]
    model_reference: str
    maximum_iterations: int


class CrewAIAdapter:
    """Maps already-governed specifications; it never resolves authority itself."""

    def build_agent(
        self, specification: dict[str, object], gateway_tools: tuple[object, ...]
    ) -> GovernedCrewAIAgent:
        required = {"role", "goal", "prompt_bundle", "model_reference", "maximum_iterations"}
        if not required.issubset(specification):
            raise ValueError("CREWAI-RUNTIME-SPECIFICATION-INCOMPLETE")
        maximum_iterations = specification["maximum_iterations"]
        if not isinstance(maximum_iterations, int):
            raise ValueError("CREWAI-RUNTIME-LIMIT-INVALID")
        return GovernedCrewAIAgent(
            role=str(specification["role"]),
            goal=str(specification["goal"]),
            backstory=str(specification["prompt_bundle"]),
            tools=gateway_tools,
            model_reference=str(specification["model_reference"]),
            maximum_iterations=maximum_iterations,
        )
