import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Unable to locate repository root")


def _load():
    name = "demo_lifecycle"
    spec = importlib.util.spec_from_file_location(name, _repo_root() / "tools/demo_lifecycle.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


demo_lifecycle = _load()
DEMO_LIFECYCLE_SCHEMA = json.loads(
    (_repo_root() / "schemas" / "evidence-audit" / "demo-lifecycle-evidence.schema.json").read_text(
        encoding="utf-8"
    )
)


def _context() -> dict[str, Any]:
    return {
        "actor_headers": {
            "X-Actor-ID": "local-dashboard-admin",
            "X-Actor-Type": "human",
            "X-Actor-Role": "platform-admin",
        },
        "authority": {"mode": "local-dashboard-context"},
    }


def _preview() -> dict[str, Any]:
    return {
        "status": "ready",
        "projects": [
            {
                "name": name,
                "repository_path": path,
                "ready": True,
                "action": "reuse",
                "existing_project_id": str(index),
            }
            for index, (name, path) in enumerate(demo_lifecycle.CANONICAL_PORTFOLIO, start=1)
        ],
    }


def _manager(*, unhealthy: bool = False) -> dict[str, Any]:
    return {
        "projects": [
            {
                "id": str(index),
                "name": name,
                "status": "execution_running",
                "workflow": {
                    "state": ("manual_intervention" if unhealthy and index == 1 else "execution")
                },
                "tasks": {"problems": 0},
            }
            for index, (name, _path) in enumerate(demo_lifecycle.CANONICAL_PORTFOLIO, start=1)
        ]
    }


def _start() -> dict[str, Any]:
    return {
        "status": "started",
        "failed_count": 0,
        "blocked_count": 0,
        "projects": [
            {"name": name, "project_id": str(index)}
            for index, (name, _path) in enumerate(demo_lifecycle.CANONICAL_PORTFOLIO, start=1)
        ],
    }


def _fake_responses(monkeypatch: pytest.MonkeyPatch, *, jobs=None, unhealthy=False):
    calls: list[tuple[str, str]] = []

    def fake_request(base_url, path, *, headers=None, method="GET", timeout=10):
        calls.append((method, path))
        if path == "/dashboard/context":
            return _context()
        assert headers == _context()["actor_headers"]
        if path.endswith("/preview"):
            return _preview()
        if path == "/api/v1/query/dashboard-manager":
            return _manager(unhealthy=unhealthy)
        if path.startswith("/api/v1/operator/jobs"):
            return jobs or []
        if path.endswith("/start"):
            return _start()
        raise AssertionError(path)

    monkeypatch.setattr(demo_lifecycle, "_request_json", fake_request)
    return calls


@pytest.mark.parametrize("url", ["https://example.com", "http://10.0.0.2:8000", "ftp://localhost"])
def test_rejects_non_loopback_or_unsupported_urls(url: str, tmp_path: Path) -> None:
    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="loopback"):
        demo_lifecycle.run_lifecycle(base_url=url, execute=False, output_dir=tmp_path)


def test_preview_is_read_only_and_does_not_write_evidence(monkeypatch, tmp_path: Path) -> None:
    calls = _fake_responses(monkeypatch)
    report, evidence = demo_lifecycle.run_lifecycle(
        base_url="http://localhost:8000", execute=False, output_dir=tmp_path
    )
    assert report["preflight"]["status"] == "ready"
    assert report["execution"] is None
    assert evidence is None
    assert not any(method == "POST" for method, _path in calls)
    assert list(tmp_path.iterdir()) == []


def test_unresolved_job_blocks_before_start_and_writes_hashed_evidence(monkeypatch, tmp_path):
    calls = _fake_responses(
        monkeypatch,
        jobs=[
            {
                "id": "job-1",
                "project_id": "project-1",
                "job_type": "execute",
                "status": "dead_letter",
                "last_failure_class": "artifact_contract",
                "last_error": "secret diagnostic must not be copied",
                "operator_resolution": None,
            }
        ],
    )
    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="blocked"):
        demo_lifecycle.run_lifecycle(
            base_url="http://127.0.0.1:8000", execute=True, output_dir=tmp_path
        )
    assert not any(path.endswith("/start") for _method, path in calls)
    evidence_file = next(tmp_path.glob("demo-lifecycle-*.json"))
    evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
    digest = evidence.pop("integrity_sha256")
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"), default=str).encode()
    assert hashlib.sha256(canonical).hexdigest() == digest
    evidence["integrity_sha256"] = digest
    jsonschema.validate(evidence, DEMO_LIFECYCLE_SCHEMA)
    assert evidence["preflight"]["unresolved_jobs"][0]["id"] == "job-1"
    assert "secret diagnostic" not in evidence_file.read_text(encoding="utf-8")


def test_unhealthy_canonical_workflow_blocks_before_start(monkeypatch, tmp_path):
    calls = _fake_responses(monkeypatch, unhealthy=True)
    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="blocked"):
        demo_lifecycle.run_lifecycle(
            base_url="http://localhost:8000", execute=True, output_dir=tmp_path
        )
    assert not any(path.endswith("/start") for _method, path in calls)


def test_execute_posts_once_and_records_exact_portfolio(monkeypatch, tmp_path):
    calls = _fake_responses(monkeypatch)
    report, evidence_path = demo_lifecycle.run_lifecycle(
        base_url="http://localhost:8000", execute=True, output_dir=tmp_path
    )
    assert report["execution"]["status"] == "started"
    assert evidence_path is not None and evidence_path.exists()
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    jsonschema.validate(evidence, DEMO_LIFECYCLE_SCHEMA)
    assert [call for call in calls if call[0] == "POST"] == [
        ("POST", "/api/v1/project-formation/mock-factory/start")
    ]
    assert len(report["portfolio"]) == 4


def test_rejects_missing_or_extra_preview_project(monkeypatch, tmp_path):
    calls = _fake_responses(monkeypatch)
    original = demo_lifecycle._request_json

    def invalid_preview(*args, **kwargs):
        result = original(*args, **kwargs)
        if args[1].endswith("/preview"):
            result["projects"].pop()
        return result

    monkeypatch.setattr(demo_lifecycle, "_request_json", invalid_preview)
    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="canonical"):
        demo_lifecycle.run_lifecycle(
            base_url="http://localhost:8000", execute=True, output_dir=tmp_path
        )
    assert not any(path.endswith("/start") for _method, path in calls)


def test_partial_execution_is_failure_with_evidence(monkeypatch, tmp_path):
    _fake_responses(monkeypatch)
    original = demo_lifecycle._request_json

    def partial(*args, **kwargs):
        if args[1].endswith("/start"):
            return {"status": "partial", "failed_count": 1, "blocked_count": 0, "projects": []}
        return original(*args, **kwargs)

    monkeypatch.setattr(demo_lifecycle, "_request_json", partial)
    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="incomplete"):
        demo_lifecycle.run_lifecycle(
            base_url="http://localhost:8000", execute=True, output_dir=tmp_path
        )
    assert len(list(tmp_path.glob("demo-lifecycle-*.json"))) == 1


def test_evidence_write_fails_closed_when_schema_validation_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report = _valid_evidence_report()
    original_schema = demo_lifecycle._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(demo_lifecycle, "_schema", stricter_schema)

    with pytest.raises(demo_lifecycle.DemoLifecycleError, match="does not validate"):
        demo_lifecycle._write_evidence(report, tmp_path)
    assert list(tmp_path.iterdir()) == []


def _valid_evidence_report() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-06T00:00:00+00:00",
        "mode": "execute",
        "base_url": "http://localhost:8000",
        "policy": {
            "non_destructive": True,
            "deletes_records": False,
            "acknowledges_jobs": False,
            "local_context_required": True,
        },
        "portfolio": [
            {
                "name": name,
                "repository_path": path,
                "action": "reuse",
                "existing_project_id": str(index),
            }
            for index, (name, path) in enumerate(demo_lifecycle.CANONICAL_PORTFOLIO, start=1)
        ],
        "preflight": {
            "status": "ready",
            "unresolved_jobs": [],
            "unhealthy_canonical_projects": [],
        },
        "execution": {"status": "started", "response": _start()},
    }
