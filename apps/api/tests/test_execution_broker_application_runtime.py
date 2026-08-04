import io
import json
import tarfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_enterprise.domain.execution.policies import RuntimeLimits
from ai_enterprise.infrastructure.execution_broker.application_runtime import (
    BrokerExecutionRuntime,
    BrokerReviewRuntime,
)
from ai_enterprise.infrastructure.execution_broker.engine import (
    BrokerEngineResult,
    BrokerPolicyError,
    _extra_input_files,
)
from ai_enterprise.infrastructure.execution_broker.evidence import StoredTerminalEvidence
from ai_enterprise.infrastructure.execution_broker.runner import DurableBrokerRunReceipt
from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore


def limits() -> RuntimeLimits:
    return RuntimeLimits(
        timeout_seconds=300,
        implementation_timeout_seconds=60,
        test_timeout_seconds=60,
        nano_cpus=500_000_000,
        memory_bytes=512 << 20,
        memory_swap_bytes=512 << 20,
        pids_limit=128,
    )


def execution_runtime_input() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "execution_id": str(uuid.uuid4()),
        "implementation": {
            "argv": [
                "python",
                "/opt/runtime/apply_edits.py",
                "--input",
                "/runtime-input/edits.json",
            ],
            "timeout_seconds": 60,
        },
        "tests": [],
    }


def execution_result() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "implementation": {
            "name": "implementation",
            "argv": [
                "python",
                "/opt/runtime/apply_edits.py",
                "--input",
                "/runtime-input/edits.json",
            ],
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
            "timed_out": False,
        },
        "tests": [],
        "success": True,
    }


def review_runtime_input() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "approved_tests": [
            {"argv": ["pytest", "-q"], "timeout_seconds": 60, "required": True}
        ],
        "review_checks": [],
    }


def review_result() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "approved_tests": [
            {
                "name": "approved-test-0",
                "argv": ["pytest", "-q"],
                "exit_code": 0,
                "duration_ms": 1,
                "stdout": "",
                "stderr": "",
                "timed_out": False,
                "required": True,
            }
        ],
        "review_checks": [],
        "success": True,
    }


@dataclass
class RecordingRunner:
    result_payload: dict[str, Any]
    log_name: str
    calls: list[tuple[Any, str, dict[str, Any]]]

    def run(
        self,
        request: Any,
        *,
        owner_worker_id: str,
        runtime_input: dict[str, Any],
    ) -> DurableBrokerRunReceipt:
        self.calls.append((request, owner_worker_id, runtime_input))
        return DurableBrokerRunReceipt(
            result=BrokerEngineResult(
                runtime_instance_id="broker-container",
                image_id="sha256:" + "a" * 64,
                exit_code=0,
                output_archive=output_archive(
                    "result.json",
                    json.dumps(self.result_payload).encode(),
                    self.log_name,
                    b"log\n",
                ),
                workspace_archive=b"",
                runtime_log="fallback-log",
                retained_evidence_volumes={
                    "workspace": "workspace-volume",
                    "output": "output-volume",
                },
            ),
            evidence=StoredTerminalEvidence(
                evidence_ref=uuid.uuid4(),
                workload_id=request.workload_id,
                correlation_id=request.correlation_id,
                kind=request.kind,
                runtime_instance_id="broker-container",
                image_id="sha256:" + "a" * 64,
                exit_code=0,
                retained_volumes={
                    "workspace": "workspace-volume",
                    "output": "output-volume",
                },
                output_archive_sha256="0" * 64,
                workspace_archive_sha256="1" * 64,
                runtime_log_sha256="2" * 64,
                manifest_sha256="3" * 64,
                state="retained",
                captured_at=datetime.now(UTC),
            ),
        )


def test_broker_execution_runtime_registers_snapshot_and_maps_result(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "app.py").write_text("print('ok')\n", encoding="utf-8")
    store = SnapshotStore(tmp_path / "broker-store")
    calls: list[tuple[Any, str, dict[str, Any]]] = []
    runner = RecordingRunner(execution_result(), "runtime.log", calls)
    runtime_input = execution_runtime_input()

    result = BrokerExecutionRuntime(
        runner,  # type: ignore[arg-type]
        snapshot_store=store,
        owner_worker_id="worker:general",
    ).run(
        execution_id=str(uuid.uuid4()),
        image="ignored",
        snapshot_path=snapshot,
        runtime_input=runtime_input,
        runtime_temp_root=tmp_path / "tmp",
        limits=limits(),
        edits=[{"path": "app.py", "mode": "replace", "content": "print('changed')\n"}],
    )

    request, owner_worker_id, broker_input = calls[0]
    assert owner_worker_id == "worker:general"
    assert request.kind == "execution"
    assert broker_input["_broker_extra_input_files"]["edits.json"][0]["path"] == "app.py"
    assert store.resolve(request.snapshot_ref, owner_worker_id="worker:general").root.joinpath(
        "app.py"
    ).read_text(encoding="utf-8") == "print('ok')\n"
    assert result.container_id == "broker-container"
    assert result.success is True
    assert result.runtime_log == "log\n"


def test_broker_review_runtime_registers_snapshot_and_maps_result(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "app.py").write_text("print('ok')\n", encoding="utf-8")
    store = SnapshotStore(tmp_path / "broker-store")
    calls: list[tuple[Any, str, dict[str, Any]]] = []
    runner = RecordingRunner(review_result(), "review.log", calls)

    result = BrokerReviewRuntime(
        runner,  # type: ignore[arg-type]
        snapshot_store=store,
        owner_worker_id="worker:general",
    ).run(
        review_id=str(uuid.uuid4()),
        image="ignored",
        snapshot_path=snapshot,
        review_input=review_runtime_input(),
        review_temp_root=tmp_path / "tmp",
        limits=limits(),
    )

    request, owner_worker_id, _broker_input = calls[0]
    assert owner_worker_id == "worker:general"
    assert request.kind == "review"
    assert store.resolve(request.snapshot_ref, owner_worker_id="worker:general").root.joinpath(
        "app.py"
    ).read_text(encoding="utf-8") == "print('ok')\n"
    assert result.container_id == "broker-container"
    assert result.success is True
    assert result.review_log == "log\n"
    assert result.approved_tests[0].check_type == "approved_test"


def test_broker_extra_input_files_reject_ambiguous_names() -> None:
    for name in (".", "..", "execution.json", "nested/edits.json", "bad\x00name"):
        try:
            _extra_input_files({"_broker_extra_input_files": {name: []}})
        except BrokerPolicyError:
            continue
        raise AssertionError(f"extra input name {name!r} should have been rejected")


def output_archive(
    result_name: str,
    result_content: bytes,
    log_name: str,
    log_content: bytes,
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        for name, content in ((result_name, result_content), (log_name, log_content)):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return output.getvalue()
