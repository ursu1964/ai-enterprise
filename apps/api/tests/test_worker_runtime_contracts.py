import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

import ai_enterprise.worker as worker_module
from ai_enterprise.config import Settings
from ai_enterprise.domain.review.exceptions import ReviewRuntimeError
from ai_enterprise.infrastructure.review.review_runtime import (
    DockerReviewRuntime,
    ReviewCheckResult,
)


def test_worker_timing_rejects_lease_and_stale_windows_too_close_to_heartbeat() -> None:
    with pytest.raises(ValidationError, match="three heartbeat intervals"):
        Settings(_env_file=None, worker_heartbeat_seconds=10, worker_lease_seconds=29)
    with pytest.raises(ValidationError, match="two heartbeat intervals"):
        Settings(
            _env_file=None,
            worker_heartbeat_seconds=10,
            worker_lease_seconds=30,
            worker_stale_after_seconds=19,
        )


def test_review_check_result_keeps_backward_compatible_default_type() -> None:
    result = ReviewCheckResult(
        name="ruff",
        argv=("ruff", "check"),
        exit_code=0,
        duration_ms=12,
        stdout="",
        stderr="",
        timed_out=False,
        required=True,
    )

    assert result.check_type == "review_check"


def test_review_result_contract_rejects_malformed_or_incomplete_artifacts(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"
    result_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(ReviewRuntimeError, match="result.json contract is invalid"):
        DockerReviewRuntime._read_result(result_path)

    result_path.write_text(
        json.dumps({"success": True, "review_checks": [{"name": "ruff"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ReviewRuntimeError, match=r"review_checks\[0\] is missing"):
        DockerReviewRuntime._read_result(result_path)


class _Context:
    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    def begin(self) -> "_Context":
        return self


class _FailingRepository:
    def __init__(self, _: Any) -> None:
        pass

    async def extend_lease(self, **_: Any) -> bool:
        raise ConnectionError("database unavailable")


@pytest.mark.asyncio
async def test_heartbeat_failure_signals_lease_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_module, "SessionFactory", lambda: _Context())
    monkeypatch.setattr(worker_module, "JobRepository", _FailingRepository)
    lease_lost = asyncio.Event()

    await worker_module._heartbeat_job(
        worker_id="worker-1",
        job_id=uuid.uuid4(),
        lease_token=uuid.uuid4(),
        lease_version=1,
        lease_seconds=30,
        interval=0,
        lease_lost=lease_lost,
    )

    assert lease_lost.is_set()
