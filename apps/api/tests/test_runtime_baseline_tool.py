from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import jsonschema
import pytest


def _load_tool():
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "runtime_baseline", root / "tools" / "runtime_baseline.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime_baseline = _load_tool()


def test_runtime_baseline_rejects_non_loopback_url(tmp_path: Path) -> None:
    with pytest.raises(runtime_baseline.BaselineError, match="loopback"):
        runtime_baseline.build_baseline(tmp_path, "https://enterprise.example.com")


def test_metric_snapshot_keeps_only_route_performance_signals() -> None:
    raw = """
ai_enterprise_http_requests_total 12
ai_enterprise_http_route_dashboard_duration_count{service="test"} 3
ai_enterprise_http_route_dashboard_duration_milliseconds_max{service="test"} 20.5
unrelated_metric 99
"""

    assert runtime_baseline._metric_snapshot(raw) == {
        "ai_enterprise_http_route_dashboard_duration_count": 3.0,
        "ai_enterprise_http_route_dashboard_duration_milliseconds_max": 20.5,
    }


def test_canonical_hash_changes_with_runtime_evidence() -> None:
    first = {"git": {"commit": "a"}, "totals": {"problems": 1}}
    second = {"git": {"commit": "a"}, "totals": {"problems": 2}}

    assert runtime_baseline._canonical_hash(first) != runtime_baseline._canonical_hash(second)


def test_runtime_baseline_builds_schema_valid_document(tmp_path: Path, monkeypatch) -> None:
    class Headers(dict):
        pass

    def fake_json(url: str, *, headers: dict[str, str] | None = None):
        assert url == "http://127.0.0.1:8000/dashboard/context"
        assert headers is None
        return {"actor_headers": {"x-actor": "tester"}, "organization_id": "org-1"}, Headers()

    def fake_request(url: str, *, headers: dict[str, str] | None = None):
        assert headers == {"x-actor": "tester"} or url.endswith("/metrics")
        if "/api/v1/query/dashboard-manager" in url:
            payload = {
                "headline": {"status": "degraded"},
                "totals": {"jobs": 2},
                "telemetry_summary": {"runtime": {"worker": "active"}},
                "records": {
                    "jobs": [
                        {
                            "id": "job-1",
                            "job_type": "orchestration",
                            "status": "failed",
                            "last_failure_class": "RuntimeError",
                            "last_error": "boom",
                        },
                        {"id": "job-2", "job_type": "orchestration", "status": "succeeded"},
                    ]
                },
            }
            return json_bytes(payload), Headers({"Server-Timing": "db;dur=1"})
        if url == "http://127.0.0.1:8000/metrics":
            return b"ai_enterprise_http_route_dashboard_duration_count 1\n", Headers()
        raise AssertionError(f"unexpected URL: {url}")

    def fake_git(root: Path, *args: str) -> str:
        assert root == tmp_path
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("rev-parse", "HEAD^{tree}"):
            return "b" * 40
        if args == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(runtime_baseline, "_json", fake_json)
    monkeypatch.setattr(runtime_baseline, "_request", fake_request)
    monkeypatch.setattr(runtime_baseline, "_git", fake_git)

    document = runtime_baseline.build_baseline(tmp_path, "http://127.0.0.1:8000")

    assert document["schema_version"] == "1.0"
    assert document["git"]["dirty"] is False
    assert document["failure_patterns"] == [
        {
            "failure_class": "RuntimeError",
            "diagnostic": "boom",
            "count": 1,
            "job_ids": ["job-1"],
            "job_types": ["orchestration"],
        }
    ]
    jsonschema.validate(document, runtime_baseline._schema())  # noqa: SLF001


def test_runtime_baseline_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original_schema = runtime_baseline._schema  # noqa: SLF001

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(runtime_baseline, "_schema", stricter_schema)

    with pytest.raises(runtime_baseline.BaselineError, match="runtime baseline does not validate"):
        runtime_baseline._validate_baseline(  # noqa: SLF001
            {
                "schema_version": "1.0",
                "captured_at": "2026-08-06T00:00:00+00:00",
                "proof_level": "local_demo",
                "source": {"base_url": "http://127.0.0.1:8000", "read_only": True},
                "git": {"commit": "a" * 40, "tree": "b" * 40, "dirty": False},
                "manager": {
                    "headline": {},
                    "totals": {},
                    "runtime": {},
                    "response_bytes": 2,
                    "server_timing": None,
                },
                "failure_patterns": [],
                "route_metrics": {},
                "evidence_hash": "c" * 64,
            }
        )


def json_bytes(payload: dict) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")
