from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError, ImageNotFound

from ai_enterprise.domain.execution.exceptions import (
    ContainerExecutionError,
    ExecutionTimeoutError,
)
from ai_enterprise.domain.execution.policies import RuntimeLimits


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
            self._client = docker.DockerClient(base_url=docker_base_url)
        else:
            self._client = docker.from_env()

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
        input_dir.mkdir(parents=True, mode=0o755)
        output_dir.mkdir(parents=True, mode=0o700)
        os.chmod(output_dir, 0o777)

        input_path = input_dir / "execution.json"
        input_path.write_text(
            json.dumps(runtime_input, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        if edits is not None:
            edits_path = input_dir / "edits.json"
            edits_path.write_text(
                json.dumps(edits, indent=2, sort_keys=True),
                encoding="utf-8",
            )

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

            result_data = json.loads(
                result_path.read_text(encoding="utf-8")
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
            return log_path.read_text(encoding="utf-8", errors="replace")

        return container.logs(
            stdout=True,
            stderr=True,
            timestamps=True,
        ).decode("utf-8", errors="replace")

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
