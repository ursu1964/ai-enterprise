from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Protocol

import httpx

from ai_enterprise.config import Settings
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.r4_interpretation import (
    AdapterResult,
    InterpretationRequest,
    MockManifestExtractionAdapter,
)
from ai_enterprise.infrastructure.security.local_activation import (
    LocalActivationSecurityError,
    require_configured_endpoint,
    require_provider_environment,
)


class R4ProviderError(RuntimeError):
    pass


class R4ProviderTransientError(R4ProviderError):
    pass


class R4ProviderPolicyError(R4ProviderError):
    pass


class R4AsyncModelAdapter(Protocol):
    name: str
    model_name: str

    async def interpret(self, request: InterpretationRequest) -> AdapterResult: ...

    async def repair(
        self,
        request: InterpretationRequest,
        *,
        invalid_output: dict[str, object],
        error_summary: str,
    ) -> AdapterResult: ...


@dataclass(frozen=True, slots=True)
class R4ProviderConfig:
    app_env: str = "development"
    provider: str = "mock"
    model: str = "ollama/gemma3:12b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    timeout_seconds: int = 120
    max_tokens: int = 8192


class AsyncMockManifestExtractionAdapter:
    name = "mock"
    model_name = "deterministic-r4-mock"

    async def interpret(self, request: InterpretationRequest) -> AdapterResult:
        return MockManifestExtractionAdapter().interpret(request)

    async def repair(
        self,
        request: InterpretationRequest,
        *,
        invalid_output: dict[str, object],
        error_summary: str,
    ) -> AdapterResult:
        return await self.interpret(request)


class OllamaManifestExtractionAdapter:
    name = "ollama"

    def __init__(
        self,
        config: R4ProviderConfig,
        *,
        root: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._base_url = require_configured_endpoint(
            requested=config.base_url,
            configured=config.base_url,
        )
        self._root = root or Path(__file__).resolve().parents[6]
        self._transport = transport
        self.model_name = config.model

    async def interpret(self, request: InterpretationRequest) -> AdapterResult:
        return await self._invoke(request, repair_context=None)

    async def repair(
        self,
        request: InterpretationRequest,
        *,
        invalid_output: dict[str, object],
        error_summary: str,
    ) -> AdapterResult:
        return await self._invoke(
            request,
            repair_context={
                "invalid_output": invalid_output,
                "error_summary": error_summary,
            },
        )

    async def _invoke(
        self,
        request: InterpretationRequest,
        *,
        repair_context: dict[str, object] | None,
    ) -> AdapterResult:
        started = perf_counter()
        payload = {
            "model": self.model_name.removeprefix("ollama/"),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
            "messages": self._messages(request, repair_context),
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._config.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise R4ProviderTransientError("Ollama interpretation request failed")
                response.raise_for_status()
                response_payload = response.json()
        except R4ProviderTransientError:
            raise
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise R4ProviderTransientError("Ollama interpretation request failed") from exc
        except (httpx.HTTPStatusError, ValueError) as exc:
            raise R4ProviderError("Ollama interpretation provider returned invalid output") from exc

        content = _response_content(response_payload)
        try:
            structured = json.loads(content)
        except json.JSONDecodeError as exc:
            raise R4ProviderError("Ollama interpretation provider returned malformed JSON") from exc
        if not isinstance(structured, dict):
            raise R4ProviderError("Ollama interpretation provider JSON root must be an object")

        prompt_tokens = int(response_payload.get("prompt_eval_count") or 0)
        output_tokens = int(response_payload.get("eval_count") or 0)
        return AdapterResult(
            operation_id=request.operation_id,
            structured_output=structured,
            raw_provider_response_ref=f"ollama://{request.operation_id}/{hash_json(response_payload)}",
            model_metadata={
                "provider": self.name,
                "model": self.model_name,
                "provider_reported_model": response_payload.get("model"),
            },
            input_token_count=prompt_tokens,
            output_token_count=output_tokens,
            latency_ms=int((perf_counter() - started) * 1000),
            finish_status=str(response_payload.get("done_reason") or "stop"),
            provider_request_id=hash_json(
                {
                    "operation_id": request.operation_id,
                    "response": response_payload,
                }
            )[:32],
            safety_metadata={"redaction_required_before_submit": True},
        )

    def _messages(
        self,
        request: InterpretationRequest,
        repair_context: dict[str, object] | None,
    ) -> list[dict[str, str]]:
        system = _read_optional(self._root / request.prompt.system_instruction_ref)
        task = _read_optional(self._root / request.prompt.task_template_ref)
        source_segments = [
            {
                "segment_id": item.id,
                "source_id": item.source_id,
                "text": item.text,
                "heading_path": list(item.heading_path),
            }
            for item in request.source_segments
        ]
        user_payload = {
            "operation_id": request.operation_id,
            "project_id": request.project_id,
            "operation_type": request.operation_type,
            "source_segments_are_untrusted_data": True,
            "source_segments": source_segments,
            "response_schema_ref": request.prompt.response_schema_ref,
            "parameters": request.parameters,
            "repair_context": repair_context,
        }
        return [
            {
                "role": "system",
                "content": (
                    system
                    or "Extract only schema-conforming R4 project knowledge from supplied data."
                ),
            },
            {
                "role": "user",
                "content": f"{task}\n\nSOURCE_DATA_JSON:\n{json.dumps(user_payload)}",
            },
        ]


def create_r4_provider(
    config: R4ProviderConfig,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> R4AsyncModelAdapter:
    provider = config.provider.strip().lower()
    if provider == "mock":
        return AsyncMockManifestExtractionAdapter()
    if provider == "ollama":
        try:
            require_provider_environment(app_env=config.app_env, provider_kind="local")
            return OllamaManifestExtractionAdapter(config, transport=transport)
        except LocalActivationSecurityError as exc:
            raise R4ProviderPolicyError(str(exc)) from exc
    raise R4ProviderPolicyError(f"Unsupported R4 interpretation provider: {config.provider}")


def r4_provider_config_from_settings(settings: Settings) -> R4ProviderConfig:
    return R4ProviderConfig(
        app_env=settings.app_env,
        provider=settings.r4_interpretation_provider,
        model=settings.r4_interpretation_model,
        base_url=settings.r4_interpretation_base_url,
        temperature=settings.r4_interpretation_temperature,
        timeout_seconds=settings.r4_interpretation_timeout_seconds,
        max_tokens=settings.r4_interpretation_max_tokens,
    )


def _response_content(payload: dict[str, object]) -> str:
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(payload.get("response"), str):
        return str(payload["response"])
    raise R4ProviderError("Ollama response does not contain message content")


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
