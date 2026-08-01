from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
from crewai import LLM

from ai_enterprise.config import Settings
from ai_enterprise.infrastructure.security.local_activation import (
    LocalActivationSecurityError,
    require_configured_endpoint,
    require_provider_environment,
)


class RequirementsProviderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RequirementsProviderConfig:
    app_env: str = "development"
    provider: str = "ollama"
    model: str = "ollama/gemma3:12b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.1
    timeout_seconds: int = 600
    max_tokens: int = 8192


class CrewLLMProvider(Protocol):
    name: str
    model_name: str

    def create_llm(self) -> LLM: ...

    async def preflight(self) -> None: ...


class OllamaCrewLLMProvider:
    name = "ollama"

    def __init__(
        self,
        config: RequirementsProviderConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._transport = transport
        self._base_url = require_configured_endpoint(
            requested=config.base_url, configured=config.base_url
        )
        self.model_name = config.model

    def create_llm(self) -> LLM:
        return LLM(
            model=self.model_name,
            base_url=self._base_url,
            api_key="ollama",
            temperature=self._config.temperature,
            timeout=self._config.timeout_seconds,
            max_tokens=self._config.max_tokens,
        )

    async def preflight(self) -> None:
        try:
            async with httpx.AsyncClient(
                timeout=min(self._config.timeout_seconds, 10),
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise RequirementsProviderError("Ollama provider preflight failed") from exc
        expected = self.model_name.removeprefix("ollama/")
        installed = {
            item.get("name") for item in payload.get("models", []) if isinstance(item, dict)
        }
        if expected not in installed:
            raise RequirementsProviderError(f"Ollama model is not installed: {expected}")


def create_requirements_provider(
    config: RequirementsProviderConfig,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CrewLLMProvider:
    if config.provider.strip().lower() == "ollama":
        try:
            require_provider_environment(app_env=config.app_env, provider_kind="local")
            return OllamaCrewLLMProvider(config, transport=transport)
        except LocalActivationSecurityError as exc:
            raise RequirementsProviderError(str(exc)) from exc
    raise RequirementsProviderError(f"Unsupported requirements provider: {config.provider}")


def provider_config_from_settings(settings: Settings) -> RequirementsProviderConfig:
    return RequirementsProviderConfig(
        app_env=settings.app_env,
        provider=settings.requirements_llm_provider,
        model=settings.requirements_llm_model,
        base_url=settings.requirements_llm_base_url,
        temperature=settings.requirements_llm_temperature,
        timeout_seconds=settings.requirements_llm_timeout_seconds,
        max_tokens=settings.requirements_llm_max_tokens,
    )
