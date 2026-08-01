from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select

from ai_enterprise.api.dependencies import SessionDependency, SettingsDependency
from ai_enterprise.infrastructure.resilience.extended_models import (
    ModelDefinitionModel,
    ModelProviderModel,
    RegionModel,
)
from ai_enterprise.infrastructure.security.local_activation import (
    LocalActivationSecurityError,
    require_configured_endpoint,
    require_provider_environment,
)

router = APIRouter(prefix="/providers", tags=["provider-readiness"])


class ProviderReadinessResponse(BaseModel):
    status: str
    active_regions: int
    active_providers: int
    active_models: int


@router.get("/readiness", response_model=ProviderReadinessResponse)
async def provider_readiness(
    session: SessionDependency, settings: SettingsDependency
) -> ProviderReadinessResponse:
    try:
        require_provider_environment(app_env=settings.app_env, provider_kind="local")
        require_configured_endpoint(
            requested=settings.ollama_base_url, configured=settings.ollama_base_url
        )
    except LocalActivationSecurityError as exc:
        raise HTTPException(
            status_code=503, detail={"code": "PROVIDER_SECURITY_POLICY", "message": str(exc)}
        ) from exc
    regions = int(
        await session.scalar(
            select(func.count()).select_from(RegionModel).where(RegionModel.status == "active")
        )
        or 0
    )
    providers = int(
        await session.scalar(
            select(func.count())
            .select_from(ModelProviderModel)
            .where(ModelProviderModel.status == "active")
        )
        or 0
    )
    models = int(
        await session.scalar(
            select(func.count())
            .select_from(ModelDefinitionModel)
            .where(ModelDefinitionModel.status == "active")
        )
        or 0
    )
    if not regions or not providers or not models:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PROVIDER_NOT_READY",
                "active_regions": regions,
                "active_providers": providers,
                "active_models": models,
            },
        )
    return ProviderReadinessResponse(
        status="ready",
        active_regions=regions,
        active_providers=providers,
        active_models=models,
    )
