import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest


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


configure_local_executor = _load("configure_local_executor")
REPO_ROOT = _repo_root()


def test_local_executor_configuration_prints_exact_env(monkeypatch: pytest.MonkeyPatch) -> None:
    image_ids = {
        "ai-enterprise-execution-agent:local": "sha256:" + "a" * 64,
        "ai-enterprise-review-agent:local": "sha256:" + "b" * 64,
    }

    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        assert check is True
        assert capture_output is True
        assert text is True
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f'{{"Id": "{image_ids[command[3]]}"}}',
            stderr="",
        )

    monkeypatch.setattr(configure_local_executor.subprocess, "run", fake_run)

    config = configure_local_executor.local_executor_configuration()

    report = config.json()
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == configure_local_executor.LOCAL_EXECUTOR_CONFIGURATION_SCHEMA_REF
    assert report["ok"] is True
    schema = json.loads((REPO_ROOT / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    assert config.dotenv() == (
        "EXECUTION_CONTAINER_PROVIDER=restricted-local-docker\n"
        "EXECUTION_IMAGE=ai-enterprise-execution-agent:local\n"
        f"EXECUTION_IMAGE_ID={'sha256:' + 'a' * 64}\n"
        "REVIEW_IMAGE=ai-enterprise-review-agent:local\n"
        f"REVIEW_IMAGE_ID={'sha256:' + 'b' * 64}\n"
    )


def test_local_executor_configuration_rejects_mutable_or_invalid_image_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(
        command: list[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, stdout='{"Id": "latest"}', stderr="")

    monkeypatch.setattr(configure_local_executor.subprocess, "run", fake_run)

    with pytest.raises(
        configure_local_executor.LocalExecutorConfigurationError,
        match="immutable sha256 image ID",
    ):
        configure_local_executor.docker_image_id("ai-enterprise-execution-agent:local")


def test_write_env_file_is_non_destructive_by_default(tmp_path: Path) -> None:
    target = tmp_path / ".env.local-executor"
    target.write_text("KEEP=1\n", encoding="utf-8")

    with pytest.raises(
        configure_local_executor.LocalExecutorConfigurationError,
        match="already exists",
    ):
        configure_local_executor.write_env_file(target, "NEW=1\n", force=False)

    assert target.read_text(encoding="utf-8") == "KEEP=1\n"

    configure_local_executor.write_env_file(target, "NEW=1\n", force=True)

    assert target.read_text(encoding="utf-8") == "NEW=1\n"


def test_local_executor_configuration_failure_report_is_schema_valid() -> None:
    report = configure_local_executor._failure_report("docker CLI is not installed")

    assert report["ok"] is False
    assert report["schema_ref"] == configure_local_executor.LOCAL_EXECUTOR_CONFIGURATION_SCHEMA_REF
    schema = json.loads((REPO_ROOT / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)


def test_local_executor_configuration_report_validation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = configure_local_executor._failure_report("docker CLI is not installed")
    schema = dict(configure_local_executor._schema())
    schema["required"] = [*schema["required"], "impossible_field"]
    monkeypatch.setattr(configure_local_executor, "_schema", lambda: schema)

    with pytest.raises(
        RuntimeError,
        match="local executor configuration report does not validate",
    ):
        configure_local_executor._validate_report(report)
