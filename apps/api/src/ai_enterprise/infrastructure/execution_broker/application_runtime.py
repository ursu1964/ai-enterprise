from __future__ import annotations

import hashlib
import io
import json
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

from docker import from_env  # type: ignore[attr-defined]

from ai_enterprise.config import Settings
from ai_enterprise.domain.execution.exceptions import ContainerExecutionError
from ai_enterprise.domain.execution.policies import RuntimeLimits
from ai_enterprise.domain.review.exceptions import ReviewRuntimeError
from ai_enterprise.infrastructure.execution.docker_runtime import (
    ContainerRunResult,
    ContainerTestResult,
    DockerExecutionRuntime,
)
from ai_enterprise.infrastructure.execution_broker.engine import (
    EXTRA_INPUT_FILES_KEY,
    DockerEngineAdapter,
)
from ai_enterprise.infrastructure.execution_broker.evidence import TerminalEvidenceStore
from ai_enterprise.infrastructure.execution_broker.policy import BrokerPolicy, BrokerRunRequest
from ai_enterprise.infrastructure.execution_broker.runner import DurableBrokerRunner
from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore
from ai_enterprise.infrastructure.review.review_runtime import (
    DockerReviewRuntime,
    ReviewCheckResult,
    ReviewContainerResult,
)


class BrokerExecutionRuntime:
    def __init__(
        self,
        runner: DurableBrokerRunner,
        *,
        snapshot_store: SnapshotStore,
        owner_worker_id: str,
    ) -> None:
        self._runner = runner
        self._snapshot_store = snapshot_store
        self._owner_worker_id = owner_worker_id

    @classmethod
    def from_settings(cls, settings: Settings, *, owner_worker_id: str) -> BrokerExecutionRuntime:
        if settings.execution_image_id is None or settings.review_image_id is None:
            raise ContainerExecutionError("Restricted broker image IDs are not configured")
        policy = BrokerPolicy(
            execution_image_id=settings.execution_image_id,
            review_image_id=settings.review_image_id,
        )
        snapshot_store = SnapshotStore(settings.execution_broker_snapshots_root)
        runner = DurableBrokerRunner(
            snapshot_store=snapshot_store,
            engine=DockerEngineAdapter(from_env(), policy),
            evidence_store=TerminalEvidenceStore(settings.execution_broker_evidence_root),
        )
        return cls(runner, snapshot_store=snapshot_store, owner_worker_id=owner_worker_id)

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
        del image, runtime_temp_root
        broker_input = dict(runtime_input)
        if edits is not None:
            broker_input[EXTRA_INPUT_FILES_KEY] = {"edits.json": edits}
        request = _request(
            snapshot_store=self._snapshot_store,
            owner_worker_id=self._owner_worker_id,
            workload_id=uuid.UUID(execution_id),
            kind="execution",
            snapshot_path=snapshot_path,
            runtime_input=broker_input,
            resource_profile=_resource_profile(limits),
        )
        receipt = self._runner.run(
            request,
            owner_worker_id=self._owner_worker_id,
            runtime_input=broker_input,
        )
        result_data = _execution_result(
            receipt.result.output_archive,
            runtime_input=runtime_input,
            exit_code=receipt.result.exit_code,
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
            container_id=receipt.result.runtime_instance_id,
            container_image="restricted-broker",
            container_image_digest=receipt.result.image_id,
            exit_code=receipt.result.exit_code,
            implementation=result_data["implementation"],
            tests=tests,
            success=bool(result_data["success"]),
            runtime_log=_archive_text(receipt.result.output_archive, "runtime.log")
            or receipt.result.runtime_log,
        )


class BrokerReviewRuntime:
    def __init__(
        self,
        runner: DurableBrokerRunner,
        *,
        snapshot_store: SnapshotStore,
        owner_worker_id: str,
    ) -> None:
        self._runner = runner
        self._snapshot_store = snapshot_store
        self._owner_worker_id = owner_worker_id

    @classmethod
    def from_settings(cls, settings: Settings, *, owner_worker_id: str) -> BrokerReviewRuntime:
        if settings.execution_image_id is None or settings.review_image_id is None:
            raise ReviewRuntimeError("Restricted broker image IDs are not configured")
        policy = BrokerPolicy(
            execution_image_id=settings.execution_image_id,
            review_image_id=settings.review_image_id,
        )
        snapshot_store = SnapshotStore(settings.execution_broker_snapshots_root)
        runner = DurableBrokerRunner(
            snapshot_store=snapshot_store,
            engine=DockerEngineAdapter(from_env(), policy),
            evidence_store=TerminalEvidenceStore(settings.execution_broker_evidence_root),
        )
        return cls(runner, snapshot_store=snapshot_store, owner_worker_id=owner_worker_id)

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
        del image, review_temp_root
        request = _request(
            snapshot_store=self._snapshot_store,
            owner_worker_id=self._owner_worker_id,
            workload_id=uuid.UUID(review_id),
            kind="review",
            snapshot_path=snapshot_path,
            runtime_input=review_input,
            resource_profile=_resource_profile(limits),
        )
        receipt = self._runner.run(
            request,
            owner_worker_id=self._owner_worker_id,
            runtime_input=review_input,
        )
        result_data = _review_result(receipt.result.output_archive)
        approved_tests = tuple(
            _review_check(item, "approved_test") for item in result_data.get("approved_tests", [])
        )
        review_checks = tuple(
            _review_check(item, "review_check") for item in result_data.get("review_checks", [])
        )
        return ReviewContainerResult(
            container_id=receipt.result.runtime_instance_id,
            container_image="restricted-broker",
            container_image_digest=receipt.result.image_id,
            exit_code=receipt.result.exit_code,
            approved_tests=approved_tests,
            review_checks=review_checks,
            success=bool(result_data["success"]),
            review_log=_archive_text(receipt.result.output_archive, "review.log")
            or receipt.result.runtime_log,
        )


def _request(
    *,
    snapshot_store: SnapshotStore,
    owner_worker_id: str,
    workload_id: uuid.UUID,
    kind: str,
    snapshot_path: Path,
    runtime_input: dict[str, Any],
    resource_profile: str,
) -> BrokerRunRequest:
    encoded = json.dumps(
        runtime_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    stored = snapshot_store.register(
        _snapshot_archive(snapshot_path),
        owner_worker_id=owner_worker_id,
    )
    return BrokerRunRequest.model_validate(
        {
            "schema_version": 1,
            "idempotency_key": uuid.uuid4(),
            "workload_id": workload_id,
            "kind": kind,
            "image_policy_key": f"{kind}-agent",
            "resource_profile": resource_profile,
            "snapshot_ref": stored.snapshot_ref,
            "input_sha256": hashlib.sha256(encoded).hexdigest(),
            "correlation_id": uuid.uuid4(),
        }
    )


def _snapshot_archive(root: Path) -> bytes:
    root = root.resolve()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise ContainerExecutionError("Snapshot contains a forbidden entry")
            relative = path.relative_to(root).as_posix()
            info = tarfile.TarInfo(relative)
            if path.is_dir():
                info.type = tarfile.DIRTYPE
                info.mode = 0o700
                archive.addfile(info)
            else:
                data = path.read_bytes()
                info.size = len(data)
                info.mode = 0o700 if path.stat().st_mode & 0o111 else 0o600
                archive.addfile(info, io.BytesIO(data))
    return output.getvalue()


def _execution_result(
    archive: bytes, *, runtime_input: dict[str, Any], exit_code: int
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("wb") as handle:
        handle.write(_archive_bytes(archive, "result.json"))
        handle.flush()
        return DockerExecutionRuntime._read_result(
            result_path=Path(handle.name),
            runtime_input=runtime_input,
            container_exit_code=exit_code,
        )


def _review_result(archive: bytes) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("wb") as handle:
        try:
            handle.write(_archive_bytes(archive, "result.json"))
        except ContainerExecutionError as exc:
            raise ReviewRuntimeError(str(exc)) from exc
        handle.flush()
        return DockerReviewRuntime._read_result(Path(handle.name))


def _archive_bytes(archive: bytes, suffix: str) -> bytes:
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        matches = [member for member in tar.getmembers() if member.name.endswith(suffix)]
        if len(matches) != 1:
            raise ContainerExecutionError(f"Broker output must contain exactly one {suffix}")
        handle = tar.extractfile(matches[0])
        if handle is None:
            raise ContainerExecutionError(f"Broker output {suffix} is unreadable")
        return handle.read()


def _archive_text(archive: bytes, suffix: str) -> str | None:
    try:
        return _archive_bytes(archive, suffix).decode("utf-8", errors="replace")
    except ContainerExecutionError:
        return None


def _review_check(item: dict[str, Any], check_type: str) -> ReviewCheckResult:
    return ReviewCheckResult(
        check_type=check_type,
        name=item["name"],
        argv=tuple(item["argv"]),
        exit_code=item["exit_code"],
        duration_ms=item["duration_ms"],
        stdout=item["stdout"],
        stderr=item["stderr"],
        timed_out=item["timed_out"],
        required=item.get("required", True),
    )


def _resource_profile(limits: RuntimeLimits) -> str:
    if limits.memory_bytes <= 512 << 20:
        return "small"
    if limits.memory_bytes <= 1 << 30:
        return "standard"
    return "large"
