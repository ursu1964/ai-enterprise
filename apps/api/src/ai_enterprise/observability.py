import json
import logging
import sys
import threading
import time
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_metrics: dict[str, int | float] = {}
_lock = threading.Lock()
_process_started_at = time.time()


def increment_metric(name: str, amount: int = 1) -> None:
    with _lock:
        _metrics[name] = _metrics.get(name, 0) + amount


def observe_duration(name: str, seconds: float) -> None:
    """Record dependency-free count, sum, and max latency signals."""
    milliseconds = max(0.0, seconds * 1000)
    with _lock:
        count = f"{name}_count"
        total = f"{name}_milliseconds_sum"
        _metrics[count] = _metrics.get(count, 0) + 1
        _metrics[total] = _metrics.get(total, 0) + milliseconds
        maximum = f"{name}_milliseconds_max"
        _metrics[maximum] = max(float(_metrics.get(maximum, 0)), milliseconds)


def metrics_snapshot() -> dict[str, int | float]:
    with _lock:
        snapshot: dict[str, int | float] = dict(_metrics)
    snapshot["process_uptime_seconds"] = round(time.time() - _process_started_at, 3)
    return snapshot


def prometheus_metrics_snapshot(labels: Mapping[str, str] | None = None) -> str:
    snapshot = metrics_snapshot()
    label_text = _format_labels(labels or {})
    lines = [
        "# HELP ai_enterprise_metric Runtime metric emitted by AI Enterprise.",
        "# TYPE ai_enterprise_metric gauge",
    ]
    for name, value in sorted(snapshot.items()):
        lines.append(f"ai_enterprise_{_sanitize_metric_name(name)}{label_text} {value}")
    return "\n".join(lines) + "\n"


def _sanitize_metric_name(name: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in name).strip("_")


def _format_labels(labels: Mapping[str, str]) -> str:
    if not labels:
        return ""
    pairs = ",".join(
        f'{_sanitize_metric_name(key)}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
        for key, value in sorted(labels.items())
    )
    return "{" + pairs + "}"


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
