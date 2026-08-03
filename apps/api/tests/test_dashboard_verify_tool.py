import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


def _load(name: str):
    root = _repo_root()
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Unable to locate repository root from test path")


dashboard_verify = _load("dashboard_verify")


def test_dashboard_verify_checks_pages_and_manager_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager_payload = {
        "headline": {"state": "active"},
        "totals": {"projects": 2},
        "business_board": {
            "next": {"target": "execution"},
            "cards": [
                {
                    "title": "Business State",
                    "message": "Active. 2 workers online.",
                    "effect": "The board refreshes from the manager read model.",
                },
                {
                    "title": "Value in Motion",
                    "message": "2 projects visible.",
                    "effect": "Delivery capacity is producing outcomes.",
                },
                {
                    "title": "Risk and Attention",
                    "message": "No urgent delivery risk is visible.",
                    "effect": "Fix risk before scaling parallel work.",
                },
                {
                    "title": "Recommended Next Move",
                    "message": "Inspect live execution.",
                    "effect": "Best next action.",
                },
            ],
        },
    }
    responses = {
        "/dashboard": (
            200,
            "text/html",
            "AI Enterprise Command Center Business decision board "
            "state.dashboardManager?.business_board Project Execution Control "
            "Guided Recovery Center Graph Hub",
        ),
        "/dashboard/demo": (
            200,
            "text/html",
            "AI Enterprise Demo Story Idea to Reality Map Step-by-Step Live Demo "
            "Demo Operator Console",
        ),
        "/dashboard/documentation-hub": (
            200,
            "text/html",
            "Documentation Hub Operator Documents Document Preview Graphs and Images Commands",
        ),
        "/api/v1/query/dashboard-manager": (
            200,
            "application/json",
            json.dumps(manager_payload),
        ),
    }

    def fake_request(
        base_url: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float,
    ) -> tuple[int, str, str]:
        assert base_url == "http://local"
        assert timeout == 1
        if path == "/api/v1/query/dashboard-manager":
            assert headers == dashboard_verify.operator_headers()
        return responses[path]

    monkeypatch.setattr(dashboard_verify, "_request", fake_request)

    report = dashboard_verify.run_dashboard_verify(
        base_url="http://local",
        attempts=1,
        interval=0,
        timeout=1,
    )

    assert report["conformant"] is True
    assert _check(report, "dashboard_manager_business_board")["card_count"] == 4
    assert _check(report, "dashboard_manager_business_board")["next_target"] == "execution"


def test_dashboard_verify_rejects_cryptic_dashboard_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(
        base_url: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float,
    ) -> tuple[int, str, str]:
        if path == "/dashboard":
            return (
                200,
                "text/html",
                "AI Enterprise Command Center Business decision board "
                "state.dashboardManager?.business_board Project Execution Control "
                "Guided Recovery Center Graph Hub No records.",
            )
        return 200, "text/html", ""

    monkeypatch.setattr(dashboard_verify, "_request", fake_request)

    with pytest.raises(RuntimeError, match="cryptic primary text"):
        dashboard_verify.run_dashboard_verify(
            base_url="http://local",
            attempts=1,
            interval=0,
            timeout=1,
        )


def test_dashboard_verify_rejects_invalid_business_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request(
        base_url: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float,
    ) -> tuple[int, str, str]:
        if path == "/api/v1/query/dashboard-manager":
            return (
                200,
                "application/json",
                json.dumps({"business_board": {"next": {"target": "execution"}, "cards": []}}),
            )
        if path == "/dashboard":
            return (
                200,
                "text/html",
                "AI Enterprise Command Center Business decision board "
                "state.dashboardManager?.business_board Project Execution Control "
                "Guided Recovery Center Graph Hub",
            )
        if path == "/dashboard/demo":
            return (
                200,
                "text/html",
                "AI Enterprise Demo Story Idea to Reality Map Step-by-Step Live Demo "
                "Demo Operator Console",
            )
        return (
            200,
            "text/html",
            "Documentation Hub Operator Documents Document Preview Graphs and Images Commands",
        )

    monkeypatch.setattr(dashboard_verify, "_request", fake_request)

    with pytest.raises(RuntimeError, match="four primary cards"):
        dashboard_verify.run_dashboard_verify(
            base_url="http://local",
            attempts=1,
            interval=0,
            timeout=1,
        )


def _check(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in report["checks"] if item["name"] == name)
