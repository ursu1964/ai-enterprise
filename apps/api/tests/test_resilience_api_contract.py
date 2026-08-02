from pathlib import Path

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor, get_actor
from ai_enterprise.api.routes.resilience import _human
from ai_enterprise.infrastructure.database.models import Base
from ai_enterprise.main import app


def test_resilience_routes_are_registered() -> None:
    paths = app.openapi()["paths"]
    expected = {
        "/api/v1/resilience/services",
        "/api/v1/resilience/services/{service_id}/objectives",
        "/api/v1/resilience/continuity/activations",
        "/api/v1/resilience/continuity/activations/{activation_id}/close",
        "/api/v1/resilience/backups",
        "/api/v1/resilience/backups/{backup_id}/restore-verifications",
        "/api/v1/resilience/dr-runs",
        "/api/v1/resilience/dr-runs/{run_id}/transitions",
        "/api/v1/resilience/services/{service_id}/readiness",
    }
    assert expected.issubset(paths)


@pytest.mark.asyncio
async def test_resilience_mutation_requires_actor_headers() -> None:
    with pytest.raises(HTTPException) as captured:
        await get_actor(None, None, None)
    assert captured.value.status_code == 401


def test_resilience_authority_is_human_and_role_scoped() -> None:
    with pytest.raises(HTTPException) as agent_denied:
        _human(
            Actor(
                "agent-1",
                "agent",
                "resilience_admin",
                frozenset({"resilience.resilience_admin"}),
                scopes=frozenset({"global"}),
            ),
            {"resilience_admin"},
        )
    assert agent_denied.value.status_code == 403
    with pytest.raises(HTTPException):
        _human(Actor("human-1", "human", "developer"), {"resilience_admin"})
    with pytest.raises(HTTPException):
        _human(Actor("human-1", "human", "resilience_admin"), {"resilience_admin"})
    with pytest.raises(HTTPException):
        _human(
            Actor(
                "human-1",
                "human",
                "resilience_admin",
                frozenset({"resilience.resilience_admin"}),
                scopes=frozenset({"organization:wrong"}),
            ),
            {"resilience_admin"},
        )
    _human(
        Actor(
            "human-1",
            "human",
            "developer",
            frozenset({"resilience.resilience_admin"}),
            scopes=frozenset({"global"}),
        ),
        {"resilience_admin"},
    )


def test_resilience_models_are_registered_in_shared_metadata() -> None:
    expected = {
        "resilience_services",
        "resilience_recovery_objectives",
        "resilience_service_dependencies",
        "continuity_activations",
        "continuity_capability_decisions",
        "backup_manifests",
        "restore_verifications",
        "disaster_recovery_plans",
        "disaster_recovery_runs",
        "disaster_recovery_steps",
    }
    assert expected.issubset(Base.metadata.tables)


def test_p9_migration_is_child_of_p4_head() -> None:
    migration = (
        Path(__file__).parents[3]
        / "migrations/versions/c91a74e8f603_add_p9_m1_resilience_control_plane.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "b73e91c4d205"' in migration
    assert "def upgrade()" in migration and "def downgrade()" in migration
