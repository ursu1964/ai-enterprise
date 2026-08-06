from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from ai_enterprise.api.routes.agent_runtime import router as agent_runtime_router
from ai_enterprise.api.routes.architecture_governance import (
    router as architecture_governance_router,
)
from ai_enterprise.api.routes.architecture_operations import (
    router as architecture_operations_router,
)
from ai_enterprise.api.routes.audit import router as audit_router
from ai_enterprise.api.routes.bk_r10_verification import router as bk_r10_verification_router
from ai_enterprise.api.routes.bk_r11_evidence_audit import (
    router as bk_r11_evidence_audit_router,
)
from ai_enterprise.api.routes.blueprints import router as blueprints_router
from ai_enterprise.api.routes.change_management import (
    router as change_management_router,
)
from ai_enterprise.api.routes.cognitive import router as cognitive_router
from ai_enterprise.api.routes.dashboard import router as dashboard_router
from ai_enterprise.api.routes.decompositions import router as decompositions_router
from ai_enterprise.api.routes.ecosystem import router as ecosystem_router
from ai_enterprise.api.routes.enterprise_evolution import router as enterprise_evolution_router
from ai_enterprise.api.routes.enterprise_kernel import router as enterprise_kernel_router
from ai_enterprise.api.routes.evolution import router as evolution_router
from ai_enterprise.api.routes.executions import router as executions_router
from ai_enterprise.api.routes.foundation import router as foundation_router
from ai_enterprise.api.routes.foundation_projects import router as foundation_projects_router
from ai_enterprise.api.routes.integration import router as integration_router
from ai_enterprise.api.routes.knowledge import router as knowledge_router
from ai_enterprise.api.routes.operator_jobs import router as operator_jobs_router
from ai_enterprise.api.routes.organizations import router as organizations_router
from ai_enterprise.api.routes.patch_reviews import (
    router as patch_reviews_router,
)
from ai_enterprise.api.routes.performance import router as performance_router
from ai_enterprise.api.routes.project_formation import router as project_formation_router
from ai_enterprise.api.routes.projects import router as projects_router
from ai_enterprise.api.routes.provider_readiness import router as provider_readiness_router
from ai_enterprise.api.routes.query_platform import router as query_platform_router
from ai_enterprise.api.routes.r4_ai_interpretation import router as r4_ai_interpretation_router
from ai_enterprise.api.routes.r5_umte import router as r5_umte_router
from ai_enterprise.api.routes.r6_uagf import router as r6_uagf_router
from ai_enterprise.api.routes.r7_uerm import router as r7_uerm_router
from ai_enterprise.api.routes.r8_ugeif import router as r8_ugeif_router
from ai_enterprise.api.routes.r9_uak import router as r9_uak_router
from ai_enterprise.api.routes.r10_ueif import router as r10_ueif_router
from ai_enterprise.api.routes.r11_uief import router as r11_uief_router
from ai_enterprise.api.routes.r12_bootstrap import router as r12_bootstrap_router
from ai_enterprise.api.routes.r13_repository_bootstrap import (
    router as r13_repository_bootstrap_router,
)
from ai_enterprise.api.routes.r14_manifest_schema import router as r14_manifest_schema_router
from ai_enterprise.api.routes.r15_manifest_compiler import (
    router as r15_manifest_compiler_router,
)
from ai_enterprise.api.routes.r16_knowledge_graph import router as r16_knowledge_graph_router
from ai_enterprise.api.routes.r17_execution_planner import (
    router as r17_execution_planner_router,
)
from ai_enterprise.api.routes.r18_generator_orchestration import (
    router as r18_generator_orchestration_router,
)
from ai_enterprise.api.routes.r19_project_memory import router as r19_project_memory_router
from ai_enterprise.api.routes.r20_runtime_kernel import router as r20_runtime_kernel_router
from ai_enterprise.api.routes.r21_execution_orchestrator import (
    router as r21_execution_orchestrator_router,
)
from ai_enterprise.api.routes.r22_artifact_intelligence import (
    router as r22_artifact_intelligence_router,
)
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
from ai_enterprise.observability import (
    configure_logging,
    increment_metric,
    observe_duration,
    prometheus_metrics_snapshot,
)


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
app.add_middleware(GZipMiddleware, minimum_size=1_000, compresslevel=5)

app.include_router(foundation_projects_router, prefix="/api/v1")
app.include_router(bk_r10_verification_router, prefix="/api/v1")
app.include_router(bk_r11_evidence_audit_router, prefix="/api/v1")
app.include_router(r4_ai_interpretation_router, prefix="/api/v1")
app.include_router(r5_umte_router, prefix="/api/v1")
app.include_router(r6_uagf_router, prefix="/api/v1")
app.include_router(r7_uerm_router, prefix="/api/v1")
app.include_router(r8_ugeif_router, prefix="/api/v1")
app.include_router(r9_uak_router, prefix="/api/v1")
app.include_router(r10_ueif_router, prefix="/api/v1")
app.include_router(r11_uief_router, prefix="/api/v1")
app.include_router(r12_bootstrap_router, prefix="/api/v1")
app.include_router(r13_repository_bootstrap_router, prefix="/api/v1")
app.include_router(r14_manifest_schema_router, prefix="/api/v1")
app.include_router(r15_manifest_compiler_router, prefix="/api/v1")
app.include_router(r16_knowledge_graph_router, prefix="/api/v1")
app.include_router(r17_execution_planner_router, prefix="/api/v1")
app.include_router(r18_generator_orchestration_router, prefix="/api/v1")
app.include_router(r19_project_memory_router, prefix="/api/v1")
app.include_router(r20_runtime_kernel_router, prefix="/api/v1")
app.include_router(r21_execution_orchestrator_router, prefix="/api/v1")
app.include_router(r22_artifact_intelligence_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(blueprints_router, prefix="/api/v1")
app.include_router(project_formation_router, prefix="/api/v1")
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
app.include_router(query_platform_router, prefix="/api/v1")
app.include_router(dashboard_router)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    started = perf_counter()
    increment_metric("http_requests_total")
    increment_metric(f"http_requests_{request.method.lower()}_total")
    try:
        response = await call_next(request)
    except Exception:
        increment_metric("http_responses_500_total")
        raise
    finally:
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        route_key = (
            route_path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
        )
        elapsed_seconds = perf_counter() - started
        observe_duration(f"http_route_{route_key}_duration", elapsed_seconds)
    response.headers["Server-Timing"] = f"app;dur={elapsed_seconds * 1000:.3f}"
    increment_metric(f"http_route_{route_key}_total")
    increment_metric(f"http_responses_{response.status_code}_total")
    return response


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
async def metrics() -> Response:
    payload = prometheus_metrics_snapshot(
        {
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }
    )
    return Response(content=payload, media_type="text/plain; version=0.0.4")
