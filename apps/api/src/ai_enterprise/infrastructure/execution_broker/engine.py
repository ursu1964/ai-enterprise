from __future__ import annotations

import io
import json
import tarfile
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from docker.client import DockerClient
from docker.errors import APIError, ImageNotFound

from ai_enterprise.infrastructure.execution_broker.policy import (
    BrokerPolicy,
    BrokerPolicyError,
    BrokerRunRequest,
)

MAXIMUM_ENGINE_ARCHIVE_BYTES = 128 * 1024 * 1024
MAXIMUM_ENGINE_LOG_BYTES = 4 * 1024 * 1024


class BrokerEngineError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class BrokerEngineResult:
    runtime_instance_id: str
    image_id: str
    exit_code: int
    output_archive: bytes
    workspace_archive: bytes
    runtime_log: str


class DockerEngineAdapter:
    def __init__(
        self,
        client: DockerClient,
        policy: BrokerPolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._policy = policy
        self._clock = clock
        self._sleeper = sleeper

    def ready(self) -> bool:
        try:
            self._client.ping()
            requests = (
                _readiness_request(key="execution-agent", kind="execution"),
                _readiness_request(key="review-agent", kind="review"),
            )
            for request in requests:
                resolved = self._policy.resolve(request)
                image = self._client.images.get(resolved.image_id)
                if image.id != resolved.image_id:
                    return False
        except (APIError, ImageNotFound, OSError):
            return False
        return True

    def run(
        self,
        request: BrokerRunRequest,
        *,
        snapshot_root: Path,
        runtime_input: dict[str, Any],
    ) -> BrokerEngineResult:
        resolved = self._policy.resolve(request)
        image = self._verified_image(resolved.image_id)
        run_label = str(request.workload_id)
        volumes: list[Any] = []
        container: Any | None = None
        cleanup_failed = False
        try:
            for purpose in ("workspace", "input", "output"):
                volumes.append(
                    self._client.volumes.create(
                        name=f"ai-broker-{run_label}-{purpose}",
                        labels={
                            "ai.enterprise.broker-managed": "true",
                            "ai.enterprise.workload-id": run_label,
                            "ai.enterprise.purpose": purpose,
                        },
                    )
                )
            workspace_volume, input_volume, output_volume = volumes
            resources = resolved.resources
            container = self._client.containers.create(
                image=image.id,
                name=f"ai-broker-{request.kind}-{run_label}",
                detach=True,
                auto_remove=False,
                network_disabled=True,
                read_only=True,
                user=f"{resolved.runtime_uid}:{resolved.runtime_gid}",
                working_dir="/workspace",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                privileged=False,
                nano_cpus=resources.nano_cpus,
                mem_limit=resources.memory_bytes,
                memswap_limit=resources.memory_swap_bytes,
                pids_limit=resources.pids_limit,
                init=True,
                stdin_open=False,
                tty=False,
                environment={
                    "EXECUTION_ID" if request.kind == "execution" else "REVIEW_ID": run_label
                },
                volumes={
                    workspace_volume.name: {"bind": "/workspace", "mode": "rw"},
                    input_volume.name: {"bind": "/runtime-input", "mode": "ro"},
                    output_volume.name: {"bind": "/runtime-output", "mode": "rw"},
                },
                tmpfs={
                    "/tmp": (
                        f"rw,noexec,nosuid,nodev,size={resources.tmpfs_size_bytes},mode=1777"
                    ),
                    "/home/runtime": "rw,noexec,nosuid,nodev,size=16777216,mode=0700",
                },
                labels={
                    "ai.enterprise.broker-managed": "true",
                    "ai.enterprise.workload-id": run_label,
                    "ai.enterprise.kind": request.kind,
                },
            )
            container.reload()
            if container.attrs.get("Image") != image.id:
                raise BrokerEngineError(
                    "image_identity_mismatch", "created container image identity changed"
                )
            container.put_archive("/workspace", _archive_directory(snapshot_root))
            input_name = "execution.json" if request.kind == "execution" else "review.json"
            container.put_archive(
                "/runtime-input",
                _archive_bytes(input_name, json.dumps(runtime_input, sort_keys=True).encode()),
            )
            container.start()
            wait_result = self._wait(container, resources.timeout_seconds)
            output_archive = _read_archive(container.get_archive("/runtime-output")[0])
            workspace_archive = _read_archive(container.get_archive("/workspace")[0])
            runtime_log = _read_log(container.logs(stdout=True, stderr=True, timestamps=True))
            return BrokerEngineResult(
                runtime_instance_id=str(container.id),
                image_id=image.id,
                exit_code=int(wait_result["StatusCode"]),
                output_archive=output_archive,
                workspace_archive=workspace_archive,
                runtime_log=runtime_log,
            )
        except ImageNotFound as exc:
            raise BrokerEngineError(
                "approved_image_missing", "approved image is unavailable"
            ) from exc
        except APIError as exc:
            raise BrokerEngineError("engine_api_failure", "engine operation failed") from exc
        finally:
            if container is not None:
                try:
                    container.remove(force=True, v=True)
                except APIError:
                    cleanup_failed = True
            for volume in reversed(volumes):
                try:
                    volume.remove(force=True)
                except APIError:
                    cleanup_failed = True
            if cleanup_failed:
                raise BrokerEngineError(
                    "engine_cleanup_failed", "broker engine cleanup could not be proven"
                )

    def _verified_image(self, image_id: str) -> Any:
        image = self._client.images.get(image_id)
        if image.id != image_id:
            raise BrokerEngineError("image_identity_mismatch", "approved image identity changed")
        return image

    def _wait(self, container: Any, timeout_seconds: int) -> dict[str, Any]:
        started = self._clock()
        while True:
            container.reload()
            if container.status in {"exited", "dead"}:
                return dict(container.wait(timeout=10))
            if self._clock() - started >= timeout_seconds:
                container.kill(signal="SIGKILL")
                raise BrokerEngineError("engine_timeout", "broker workload exceeded its deadline")
            self._sleeper(0.5)


def _readiness_request(
    *,
    key: Literal["execution-agent", "review-agent"],
    kind: Literal["execution", "review"],
) -> BrokerRunRequest:
    return BrokerRunRequest.model_validate(
        {
            "schema_version": 1,
            "idempotency_key": uuid.uuid4(),
            "workload_id": uuid.uuid4(),
            "kind": kind,
            "image_policy_key": key,
            "resource_profile": "small",
            "snapshot_ref": uuid.uuid4(),
            "input_sha256": "0" * 64,
            "correlation_id": uuid.uuid4(),
        }
    )


def _archive_directory(root: Path) -> bytes:
    root = root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise BrokerPolicyError("snapshot root must be a private directory")
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise BrokerPolicyError("snapshot contains a forbidden entry")
            relative = path.relative_to(root).as_posix()
            info = tarfile.TarInfo(relative)
            if path.is_dir():
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                archive.addfile(info)
            else:
                info.size = path.stat().st_size
                info.mode = 0o700 if path.stat().st_mode & 0o111 else 0o600
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
            if output.tell() > MAXIMUM_ENGINE_ARCHIVE_BYTES:
                raise BrokerPolicyError("snapshot transfer exceeds broker limit")
    return output.getvalue()


def _archive_bytes(name: str, content: bytes) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        info.mode = 0o400
        archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _read_archive(chunks: Iterable[bytes]) -> bytes:
    output = bytearray()
    for chunk in chunks:
        output.extend(chunk)
        if len(output) > MAXIMUM_ENGINE_ARCHIVE_BYTES:
            raise BrokerEngineError("engine_archive_too_large", "engine archive exceeds limit")
    return bytes(output)


def _read_log(value: bytes | Iterable[bytes]) -> str:
    chunks = (value,) if isinstance(value, bytes) else value
    output = bytearray()
    for chunk in chunks:
        output.extend(chunk)
        if len(output) > MAXIMUM_ENGINE_LOG_BYTES:
            raise BrokerEngineError("engine_log_too_large", "engine log exceeds limit")
    return bytes(output).decode("utf-8", errors="replace")
