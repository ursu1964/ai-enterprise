from fastapi.testclient import TestClient

from ai_enterprise.main import app


def test_metrics_endpoint_returns_prometheus_text_with_http_counters() -> None:
    client = TestClient(app)

    client.get("/health/live")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "ai_enterprise_http_requests_total" in response.text
    assert "ai_enterprise_http_responses_200_total" in response.text
    assert "ai_enterprise_process_uptime_seconds" in response.text
