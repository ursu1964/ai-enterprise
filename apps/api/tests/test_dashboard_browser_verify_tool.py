import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest


def _load():
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / "dashboard_browser_verify.py"
    spec = importlib.util.spec_from_file_location("dashboard_browser_verify", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


browser_verify = _load()


def test_browser_journeys_cover_all_primary_operator_views() -> None:
    assert browser_verify.TAB_JOURNEYS == {
        "overview": "Living Enterprise Pulse",
        "execution": "Project Execution Control",
        "factory": "Manifesto Launcher",
        "problems": "Guided Recovery Center",
        "metrics": "Business Telemetry",
        "projects": "Project Intelligence Graph",
        "graph": "Blueprint Graph Hub",
    }
    assert browser_verify.REDUNDANT_DASHBOARD_REQUESTS == {
        "/api/v1/query/operating-picture",
        "/dashboard/telemetry-summary",
        "/api/v1/projects",
        "/api/v1/operator/jobs",
        "/api/v1/operator/jobs/worker-instances",
    }


def test_browser_verifier_covers_r10_client_runtime() -> None:
    source = Path(browser_verify.__file__).read_text(encoding="utf-8")

    assert "/client-portal" in source
    assert "Universal Experience Runtime" in source
    assert "Bootstrap R10 Workspace" in source
    assert "roleSelect" in source
    assert "deviceSelect" in source
    assert "mobile_width" in source


def test_browser_verifier_failure_report_matches_schema() -> None:
    report = browser_verify._failure_report("browser unavailable")

    assert report["conformant"] is False
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/release-artifacts/dashboard-browser-verification-report.schema.json"
    )
    root = Path(browser_verify.__file__).resolve().parents[1]
    schema = json.loads((root / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)


def test_browser_verifier_report_fails_closed_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_schema = browser_verify._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(browser_verify, "_schema", stricter_schema)

    with pytest.raises(
        RuntimeError,
        match="dashboard-browser-verification-report.schema.json",
    ):
        browser_verify._failure_report("boom")
