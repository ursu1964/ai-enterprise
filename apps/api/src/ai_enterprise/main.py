from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from ai_enterprise.api.routes.agent_runtime import router as agent_runtime_router
from ai_enterprise.api.routes.architecture_governance import (
    router as architecture_governance_router,
)
from ai_enterprise.api.routes.architecture_operations import (
    router as architecture_operations_router,
)
from ai_enterprise.api.routes.audit import router as audit_router
from ai_enterprise.api.routes.change_management import (
    router as change_management_router,
)
from ai_enterprise.api.routes.cognitive import router as cognitive_router
from ai_enterprise.api.routes.decompositions import router as decompositions_router
from ai_enterprise.api.routes.ecosystem import router as ecosystem_router
from ai_enterprise.api.routes.enterprise_evolution import router as enterprise_evolution_router
from ai_enterprise.api.routes.enterprise_kernel import router as enterprise_kernel_router
from ai_enterprise.api.routes.evolution import router as evolution_router
from ai_enterprise.api.routes.executions import router as executions_router
from ai_enterprise.api.routes.foundation import router as foundation_router
from ai_enterprise.api.routes.integration import router as integration_router
from ai_enterprise.api.routes.knowledge import router as knowledge_router
from ai_enterprise.api.routes.operator_jobs import router as operator_jobs_router
from ai_enterprise.api.routes.organizations import router as organizations_router
from ai_enterprise.api.routes.patch_reviews import (
    router as patch_reviews_router,
)
from ai_enterprise.api.routes.performance import router as performance_router
from ai_enterprise.api.routes.projects import router as projects_router
from ai_enterprise.api.routes.provider_readiness import router as provider_readiness_router
from ai_enterprise.api.routes.recovery import router as recovery_router
from ai_enterprise.api.routes.requirements_provider import router as requirements_provider_router
from ai_enterprise.api.routes.requirements_revisions import (
    router as requirements_revisions_router,
)
from ai_enterprise.api.routes.resilience import router as resilience_router
from ai_enterprise.api.routes.resilience_extended import router as resilience_extended_router
from ai_enterprise.api.routes.specifications import router as specifications_router
from ai_enterprise.api.routes.workflows import router as workflows_router
from ai_enterprise.config import get_settings
from ai_enterprise.infrastructure.database.session import SessionFactory
from ai_enterprise.observability import configure_logging, metrics_snapshot


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.artifact_root.mkdir(parents=True, exist_ok=True)

    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(projects_router, prefix="/api/v1")
app.include_router(architecture_governance_router, prefix="/api/v1")
app.include_router(architecture_operations_router)
app.include_router(executions_router, prefix="/api/v1")
app.include_router(patch_reviews_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(recovery_router, prefix="/api/v1")
app.include_router(integration_router, prefix="/api/v1")
app.include_router(workflows_router, prefix="/api/v1")
app.include_router(foundation_router, prefix="/api/v1")
app.include_router(provider_readiness_router, prefix="/api/v1")
app.include_router(resilience_router, prefix="/api/v1")
app.include_router(resilience_extended_router, prefix="/api/v1")
app.include_router(change_management_router, prefix="/api/v1")
app.include_router(decompositions_router, prefix="/api/v1")
app.include_router(evolution_router, prefix="/api/v1")
app.include_router(enterprise_evolution_router, prefix="/api/v1")
app.include_router(enterprise_kernel_router, prefix="/api/v1")
app.include_router(ecosystem_router, prefix="/api/v1")
app.include_router(cognitive_router, prefix="/api/v1")
app.include_router(operator_jobs_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(requirements_revisions_router, prefix="/api/v1")
app.include_router(requirements_provider_router, prefix="/api/v1")
app.include_router(agent_runtime_router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(performance_router, prefix="/api/v1")
app.include_router(specifications_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "status": "running",
    }


@app.get("/health")
@app.get("/health/live")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "not_checked",
    }


@app.get("/ready")
@app.get("/health/ready")
async def readiness() -> dict[str, str]:
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": "reachable",
    }


@app.get("/metrics")
async def metrics() -> dict[str, int]:
    return metrics_snapshot()
