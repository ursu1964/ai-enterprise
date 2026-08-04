from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
