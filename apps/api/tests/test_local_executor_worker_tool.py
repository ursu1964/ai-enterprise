import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from ai_enterprise.domain.enums import JobType
from ai_enterprise.infrastructure.jobs.readiness import SetupBlocker, WorkerReadiness


def _load(name: str):
    root = _repo_root()
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Unable to locate repository root from test path")


local_executor_worker = _load("local_executor_worker")
REPO_ROOT = _repo_root()


def test_activation_env_uses_generated_image_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        local_executor_worker,
        "local_executor_configuration",
        lambda: SimpleNamespace(
            execution_image="execution:local",
            execution_image_id="sha256:" + "a" * 64,
            review_image="review:local",
            review_image_id="sha256:" + "b" * 64,
        ),
    )

    env = local_executor_worker.activation_env({"PYTHONPATH": "existing"})

    assert env["EXECUTION_CONTAINER_PROVIDER"] == "restricted-local-docker"
    assert env["EXECUTION_IMAGE_ID"] == "sha256:" + "a" * 64
    assert env["REVIEW_IMAGE_ID"] == "sha256:" + "b" * 64
    assert env["WORKER_PROFILE"] == "general"
    assert str(local_executor_worker.API_SRC) in env["PYTHONPATH"]
    assert "existing" in env["PYTHONPATH"]


@pytest.mark.asyncio
async def test_executor_readiness_report_is_limited_to_execution_job_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_candidates: list[frozenset[JobType]] = []

    async def fake_readiness(settings: object, candidates: frozenset[JobType]) -> WorkerReadiness:
        assert settings.execution_container_provider == "restricted-local-docker"  # type: ignore[attr-defined]
        seen_candidates.append(candidates)
        return WorkerReadiness(permitted_job_types=candidates, blockers=())

    monkeypatch.setattr(local_executor_worker, "assess_worker_readiness", fake_readiness)

    report = await local_executor_worker.readiness_report(
        {
            "EXECUTION_CONTAINER_PROVIDER": "restricted-local-docker",
            "EXECUTION_IMAGE": "execution:local",
            "EXECUTION_IMAGE_ID": "sha256:" + "a" * 64,
            "REVIEW_IMAGE": "review:local",
            "REVIEW_IMAGE_ID": "sha256:" + "b" * 64,
        },
        scope="executor",
    )

    assert report["ok"] is True
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == local_executor_worker.LOCAL_EXECUTOR_WORKER_SCHEMA_REF
    schema = json.loads((REPO_ROOT / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    assert seen_candidates == [
        frozenset({JobType.EXECUTE_WORK_PACKAGE, JobType.REVIEW_CANDIDATE_PATCH})
    ]


@pytest.mark.asyncio
async def test_readiness_report_preserves_blocker_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_readiness(_settings: object, candidates: frozenset[JobType]) -> WorkerReadiness:
        return WorkerReadiness(
            permitted_job_types=frozenset(),
            blockers=(
                SetupBlocker(
                    code="docker_runtime_unavailable",
                    capability="container_execution",
                    job_types=candidates,
                    detail="Docker is not reachable.",
                    next_action="Run the host worker only where Docker is approved.",
                ),
            ),
        )

    monkeypatch.setattr(local_executor_worker, "assess_worker_readiness", fake_readiness)

    report = await local_executor_worker.readiness_report(
        {
            "EXECUTION_CONTAINER_PROVIDER": "restricted-local-docker",
            "EXECUTION_IMAGE": "execution:local",
            "EXECUTION_IMAGE_ID": "sha256:" + "a" * 64,
            "REVIEW_IMAGE": "review:local",
            "REVIEW_IMAGE_ID": "sha256:" + "b" * 64,
        },
        scope="executor",
    )

    assert report["ok"] is False
    assert report["blockers"][0]["code"] == "docker_runtime_unavailable"
    assert report["blockers"][0]["next_action"] == (
        "Run the host worker only where Docker is approved."
    )


@pytest.mark.asyncio
async def test_local_executor_worker_report_validation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_readiness(_settings: object, candidates: frozenset[JobType]) -> WorkerReadiness:
        return WorkerReadiness(permitted_job_types=candidates, blockers=())

    monkeypatch.setattr(local_executor_worker, "assess_worker_readiness", fake_readiness)
    schema = dict(local_executor_worker._schema())
    schema["required"] = [*schema["required"], "impossible_field"]
    monkeypatch.setattr(local_executor_worker, "_schema", lambda: schema)

    with pytest.raises(RuntimeError, match="local executor worker report does not validate"):
        await local_executor_worker.readiness_report(
            {
                "EXECUTION_CONTAINER_PROVIDER": "restricted-local-docker",
                "EXECUTION_IMAGE": "execution:local",
                "EXECUTION_IMAGE_ID": "sha256:" + "a" * 64,
                "REVIEW_IMAGE": "review:local",
                "REVIEW_IMAGE_ID": "sha256:" + "b" * 64,
            },
            scope="executor",
        )
