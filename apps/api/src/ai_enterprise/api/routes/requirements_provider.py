from fastapi import APIRouter, HTTPException

from ai_enterprise.api.dependencies import SettingsDependency
from ai_enterprise.infrastructure.requirements_llm.provider import (
    RequirementsProviderError,
    create_requirements_provider,
    provider_config_from_settings,
)

router = APIRouter(prefix="/requirements-provider", tags=["requirements-provider"])


@router.get("/readiness")
async def requirements_provider_readiness(settings: SettingsDependency) -> dict[str, str]:
    if settings.requirements_crew_adapter.strip().lower() == "deterministic":
        return {"status": "ready", "adapter": "deterministic", "provider": "none"}
    try:
        provider = create_requirements_provider(provider_config_from_settings(settings))
        await provider.preflight()
    except RequirementsProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ready", "adapter": "crewai", "provider": provider.name}
