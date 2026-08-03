from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docker.client import DockerClient, from_env
from docker.errors import APIError, ImageNotFound

from ai_enterprise.domain.execution.exceptions import (
    ContainerExecutionError,
    ExecutionTimeoutError,
)
from ai_enterprise.domain.execution.policies import RuntimeLimits

MAXIMUM_RESULT_BYTES = 8 * 1024 * 1024
MAXIMUM_RUNTIME_LOG_BYTES = 4 * 1024 * 1024
MAXIMUM_COMMAND_OUTPUT_CHARS = 2 * 1024 * 1024
RUNTIME_UID = 10001
RUNTIME_GID = 10001


@dataclass(frozen=True, slots=True)
class ContainerTestResult:
    name: str
    argv: tuple[str, ...]
    exit_code: int | None
    duration_ms: int
    stdout: str
    stderr: str
    timed_out: bool
    required: bool


@dataclass(frozen=True, slots=True)
class ContainerRunResult:
    container_id: str
    container_image: str
    container_image_digest: str | None
    exit_code: int
    implementation: dict[str, Any]
    tests: tuple[ContainerTestResult, ...]
    success: bool
    runtime_log: str


class DockerExecutionRuntime:
    def __init__(self, docker_base_url: str | None = None) -> None:
        if docker_base_url:
            self._client = DockerClient(base_url=docker_base_url)
        else:
            self._client = from_env()

        self._client.ping()

    def run(
        self,
        *,
        execution_id: str,
        image: str,
        snapshot_path: Path,
        runtime_input: dict[str, Any],
        runtime_temp_root: Path,
        limits: RuntimeLimits,
        edits: list[dict[str, Any]] | None = None,
    ) -> ContainerRunResult:
        invocation_root = runtime_temp_root / execution_id
        input_dir = invocation_root / "input"
        output_dir = invocation_root / "output"

        shutil.rmtree(invocation_root, ignore_errors=True)
        input_dir.mkdir(parents=True, mode=0o700)
        output_dir.mkdir(parents=True, mode=0o700)

        input_path = input_dir / "execution.json"
        input_path.write_text(
            json.dumps(runtime_input, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        input_path.chmod(0o400)
        os.chown(input_path, RUNTIME_UID, RUNTIME_GID)

        if edits is not None:
            edits_path = input_dir / "edits.json"
            edits_path.write_text(
                json.dumps(edits, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            edits_path.chmod(0o400)
            os.chown(edits_path, RUNTIME_UID, RUNTIME_GID)

        os.chown(input_dir, RUNTIME_UID, RUNTIME_GID)
        os.chown(output_dir, RUNTIME_UID, RUNTIME_GID)

        container = None

        try:
            image_object = self._client.images.get(image)
            image_digest = self._extract_digest(image_object.attrs)

            container = self._client.containers.run(
                image=image,
                name=f"ai-execution-{execution_id}",
                detach=True,
                auto_remove=False,
                network_disabled=True,
                read_only=True,
                user="10001:10001",
                working_dir="/workspace",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                privileged=False,
                nano_cpus=limits.nano_cpus,
                mem_limit=limits.memory_bytes,
                memswap_limit=limits.memory_swap_bytes,
                pids_limit=limits.pids_limit,
                init=True,
                stdin_open=False,
                tty=False,
                environment={
                    "EXECUTION_ID": execution_id,
                },
                volumes={
                    str(snapshot_path.resolve()): {
                        "bind": "/workspace",
                        "mode": "rw",
                    },
                    str(input_dir.resolve()): {
                        "bind": "/runtime-input",
                        "mode": "ro",
                    },
                    str(output_dir.resolve()): {
                        "bind": "/runtime-output",
                        "mode": "rw",
                    },
                },
                tmpfs={
                    "/tmp": (
                        f"rw,noexec,nosuid,nodev,"
                        f"size={limits.tmpfs_size_bytes},mode=1777"
                    ),
                    "/home/runtime": (
                        "rw,noexec,nosuid,nodev,size=16777216,mode=0700,"
                        "uid=10001,gid=10001"
                    ),
                },
                labels={
                    "ai.enterprise.execution-id": execution_id,
                    "ai.enterprise.managed": "true",
                },
            )

            wait_result = self._wait_with_timeout(
                container=container,
                timeout_seconds=limits.timeout_seconds,
            )

            exit_code = int(wait_result["StatusCode"])

            runtime_log = self._read_runtime_log(
                output_dir=output_dir,
                container=container,
            )

            result_path = output_dir / "result.json"

            if not result_path.is_file():
                raise ContainerExecutionError(
                    "Container produced no result.json"
                )

            result_data = self._read_result(
                result_path=result_path,
                runtime_input=runtime_input,
                container_exit_code=exit_code,
            )

            tests = tuple(
                ContainerTestResult(
                    name=item["name"],
                    argv=tuple(item["argv"]),
                    exit_code=item["exit_code"],
                    duration_ms=item["duration_ms"],
                    stdout=item["stdout"],
                    stderr=item["stderr"],
                    timed_out=item["timed_out"],
                    required=item.get("required", True),
                )
                for item in result_data.get("tests", [])
            )

            return ContainerRunResult(
                container_id=container.id,
                container_image=image,
                container_image_digest=image_digest,
                exit_code=exit_code,
                implementation=result_data["implementation"],
                tests=tests,
                success=bool(result_data["success"]),
                runtime_log=runtime_log,
            )
        except ImageNotFound as exc:
            raise ContainerExecutionError(
                f"Execution image not found: {image}"
            ) from exc
        except APIError as exc:
            raise ContainerExecutionError(
                f"Docker API error: {exc}"
            ) from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError:
                    pass

    def _read_runtime_log(
        self,
        *,
        output_dir: Path,
        container: Any,
    ) -> str:
        log_path = output_dir / "runtime.log"

        if log_path.is_file():
            return self._read_bounded_text(
                log_path,
                maximum_bytes=MAXIMUM_RUNTIME_LOG_BYTES,
            )

        log_chunks = container.logs(
            stdout=True,
            stderr=True,
            timestamps=True,
            stream=True,
        )

        buffered = bytearray()

        for chunk in log_chunks:
            buffered.extend(chunk)

            if len(buffered) > MAXIMUM_RUNTIME_LOG_BYTES:
                raise ContainerExecutionError("Container log exceeds size limit")

        return bytes(buffered).decode("utf-8", errors="replace")

    @classmethod
    def _read_result(
        cls,
        *,
        result_path: Path,
        runtime_input: dict[str, Any],
        container_exit_code: int,
    ) -> dict[str, Any]:
        encoded = cls._read_bounded_bytes(
            result_path,
            maximum_bytes=MAXIMUM_RESULT_BYTES,
        )

        try:
            result = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContainerExecutionError("Container result is invalid JSON") from exc

        if not isinstance(result, dict) or result.get("schema_version") != 1:
            raise ContainerExecutionError("Unsupported container result schema")

        implementation = cls._validate_command_result(
            result.get("implementation"),
            expected_name="implementation",
            expected_argv=runtime_input["implementation"]["argv"],
        )

        raw_tests = result.get("tests")
        expected_tests = runtime_input.get("tests", [])

        if not isinstance(raw_tests, list):
            raise ContainerExecutionError("Container test results must be a list")

        implementation_passed = (
            not implementation["timed_out"]
            and implementation["exit_code"] == 0
        )

        if implementation_passed and len(raw_tests) != len(expected_tests):
            raise ContainerExecutionError("Not every approved test was attempted")

        if not implementation_passed and raw_tests:
            raise ContainerExecutionError("Tests ran after implementation failure")

        validated_tests: list[dict[str, Any]] = []

        for index, raw_test in enumerate(raw_tests):
            expected_test = expected_tests[index]
            validated = cls._validate_command_result(
                raw_test,
                expected_name=f"test-{index}",
                expected_argv=expected_test["argv"],
            )
            expected_required = bool(expected_test.get("required", True))

            if not isinstance(validated.get("required", True), bool):
                raise ContainerExecutionError("Invalid test required flag")

            if validated.get("required", True) is not expected_required:
                raise ContainerExecutionError("Test required flag does not match approval")

            validated["required"] = expected_required
            validated_tests.append(validated)

        expected_success = implementation_passed and all(
            (not test["timed_out"] and test["exit_code"] == 0)
            for test in validated_tests
            if test["required"]
        )

        if result.get("success") is not expected_success:
            raise ContainerExecutionError("Container success flag is inconsistent")

        expected_exit_code = 0 if expected_success else (30 if implementation_passed else 20)

        if container_exit_code != expected_exit_code:
            raise ContainerExecutionError(
                "Container exit code is inconsistent with command results"
            )

        result["implementation"] = implementation
        result["tests"] = validated_tests
        return result

    @staticmethod
    def _validate_command_result(
        value: object,
        *,
        expected_name: str,
        expected_argv: object,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ContainerExecutionError("Command result must be an object")

        if value.get("name") != expected_name or value.get("argv") != expected_argv:
            raise ContainerExecutionError("Command result does not match approved command")

        exit_code = value.get("exit_code")
        timed_out = value.get("timed_out")
        duration_ms = value.get("duration_ms")
        stdout = value.get("stdout")
        stderr = value.get("stderr")

        if not isinstance(timed_out, bool):
            raise ContainerExecutionError("Invalid command timeout status")

        if isinstance(exit_code, bool) or not (
            exit_code is None or isinstance(exit_code, int)
        ):
            raise ContainerExecutionError("Invalid command exit code")

        if timed_out != (exit_code is None):
            raise ContainerExecutionError("Command timeout and exit code disagree")

        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int) or duration_ms < 0:
            raise ContainerExecutionError("Invalid command duration")

        if not isinstance(stdout, str) or not isinstance(stderr, str):
            raise ContainerExecutionError("Invalid command output")

        if len(stdout) > MAXIMUM_COMMAND_OUTPUT_CHARS or len(stderr) > MAXIMUM_COMMAND_OUTPUT_CHARS:
            raise ContainerExecutionError("Command output exceeds size limit")

        return dict(value)

    @staticmethod
    def _read_bounded_text(path: Path, *, maximum_bytes: int) -> str:
        data = DockerExecutionRuntime._read_bounded_bytes(
            path,
            maximum_bytes=maximum_bytes,
        )

        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _read_bounded_bytes(path: Path, *, maximum_bytes: int) -> bytes:
        with path.open("rb") as handle:
            data = handle.read(maximum_bytes + 1)

        if len(data) > maximum_bytes:
            raise ContainerExecutionError(f"{path.name} exceeds size limit")

        return data

    @staticmethod
    def _wait_with_timeout(
        *,
        container: Any,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        started = time.monotonic()

        while True:
            container.reload()

            if container.status in {"exited", "dead"}:
                return container.wait(timeout=10)

            if time.monotonic() - started >= timeout_seconds:
                try:
                    container.kill(signal="SIGKILL")
                finally:
                    raise ExecutionTimeoutError(
                        f"Execution exceeded {timeout_seconds} seconds"
                    )

            time.sleep(0.5)

    @staticmethod
    def _extract_digest(attrs: dict[str, Any]) -> str | None:
        repo_digests = attrs.get("RepoDigests") or []

        if not repo_digests:
            return None

        first = str(repo_digests[0])

        if "@" not in first:
            return None

        return first.split("@", maxsplit=1)[1]
