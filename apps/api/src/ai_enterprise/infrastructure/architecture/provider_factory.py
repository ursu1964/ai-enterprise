from dataclasses import dataclass

import httpx

from ai_enterprise.infrastructure.architecture.contracts import ArchitectureModelProvider
from ai_enterprise.infrastructure.architecture.crewai_provider import (
    CrewAIOllamaArchitectureProvider,
)
from ai_enterprise.infrastructure.architecture.fake_provider import ScriptedArchitectureProvider


@dataclass(frozen=True, slots=True)
class ArchitectureProviderConfig:
    provider: str = "crewai-ollama"
    model_name: str = "ollama/gemma3:12b"
    base_url: str = "http://localhost:11434"
    temperature: float = 0.0
    timeout_seconds: int = 900
    max_tokens: int = 16384

    def __post_init__(self) -> None:
        if not self.model_name.strip() or self.timeout_seconds <= 0 or self.max_tokens <= 0:
            raise ValueError("Invalid architecture provider configuration")
        if not 0 <= self.temperature <= 1:
            raise ValueError("Architecture temperature must be between zero and one")


def create_architecture_provider(
    config: ArchitectureProviderConfig, *, scripted_outputs: list[str | Exception] | None = None
) -> ArchitectureModelProvider:
    if config.provider == "scripted":
        if scripted_outputs is None:
            raise ValueError("Scripted provider requires explicit deterministic outputs")
        return ScriptedArchitectureProvider(scripted_outputs)
    if config.provider == "crewai-ollama":
        return CrewAIOllamaArchitectureProvider(
            model_name=config.model_name,
            base_url=config.base_url,
            temperature=config.temperature,
            timeout_seconds=config.timeout_seconds,
            max_tokens=config.max_tokens,
        )
    raise ValueError(f"Unsupported architecture provider: {config.provider}")


async def architecture_provider_ready(config: ArchitectureProviderConfig) -> bool:
    if config.provider == "scripted":
        return True
    if config.provider != "crewai-ollama":
        return False
    try:
        async with httpx.AsyncClient(timeout=min(10, config.timeout_seconds)) as client:
            response = await client.get(f"{config.base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return False
    expected = config.model_name.removeprefix("ollama/")
    return expected in {
        item.get("name") for item in payload.get("models", []) if isinstance(item, dict)
    }
