#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

DEFAULT_ACTOR_ID = "local-dashboard-admin"
DEFAULT_ACTOR_TYPE = "human"
DEFAULT_ACTOR_ROLE = "platform-admin"


def _sign_identity_assertion(
    *, secret: str, actor_id: str, actor_type: str, actor_role: str, timestamp: int
) -> str:
    message = f"{actor_id}\n{actor_type}\n{actor_role}\n{timestamp}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def operator_headers(
    *,
    actor_id: str = DEFAULT_ACTOR_ID,
    actor_type: str = DEFAULT_ACTOR_TYPE,
    actor_role: str = DEFAULT_ACTOR_ROLE,
    trusted_proxy_secret: str | None = None,
    timestamp: int | None = None,
) -> dict[str, str]:
    headers = {
        "X-Actor-ID": actor_id,
        "X-Actor-Type": actor_type,
        "X-Actor-Role": actor_role,
    }
    if trusted_proxy_secret:
        asserted_at = timestamp or int(time.time())
        headers["X-Proxy-Timestamp"] = str(asserted_at)
        headers["X-Proxy-Signature"] = _sign_identity_assertion(
            secret=trusted_proxy_secret,
            actor_id=actor_id,
            actor_type=actor_type,
            actor_role=actor_role,
            timestamp=asserted_at,
        )
    return headers


OPERATOR_HEADERS = {
    "X-Actor-ID": DEFAULT_ACTOR_ID,
    "X-Actor-Type": "human",
    "X-Actor-Role": DEFAULT_ACTOR_ROLE,
}


def _request(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float,
) -> tuple[int, str, str]:
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}", headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, response.headers.get("content-type", ""), body


def _json(body: str) -> Any:
    return json.loads(body)


def _wait_for(
    name: str,
    check: Any,
    *,
    attempts: int,
    interval: float,
) -> dict[str, Any]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            return {"name": name, "attempt": attempt, "ok": True, **check()}
        except Exception as exc:  # noqa: BLE001 - smoke output should preserve any failure.
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(interval)
    raise RuntimeError(f"{name} failed after {attempts} attempts: {last_error}")


def run_smoke(
    *,
    base_url: str,
    attempts: int,
    interval: float,
    timeout: float,
    require_worker: bool,
    actor_id: str = DEFAULT_ACTOR_ID,
    actor_type: str = DEFAULT_ACTOR_TYPE,
    actor_role: str = DEFAULT_ACTOR_ROLE,
    trusted_proxy_secret: str | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def live() -> dict[str, Any]:
        status, content_type, body = _request(base_url, "/health/live", timeout=timeout)
        payload = _json(body)
        if status != 200 or payload.get("status") != "ok":
            raise RuntimeError(f"unexpected live response: {status} {body}")
        return {"status": status, "content_type": content_type, "payload": payload}

    def ready() -> dict[str, Any]:
        status, content_type, body = _request(base_url, "/health/ready", timeout=timeout)
        payload = _json(body)
        if status != 200 or payload.get("status") != "ok":
            raise RuntimeError(f"unexpected ready response: {status} {body}")
        if payload.get("database") != "reachable":
            raise RuntimeError(f"database is not reachable: {body}")
        return {"status": status, "content_type": content_type, "payload": payload}

    def metrics() -> dict[str, Any]:
        status, content_type, body = _request(base_url, "/metrics", timeout=timeout)
        if status != 200 or "ai_enterprise_process_uptime_seconds" not in body:
            raise RuntimeError("metrics endpoint did not expose process uptime")
        if "ai_enterprise_http_requests_total" not in body:
            raise RuntimeError("metrics endpoint did not expose HTTP counters")
        return {"status": status, "content_type": content_type, "bytes": len(body)}

    def workers() -> dict[str, Any]:
        status, content_type, body = _request(
            base_url,
            "/api/v1/operator/jobs/worker-instances",
            headers=operator_headers(
                actor_id=actor_id,
                actor_type=actor_type,
                actor_role=actor_role,
                trusted_proxy_secret=trusted_proxy_secret,
            ),
            timeout=timeout,
        )
        payload = _json(body)
        if status != 200 or not isinstance(payload, list):
            raise RuntimeError(f"unexpected worker response: {status} {body}")
        if require_worker and not payload:
            raise RuntimeError("no worker instances are visible")
        visible_statuses = sorted({str(item.get("status")) for item in payload})
        return {
            "status": status,
            "content_type": content_type,
            "worker_count": len(payload),
            "worker_statuses": visible_statuses,
        }

    checks.append(_wait_for("health_live", live, attempts=attempts, interval=interval))
    checks.append(_wait_for("health_ready", ready, attempts=attempts, interval=interval))
    checks.append(_wait_for("metrics", metrics, attempts=attempts, interval=interval))
    checks.append(_wait_for("worker_visibility", workers, attempts=attempts, interval=interval))
    return {
        "conformant": True,
        "base_url": base_url,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-check a running local Docker stack.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--require-worker", action="store_true")
    parser.add_argument("--actor-id", default=os.getenv("DOCKER_SMOKE_ACTOR_ID", DEFAULT_ACTOR_ID))
    parser.add_argument(
        "--actor-type",
        default=os.getenv("DOCKER_SMOKE_ACTOR_TYPE", DEFAULT_ACTOR_TYPE),
    )
    parser.add_argument(
        "--actor-role",
        default=os.getenv("DOCKER_SMOKE_ACTOR_ROLE", DEFAULT_ACTOR_ROLE),
    )
    parser.add_argument(
        "--trusted-proxy-secret",
        default=os.getenv("TRUSTED_PROXY_HMAC_SECRET") or None,
    )
    args = parser.parse_args()

    try:
        report = run_smoke(
            base_url=args.base_url,
            attempts=args.attempts,
            interval=args.interval,
            timeout=args.timeout,
            require_worker=args.require_worker,
            actor_id=args.actor_id,
            actor_type=args.actor_type,
            actor_role=args.actor_role,
            trusted_proxy_secret=args.trusted_proxy_secret,
        )
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps({"conformant": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
