import os

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, text

from ai_enterprise.api.dependencies import ActorDependency, SessionDependency, SettingsDependency
from ai_enterprise.domain.architecture.enums import ArchitectureRunStatus
from ai_enterprise.infrastructure.architecture.models import ArchitectureRunModel
from ai_enterprise.infrastructure.architecture.provider_factory import (
    ArchitectureProviderConfig,
    architecture_provider_ready,
)

router = APIRouter(prefix="/internal/health", tags=["internal-architecture-operations"])


@router.get("/architecture-worker")
async def architecture_worker_health(
    session: SessionDependency,
    settings: SettingsDependency,
    actor: ActorDependency,
) -> dict[str, object]:
    """Authenticated deep readiness probe; this route must not be publicly exposed."""
    if actor.role not in {"platform_operator", "architecture_operator"}:
        raise HTTPException(status_code=403, detail="Architecture operator role required")
    try:
        await session.execute(text("SELECT 1"))
        active = int(
            await session.scalar(
                select(func.count())
                .select_from(ArchitectureRunModel)
                .where(ArchitectureRunModel.status == ArchitectureRunStatus.RUNNING)
            )
            or 0
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Architecture database is unavailable") from exc
    model_ready = await architecture_provider_ready(
        ArchitectureProviderConfig(
            provider=settings.architecture_provider,
            model_name=settings.architecture_model_name,
            base_url=settings.architecture_model_base_url,
            temperature=settings.architecture_temperature,
            timeout_seconds=settings.architecture_timeout_seconds,
            max_tokens=settings.architecture_max_tokens,
        )
    )
    payload: dict[str, object] = {
        "status": "healthy" if model_ready else "not_ready",
        "worker_id": os.environ.get("ARCHITECTURE_WORKER_ID", "architecture-worker"),
        "database": "reachable",
        "queue": "reachable",
        "model_endpoint": "reachable" if model_ready else "unreachable",
        "active_job_count": active,
    }
    if not model_ready:
        raise HTTPException(status_code=503, detail=payload)
    return payload
