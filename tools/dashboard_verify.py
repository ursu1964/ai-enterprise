#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jsonschema

DEFAULT_ACTOR_ID = "local-dashboard-admin"
DEFAULT_ACTOR_TYPE = "human"
DEFAULT_ACTOR_ROLE = "platform-admin"
DASHBOARD_SCHEMA_REF = "schemas/release-artifacts/dashboard-verification-report.schema.json"

CRITICAL_DASHBOARD_TEXT = [
    "AI Enterprise Command Center",
    "Business decision board",
    "state.dashboardManager?.business_board",
    "Project Execution Control",
    "Guided Recovery Center",
    "Graph Hub",
]

CRITICAL_DEMO_TEXT = [
    "AI Enterprise Demo Story",
    "Idea to Reality Map",
    "Step-by-Step Live Demo",
    "Demo Operator Console",
]

CRITICAL_DOCUMENTATION_TEXT = [
    "Documentation Hub",
    "Operator Documents",
    "Document Preview",
    "Graphs and Images",
    "Commands",
]

CRYPTIC_PRIMARY_TEXT = [
    "No records.",
    "Data is incomplete",
    "project(s)",
    "worker(s)",
    "problem(s)",
    "data source(s)",
    "proof item(s)",
    "queued, leased",
]


def operator_headers(
    *,
    actor_id: str = DEFAULT_ACTOR_ID,
    actor_type: str = DEFAULT_ACTOR_TYPE,
    actor_role: str = DEFAULT_ACTOR_ROLE,
) -> dict[str, str]:
    return {
        "X-Actor-ID": actor_id,
        "X-Actor-Type": actor_type,
        "X-Actor-Role": actor_role,
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


def _missing(body: str, expected: list[str]) -> list[str]:
    return [item for item in expected if item not in body]


def _present(body: str, blocked: list[str]) -> list[str]:
    return [item for item in blocked if item in body]


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
        except Exception as exc:  # noqa: BLE001 - verifier output should preserve root cause.
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(interval)
    raise RuntimeError(f"{name} failed after {attempts} attempts: {last_error}")


def _assert_page(
    *,
    base_url: str,
    path: str,
    expected: list[str],
    timeout: float,
) -> dict[str, Any]:
    status, content_type, body = _request(base_url, path, timeout=timeout)
    if status != 200:
        raise RuntimeError(f"{path} returned {status}")
    missing = _missing(body, expected)
    if missing:
        raise RuntimeError(f"{path} is missing required text: {', '.join(missing)}")
    cryptic = _present(body, CRYPTIC_PRIMARY_TEXT)
    if cryptic:
        raise RuntimeError(f"{path} exposes cryptic primary text: {', '.join(cryptic)}")
    return {
        "status": status,
        "content_type": content_type,
        "bytes": len(body),
        "required_text": len(expected),
    }


def _assert_manager(
    *,
    base_url: str,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    status, content_type, body = _request(
        base_url,
        "/api/v1/query/dashboard-manager",
        headers=headers,
        timeout=timeout,
    )
    payload = _json(body)
    if status != 200:
        raise RuntimeError(f"dashboard manager returned {status}")
    board = payload.get("business_board")
    if not isinstance(board, dict):
        raise TypeError("dashboard manager did not return business_board")
    cards = board.get("cards")
    if not isinstance(cards, list) or len(cards) != 4:
        raise RuntimeError("business_board must contain four primary cards")
    titles = [str(card.get("title", "")) for card in cards]
    expected_titles = [
        "Business State",
        "Value in Motion",
        "Risk and Attention",
        "Recommended Next Move",
    ]
    if titles != expected_titles:
        raise RuntimeError(f"unexpected business_board titles: {titles}")
    next_step = board.get("next")
    if not isinstance(next_step, dict) or not next_step.get("target"):
        raise RuntimeError("business_board next action needs a dashboard target")
    card_text = " ".join(
        " ".join(str(card.get(key, "")) for key in ("title", "message", "effect")) for card in cards
    )
    cryptic = _present(card_text, CRYPTIC_PRIMARY_TEXT)
    if cryptic:
        raise RuntimeError(f"business_board exposes cryptic text: {', '.join(cryptic)}")
    return {
        "status": status,
        "content_type": content_type,
        "state": payload.get("headline", {}).get("state"),
        "project_count": payload.get("totals", {}).get("projects"),
        "next_target": next_step["target"],
        "card_count": len(cards),
    }


def run_dashboard_verify(
    *,
    base_url: str,
    attempts: int,
    interval: float,
    timeout: float,
    actor_id: str = DEFAULT_ACTOR_ID,
    actor_type: str = DEFAULT_ACTOR_TYPE,
    actor_role: str = DEFAULT_ACTOR_ROLE,
) -> dict[str, Any]:
    headers = operator_headers(
        actor_id=actor_id,
        actor_type=actor_type,
        actor_role=actor_role,
    )
    checks = [
        _wait_for(
            "dashboard_page",
            lambda: _assert_page(
                base_url=base_url,
                path="/dashboard",
                expected=CRITICAL_DASHBOARD_TEXT,
                timeout=timeout,
            ),
            attempts=attempts,
            interval=interval,
        ),
        _wait_for(
            "demo_story_page",
            lambda: _assert_page(
                base_url=base_url,
                path="/dashboard/demo",
                expected=CRITICAL_DEMO_TEXT,
                timeout=timeout,
            ),
            attempts=attempts,
            interval=interval,
        ),
        _wait_for(
            "documentation_hub_page",
            lambda: _assert_page(
                base_url=base_url,
                path="/dashboard/documentation-hub",
                expected=CRITICAL_DOCUMENTATION_TEXT,
                timeout=timeout,
            ),
            attempts=attempts,
            interval=interval,
        ),
        _wait_for(
            "dashboard_manager_business_board",
            lambda: _assert_manager(
                base_url=base_url,
                headers=headers,
                timeout=timeout,
            ),
            attempts=attempts,
            interval=interval,
        ),
    ]
    report = {
        "conformant": True,
        "base_url": base_url,
        "checks": checks,
        "schema_version": "1.0",
        "schema_ref": DASHBOARD_SCHEMA_REF,
    }
    _validate_report(report)
    return report


def _schema() -> dict[str, Any]:
    for candidate in Path(__file__).resolve().parents:
        schema_path = candidate / DASHBOARD_SCHEMA_REF
        if schema_path.is_file():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            return schema
    raise RuntimeError(f"{DASHBOARD_SCHEMA_REF} schema file is missing")


def _validate_report(report: dict[str, Any]) -> None:
    try:
        jsonschema.validate(report, _schema())
    except jsonschema.ValidationError as exc:
        raise RuntimeError(
            f"{DASHBOARD_SCHEMA_REF}: generated dashboard verification report "
            f"does not validate: {exc.message}"
        ) from exc


def _failure_report(error: str) -> dict[str, Any]:
    report = {
        "conformant": False,
        "error": error,
        "schema_version": "1.0",
        "schema_ref": DASHBOARD_SCHEMA_REF,
    }
    _validate_report(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify live dashboard pages and manager read-model contracts."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--attempts", type=int, default=10)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--actor-id", default=DEFAULT_ACTOR_ID)
    parser.add_argument("--actor-type", default=DEFAULT_ACTOR_TYPE)
    parser.add_argument("--actor-role", default=DEFAULT_ACTOR_ROLE)
    args = parser.parse_args()

    try:
        report = run_dashboard_verify(
            base_url=args.base_url,
            attempts=args.attempts,
            interval=args.interval,
            timeout=args.timeout,
            actor_id=args.actor_id,
            actor_type=args.actor_type,
            actor_role=args.actor_role,
        )
    except (RuntimeError, urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps(_failure_report(str(exc)), sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
