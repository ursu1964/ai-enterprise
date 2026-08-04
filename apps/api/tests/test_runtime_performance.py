from fastapi.testclient import TestClient

from ai_enterprise.main import app
from ai_enterprise.observability import metrics_snapshot, observe_duration


def test_duration_metrics_record_count_sum_and_max() -> None:
    before = metrics_snapshot()
    prefix = "test_runtime_performance_duration"

    observe_duration(prefix, 0.012)
    observe_duration(prefix, 0.020)
    after = metrics_snapshot()

    assert after[f"{prefix}_count"] - before.get(f"{prefix}_count", 0) == 2
    assert after[f"{prefix}_milliseconds_sum"] - before.get(
        f"{prefix}_milliseconds_sum", 0
    ) == 32
    assert after[f"{prefix}_milliseconds_max"] == 20


def test_http_responses_expose_server_timing_and_route_metrics() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.headers["server-timing"].startswith("app;dur=")
    metrics = client.get("/metrics").text
    assert "http_route_health_live_duration_count" in metrics
    assert "http_route_health_live_duration_milliseconds_sum" in metrics
    assert "http_route_health_live_duration_milliseconds_max" in metrics


def test_large_dashboard_responses_are_compressed() -> None:
    response = TestClient(app).get(
        "/dashboard",
        headers={"Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in response.headers["vary"]
