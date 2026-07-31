from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai_enterprise.api.routes.executions import router as executions_router
from ai_enterprise.api.routes.projects import router as projects_router
from ai_enterprise.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.artifact_root.mkdir(parents=True, exist_ok=True)

    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(projects_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }
