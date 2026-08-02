import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


docker_smoke = _load("docker_smoke")


def test_docker_smoke_reports_health_metrics_and_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "/health/live": (200, "application/json", json.dumps({"status": "ok"})),
        "/health/ready": (
            200,
            "application/json",
            json.dumps({"status": "ok", "database": "reachable"}),
        ),
        "/metrics": (
            200,
            "text/plain",
            "ai_enterprise_process_uptime_seconds 1\nai_enterprise_http_requests_total 2\n",
        ),
        "/api/v1/operator/jobs/worker-instances": (
            200,
            "application/json",
            json.dumps([{"worker_id": "worker-1", "status": "online"}]),
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
        if path.endswith("worker-instances"):
            assert headers == docker_smoke.OPERATOR_HEADERS
        return responses[path]

    monkeypatch.setattr(docker_smoke, "_request", fake_request)

    report = docker_smoke.run_smoke(
        base_url="http://local",
        attempts=1,
        interval=0,
        timeout=1,
        require_worker=True,
    )

    assert report["conformant"] is True
    worker_check = _check(report, "worker_visibility")
    assert worker_check["worker_count"] == 1
    assert worker_check["worker_statuses"] == ["online"]


def test_docker_smoke_requires_visible_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_request(
        base_url: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float,
    ) -> tuple[int, str, str]:
        if path == "/health/live":
            return 200, "application/json", json.dumps({"status": "ok"})
        if path == "/health/ready":
            return 200, "application/json", json.dumps({"status": "ok", "database": "reachable"})
        if path == "/metrics":
            return (
                200,
                "text/plain",
                "ai_enterprise_process_uptime_seconds 1\nai_enterprise_http_requests_total 2\n",
            )
        return 200, "application/json", "[]"

    monkeypatch.setattr(docker_smoke, "_request", fake_request)

    with pytest.raises(RuntimeError, match="no worker instances are visible"):
        docker_smoke.run_smoke(
            base_url="http://local",
            attempts=1,
            interval=0,
            timeout=1,
            require_worker=True,
        )


def _check(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in report["checks"] if item["name"] == name)
