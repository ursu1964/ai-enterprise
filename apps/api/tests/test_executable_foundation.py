from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ai_enterprise.config import Settings
from ai_enterprise.main import health, readiness, root


@pytest.mark.asyncio
async def test_root_and_liveness_contracts() -> None:
    root_payload = await root()
    live = await health()
    assert root_payload["status"] == "running"
    assert root_payload["version"] == "0.1.0"
    assert live["database"] == "not_checked"


@pytest.mark.asyncio
async def test_readiness_checks_database() -> None:
    session = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = session
    with patch("ai_enterprise.main.SessionFactory", return_value=context):
        response = await readiness()
    assert response["database"] == "reachable"
    session.execute.assert_awaited_once()


def test_settings_validate_api_and_pool_bounds() -> None:
    settings = Settings(api_port=9000, database_pool_size=2, database_max_overflow=0)
    assert settings.api_port == 9000
    assert settings.app_version == "0.1.0"


def test_container_foundation_is_non_root_and_read_only() -> None:
    root = Path(__file__).parents[3]
    dockerfile = (root / "apps/api/Dockerfile").read_text(encoding="utf-8")
    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile
    assert "--uid 10001" in dockerfile
    assert "read_only: true" in compose
    assert "condition: service_completed_successfully" in compose
    assert "127.0.0.1:8000:8000" in compose
    assert "127.0.0.1:5432:5432" in compose


def test_platform_metadata_migration_is_reversible_and_linear() -> None:
    root = Path(__file__).parents[3]
    migration = (
        root / "migrations/versions/b94e10d3f721_add_platform_metadata_foundation.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "a67c9e12b4d8"' in migration
    assert 'op.create_table(\n        "platform_metadata"' in migration
    assert 'op.drop_table("platform_metadata")' in migration
