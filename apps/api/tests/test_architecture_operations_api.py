import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.architecture_operations import _require_architecture_operator


def test_architecture_worker_health_requires_scoped_capability() -> None:
    with pytest.raises(HTTPException, match="Architecture operator capability"):
        _require_architecture_operator(Actor("operator", "human", "architecture_operator"))
    with pytest.raises(HTTPException, match="Architecture operator capability"):
        _require_architecture_operator(
            Actor(
                "operator",
                "human",
                "architecture_operator",
                frozenset({"architecture.worker.readiness"}),
                scopes=frozenset({"project:wrong"}),
            )
        )
    _require_architecture_operator(
        Actor(
            "operator",
            "human",
            "architecture_operator",
            frozenset({"architecture.worker.readiness"}),
            scopes=frozenset({"global"}),
        )
    )
