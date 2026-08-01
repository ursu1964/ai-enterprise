from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from ai_enterprise.domain.execution.exceptions import (
    ContainerExecutionError,
    ScopeViolationError,
)
from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.infrastructure.execution.docker_runtime import (
    MAXIMUM_RESULT_BYTES,
    DockerExecutionRuntime,
)
from ai_enterprise.infrastructure.execution.scope_validator import ScopeValidator


def _git(repository: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        },
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    (repository / "allowed").mkdir()
    (repository / "allowed" / "file.txt").write_text("base\n", encoding="utf-8")
    (repository / "forbidden").mkdir()
    (repository / "forbidden" / "secret.txt").write_text("base\n", encoding="utf-8")
    _git(repository, "add", "--all")
    _git(repository, "commit", "--quiet", "-m", "base")
    return repository


def _scope() -> ExecutionScope:
    return ExecutionScope(
        allowed_paths=("allowed",),
        forbidden_paths=("forbidden",),
    )


def test_scope_rejects_rename_from_forbidden_path(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "forbidden" / "secret.txt").rename(
        repository / "allowed" / "renamed.txt"
    )

    with pytest.raises(ScopeViolationError, match="forbidden/secret.txt"):
        ScopeValidator().inspect(
            repository=repository,
            scope=_scope(),
            maximum_changed_files=10,
        )


def test_scope_rejects_changed_symlink_that_escapes_snapshot(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "allowed" / "escape").symlink_to("../../outside")

    with pytest.raises(ScopeViolationError, match="symlink escapes"):
        ScopeValidator().inspect(
            repository=repository,
            scope=_scope(),
            maximum_changed_files=10,
        )


def test_scope_rejects_submodule_pointer_change(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    first = "1" * 40
    second = "2" * 40
    _git(repository, "update-index", "--add", "--cacheinfo", f"160000,{first},allowed/sub")
    _git(repository, "commit", "--quiet", "-m", "add gitlink")
    _git(repository, "update-index", "--cacheinfo", f"160000,{second},allowed/sub")

    with pytest.raises(ScopeViolationError, match="Submodule pointer"):
        ScopeValidator().inspect(
            repository=repository,
            scope=_scope(),
            maximum_changed_files=10,
        )


def _runtime_input() -> dict[str, object]:
    return {
        "implementation": {"argv": ["python", "/opt/runtime/apply_edits.py"]},
        "tests": [
            {
                "argv": ["python", "-m", "pytest"],
                "required": True,
            }
        ],
    }


def _command(name: str, argv: list[str]) -> dict[str, object]:
    return {
        "name": name,
        "argv": argv,
        "exit_code": 0,
        "duration_ms": 1,
        "stdout": "",
        "stderr": "",
        "timed_out": False,
    }


def test_result_rejects_omitted_approved_test(tmp_path: Path) -> None:
    runtime_input = _runtime_input()
    result = {
        "schema_version": 1,
        "implementation": _command(
            "implementation", runtime_input["implementation"]["argv"]
        ),
        "tests": [],
        "success": True,
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ContainerExecutionError, match="approved test"):
        DockerExecutionRuntime._read_result(
            result_path=result_path,
            runtime_input=runtime_input,
            container_exit_code=0,
        )


def test_result_rejects_command_substitution(tmp_path: Path) -> None:
    runtime_input = _runtime_input()
    result = {
        "schema_version": 1,
        "implementation": _command(
            "implementation", runtime_input["implementation"]["argv"]
        ),
        "tests": [
            {
                **_command("test-0", ["python", "-c", "print('forged')"]),
                "required": True,
            }
        ],
        "success": True,
    }
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ContainerExecutionError, match="approved command"):
        DockerExecutionRuntime._read_result(
            result_path=result_path,
            runtime_input=runtime_input,
            container_exit_code=0,
        )


def test_result_read_is_bounded(tmp_path: Path) -> None:
    result_path = tmp_path / "result.json"

    with result_path.open("wb") as handle:
        handle.truncate(MAXIMUM_RESULT_BYTES + 1)

    with pytest.raises(ContainerExecutionError, match="size limit"):
        DockerExecutionRuntime._read_result(
            result_path=result_path,
            runtime_input=_runtime_input(),
            container_exit_code=0,
        )
