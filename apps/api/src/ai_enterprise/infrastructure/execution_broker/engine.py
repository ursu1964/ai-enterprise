from __future__ import annotations

import hashlib
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
from requests.exceptions import Timeout as RequestTimeout

from ai_enterprise.infrastructure.execution_broker.policy import (
    BrokerPolicy,
    BrokerPolicyError,
    BrokerRunRequest,
)
from ai_enterprise.infrastructure.execution_broker.store import SnapshotHandle

MAXIMUM_ENGINE_ARCHIVE_BYTES = 128 * 1024 * 1024
MAXIMUM_ENGINE_LOG_BYTES = 4 * 1024 * 1024
MAXIMUM_EXTRA_INPUT_BYTES = 8 * 1024 * 1024
EXTRA_INPUT_FILES_KEY = "_broker_extra_input_files"


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
    retained_evidence_volumes: dict[str, str]


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
        snapshot: SnapshotHandle,
        runtime_input: dict[str, Any],
    ) -> BrokerEngineResult:
        runtime_input_encoded = _runtime_input_bytes(runtime_input)
        if snapshot.snapshot_ref != request.snapshot_ref:
            raise BrokerEngineError(
                "snapshot_identity_mismatch", "resolved snapshot does not match request"
            )
        if hashlib.sha256(runtime_input_encoded).hexdigest() != request.input_sha256:
            raise BrokerEngineError(
                "input_identity_mismatch", "runtime input does not match request"
            )
        resolved = self._policy.resolve(request)
        image = self._verified_image(resolved.image_id)
        run_label = str(request.workload_id)
        run_nonce = uuid.uuid4().hex
        volumes: list[Any] = []
        materializer: Any | None = None
        container: Any | None = None
        cleanup_failed = False
        terminal_evidence_captured = False
        retained_evidence_volumes: dict[str, str] = {}
        try:
            for purpose in ("workspace", "input", "output"):
                volumes.append(
                    self._client.volumes.create(
                        name=f"ai-broker-{run_label}-{run_nonce}-{purpose}",
                        labels={
                            "ai.enterprise.broker-managed": "true",
                            "ai.enterprise.workload-id": run_label,
                            "ai.enterprise.run-nonce": run_nonce,
                            "ai.enterprise.purpose": purpose,
                            "ai.enterprise.retention": (
                                "terminal-evidence-candidate"
                                if purpose in {"workspace", "output"}
                                else "transient"
                            ),
                        },
                    )
                )
            workspace_volume, input_volume, output_volume = volumes
            resources = resolved.resources
            input_name = "execution.json" if request.kind == "execution" else "review.json"
            materializer = self._client.containers.create(
                image=image.id,
                name=f"ai-broker-materializer-{run_nonce}",
                detach=True,
                auto_remove=False,
                network_disabled=True,
                read_only=True,
                user="0:0",
                entrypoint=["/bin/sh", "-c"],
                command=[
                    _materializer_command(
                        resolved.runtime_uid, resolved.runtime_gid, input_name
                    )
                ],
                cap_drop=["ALL"],
                cap_add=["CHOWN"],
                security_opt=["no-new-privileges:true"],
                privileged=False,
                pids_limit=32,
                mem_limit=128 << 20,
                memswap_limit=128 << 20,
                nano_cpus=250_000_000,
                volumes={
                    workspace_volume.name: {"bind": "/seed/workspace", "mode": "rw"},
                    input_volume.name: {"bind": "/seed/input", "mode": "rw"},
                    output_volume.name: {"bind": "/seed/output", "mode": "rw"},
                },
                tmpfs={"/tmp": "rw,noexec,nosuid,nodev,size=16777216,mode=1777"},
                labels={
                    "ai.enterprise.broker-managed": "true",
                    "ai.enterprise.workload-id": run_label,
                    "ai.enterprise.run-nonce": run_nonce,
                    "ai.enterprise.purpose": "materializer",
                },
            )
            materializer.put_archive("/seed/workspace", _archive_directory(snapshot.root))
            materializer.put_archive(
                "/seed/input",
                _archive_bytes(input_name, runtime_input_encoded),
            )
            for name, content in _extra_input_files(runtime_input).items():
                materializer.put_archive("/seed/input", _archive_bytes(name, content))
            materializer.start()
            try:
                materializer_result = materializer.wait(timeout=60)
            except RequestTimeout as exc:
                materializer.kill(signal="SIGKILL")
                raise BrokerEngineError(
                    "materialization_timeout", "runtime volume preparation timed out"
                ) from exc
            if int(materializer_result["StatusCode"]) != 0:
                raise BrokerEngineError(
                    "materialization_failed", "runtime volume preparation failed"
                )
            materializer.remove(force=True, v=False)
            materializer = None
            container = self._client.containers.create(
                image=image.id,
                name=f"ai-broker-{request.kind}-{run_label}-{run_nonce}",
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
                    "/home/runtime": (
                        "rw,noexec,nosuid,nodev,size=16777216,mode=0700,"
                        f"uid={resolved.runtime_uid},gid={resolved.runtime_gid}"
                    ),
                },
                labels={
                    "ai.enterprise.broker-managed": "true",
                    "ai.enterprise.workload-id": run_label,
                    "ai.enterprise.run-nonce": run_nonce,
                    "ai.enterprise.kind": request.kind,
                },
            )
            container.reload()
            if container.attrs.get("Image") != image.id:
                raise BrokerEngineError(
                    "image_identity_mismatch", "created container image identity changed"
                )
            container.start()
            wait_result = self._wait(container, resources.timeout_seconds)
            output_archive = _read_archive(container.get_archive("/runtime-output")[0])
            workspace_archive = _read_archive(container.get_archive("/workspace")[0])
            runtime_log = _read_log(container.logs(stdout=True, stderr=True, timestamps=True))
            terminal_evidence_captured = True
            retained_evidence_volumes = {
                "workspace": workspace_volume.name,
                "output": output_volume.name,
            }
            return BrokerEngineResult(
                runtime_instance_id=str(container.id),
                image_id=image.id,
                exit_code=int(wait_result["StatusCode"]),
                output_archive=output_archive,
                workspace_archive=workspace_archive,
                runtime_log=runtime_log,
                retained_evidence_volumes=retained_evidence_volumes,
            )
        except ImageNotFound as exc:
            raise BrokerEngineError(
                "approved_image_missing", "approved image is unavailable"
            ) from exc
        except APIError as exc:
            raise BrokerEngineError("engine_api_failure", "engine operation failed") from exc
        finally:
            if materializer is not None:
                try:
                    materializer.remove(force=True, v=False)
                except APIError:
                    cleanup_failed = True
            if container is not None:
                try:
                    container.remove(force=True, v=not terminal_evidence_captured)
                except APIError:
                    cleanup_failed = True
            for volume in reversed(volumes):
                if terminal_evidence_captured and volume.name in retained_evidence_volumes.values():
                    try:
                        self._client.volumes.get(volume.name)
                    except APIError:
                        cleanup_failed = True
                    continue
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


def _materializer_command(runtime_uid: int, runtime_gid: int, input_name: str) -> str:
    identity = f"{runtime_uid}:{runtime_gid}"
    return (
        "find /seed/workspace -type d -exec chmod 0700 {} + && "
        "find /seed/workspace -type f -perm /0111 -exec chmod 0700 {} + && "
        "find /seed/workspace -type f ! -perm /0111 -exec chmod 0600 {} + && "
        "find /seed/input -type d -exec chmod 0500 {} + && "
        "find /seed/input -type f -exec chmod 0400 {} + && "
        "chmod 0700 /seed/output && "
        f"find /seed/workspace /seed/input /seed/output -type f -exec chown {identity} {{}} + && "
        f'test "$(stat -c %u:%g /seed/input/{input_name})" = "{identity}" && '
        f'test "$(stat -c %a /seed/input/{input_name})" = "400" && '
        f"find /seed/workspace /seed/input /seed/output -depth -type d "
        f"-exec chown {identity} {{}} + && "
        'test "$(stat -c %u:%g /seed/workspace /seed/input /seed/output)" = '
        f'"{identity}\n{identity}\n{identity}" && '
        'test "$(stat -c %a /seed/workspace /seed/input /seed/output)" = '
        '"700\n500\n700"'
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


def _runtime_input_bytes(runtime_input: dict[str, Any]) -> bytes:
    return json.dumps(
        runtime_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _extra_input_files(runtime_input: dict[str, Any]) -> dict[str, bytes]:
    raw_files = runtime_input.get(EXTRA_INPUT_FILES_KEY, {})
    if not isinstance(raw_files, dict):
        raise BrokerPolicyError("broker extra input files must be an object")
    encoded_files: dict[str, bytes] = {}
    total_bytes = 0
    for name, value in raw_files.items():
        if (
            not isinstance(name, str)
            or not name
            or "/" in name
            or "\\" in name
            or name in {".", "..", "execution.json", "review.json"}
            or any(ord(character) < 32 or ord(character) == 127 for character in name)
        ):
            raise BrokerPolicyError("broker extra input file name is invalid")
        content = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        total_bytes += len(content)
        if total_bytes > MAXIMUM_EXTRA_INPUT_BYTES:
            raise BrokerPolicyError("broker extra input files exceed size limit")
        encoded_files[name] = content
    return encoded_files


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
