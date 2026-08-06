import importlib.util
from pathlib import Path


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
