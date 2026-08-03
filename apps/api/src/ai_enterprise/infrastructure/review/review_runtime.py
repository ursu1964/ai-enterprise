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

from ai_enterprise.domain.execution.policies import RuntimeLimits
from ai_enterprise.domain.review.exceptions import ReviewRuntimeError


@dataclass(frozen=True, slots=True)
class ReviewCheckResult:
    check_type: str
    name: str
    argv: tuple[str, ...]
    exit_code: int | None
    duration_ms: int
    stdout: str
    stderr: str
    timed_out: bool
    required: bool


@dataclass(frozen=True, slots=True)
class ReviewContainerResult:
    container_id: str
    container_image: str
    container_image_digest: str | None
    exit_code: int
    approved_tests: tuple[ReviewCheckResult, ...]
    review_checks: tuple[ReviewCheckResult, ...]
    success: bool
    review_log: str


class DockerReviewRuntime:
    def __init__(self, docker_base_url: str | None = None) -> None:
        self._runtime_uid = os.getuid()
        self._runtime_gid = os.getgid()
        if docker_base_url:
            self._client = DockerClient(base_url=docker_base_url)
        else:
            self._client = from_env()

        self._client.ping()

    def run(
        self,
        *,
        review_id: str,
        image: str,
        snapshot_path: Path,
        review_input: dict[str, Any],
        review_temp_root: Path,
        limits: RuntimeLimits,
    ) -> ReviewContainerResult:
        invocation_root = review_temp_root / review_id
        input_dir = invocation_root / "input"
        output_dir = invocation_root / "output"

        shutil.rmtree(invocation_root, ignore_errors=True)
        input_dir.mkdir(parents=True, mode=0o755)
        output_dir.mkdir(parents=True, mode=0o700)
        os.chmod(output_dir, 0o777)

        input_path = input_dir / "review.json"
        input_path.write_text(
            json.dumps(review_input, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        container = None

        try:
            image_object = self._client.images.get(image)
            image_digest = self._extract_digest(image_object.attrs)

            container = self._client.containers.run(
                image=image,
                name=f"ai-review-{review_id}",
                detach=True,
                auto_remove=False,
                network_disabled=True,
                read_only=True,
                user=f"{self._runtime_uid}:{self._runtime_gid}",
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
                    "REVIEW_ID": review_id,
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
                    "/tmp": (f"rw,noexec,nosuid,nodev,size={limits.tmpfs_size_bytes},mode=1777"),
                    "/home/reviewer": (
                        "rw,noexec,nosuid,nodev,size=16777216,mode=0700,"
                        f"uid={self._runtime_uid},gid={self._runtime_gid}"
                    ),
                },
                labels={
                    "ai.enterprise.review-id": review_id,
                    "ai.enterprise.managed": "true",
                },
            )

            wait_result = self._wait_with_timeout(
                container=container,
                timeout_seconds=limits.timeout_seconds,
            )

            exit_code = int(wait_result["StatusCode"])

            review_log = self._read_review_log(
                output_dir=output_dir,
                container=container,
            )

            result_path = output_dir / "result.json"

            if not result_path.is_file():
                raise ReviewRuntimeError("Review container produced no result.json")

            result_data = json.loads(result_path.read_text(encoding="utf-8"))

            approved_tests = tuple(
                ReviewCheckResult(
                    check_type="approved_test",
                    name=item["name"],
                    argv=tuple(item["argv"]),
                    exit_code=item["exit_code"],
                    duration_ms=item["duration_ms"],
                    stdout=item["stdout"],
                    stderr=item["stderr"],
                    timed_out=item["timed_out"],
                    required=item.get("required", True),
                )
                for item in result_data.get("approved_tests", [])
            )

            review_checks = tuple(
                ReviewCheckResult(
                    check_type="review_check",
                    name=item["name"],
                    argv=tuple(item["argv"]),
                    exit_code=item["exit_code"],
                    duration_ms=item["duration_ms"],
                    stdout=item["stdout"],
                    stderr=item["stderr"],
                    timed_out=item["timed_out"],
                    required=item.get("required", True),
                )
                for item in result_data.get("review_checks", [])
            )

            return ReviewContainerResult(
                container_id=container.id,
                container_image=image,
                container_image_digest=image_digest,
                exit_code=exit_code,
                approved_tests=approved_tests,
                review_checks=review_checks,
                success=bool(result_data["success"]),
                review_log=review_log,
            )
        except ImageNotFound as exc:
            raise ReviewRuntimeError(f"Review image not found: {image}") from exc
        except APIError as exc:
            raise ReviewRuntimeError(f"Docker API error: {exc}") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError:
                    pass

    def _read_review_log(
        self,
        *,
        output_dir: Path,
        container: Any,
    ) -> str:
        log_path = output_dir / "review.log"

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
                    raise ReviewRuntimeError(f"Review exceeded {timeout_seconds} seconds")

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
