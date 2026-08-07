import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
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
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == "schemas/release-artifacts/docker-smoke-report.schema.json"
    schema = json.loads((_repo_root() / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    worker_check = _check(report, "worker_visibility")
    assert worker_check["worker_count"] == 1
    assert worker_check["worker_statuses"] == ["online"]


def test_docker_smoke_can_sign_operator_headers() -> None:
    headers = docker_smoke.operator_headers(
        trusted_proxy_secret="x" * 32,
        timestamp=123,
    )

    assert headers["X-Actor-ID"] == "local-dashboard-admin"
    assert headers["X-Actor-Type"] == "human"
    assert headers["X-Actor-Role"] == "platform-admin"
    assert headers["X-Proxy-Timestamp"] == "123"
    assert len(headers["X-Proxy-Signature"]) == 64


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


def test_docker_smoke_report_fails_closed_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_schema = docker_smoke._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(docker_smoke, "_schema", stricter_schema)

    with pytest.raises(RuntimeError, match="docker-smoke-report.schema.json"):
        docker_smoke._failure_report("boom")


def _check(report: dict[str, Any], name: str) -> dict[str, Any]:
    return next(item for item in report["checks"] if item["name"] == name)
