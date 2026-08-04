import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from ai_enterprise.infrastructure.execution_broker.engine import (
    BrokerEngineError,
    BrokerEngineResult,
)
from ai_enterprise.infrastructure.execution_broker.evidence import (
    StoredTerminalEvidence,
    TerminalEvidenceStoreError,
)
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest
from ai_enterprise.infrastructure.execution_broker.runner import (
    BrokerRunPersistenceError,
    DurableBrokerRunner,
)
from ai_enterprise.infrastructure.execution_broker.store import SnapshotHandle


def request(runtime_input: dict[str, object] | None = None) -> BrokerRunRequest:
    encoded = json.dumps(
        runtime_input or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return BrokerRunRequest.model_validate(
        {
            "schema_version": 1,
            "idempotency_key": uuid.uuid4(),
            "workload_id": uuid.uuid4(),
            "kind": "execution",
            "image_policy_key": "execution-agent",
            "resource_profile": "small",
            "snapshot_ref": uuid.uuid4(),
            "input_sha256": hashlib.sha256(encoded).hexdigest(),
            "correlation_id": uuid.uuid4(),
        }
    )


def result() -> BrokerEngineResult:
    return BrokerEngineResult(
        runtime_instance_id="runtime-1",
        image_id="sha256:" + "a" * 64,
        exit_code=0,
        output_archive=b"output",
        workspace_archive=b"workspace",
        runtime_log="log",
        retained_evidence_volumes={
            "workspace": "ai-broker-workload-nonce-workspace",
            "output": "ai-broker-workload-nonce-output",
        },
    )


def evidence(request_value: BrokerRunRequest) -> StoredTerminalEvidence:
    return StoredTerminalEvidence(
        evidence_ref=uuid.uuid4(),
        workload_id=request_value.workload_id,
        correlation_id=request_value.correlation_id,
        kind=request_value.kind,
        runtime_instance_id="runtime-1",
        image_id="sha256:" + "a" * 64,
        exit_code=0,
        retained_volumes={
            "workspace": "ai-broker-workload-nonce-workspace",
            "output": "ai-broker-workload-nonce-output",
        },
        output_archive_sha256="0" * 64,
        workspace_archive_sha256="1" * 64,
        runtime_log_sha256="2" * 64,
        manifest_sha256="3" * 64,
        state="retained",
        captured_at=datetime.now(UTC),
    )


@dataclass
class SnapshotResolver:
    handle: SnapshotHandle
    calls: list[str]

    def resolve(self, snapshot_ref: uuid.UUID, *, owner_worker_id: str) -> SnapshotHandle:
        self.calls.append(f"resolve:{snapshot_ref}:{owner_worker_id}")
        return self.handle


@dataclass
class Engine:
    value: BrokerEngineResult
    calls: list[str]
    error: BrokerEngineError | None = None

    def run(
        self,
        request_value: BrokerRunRequest,
        *,
        snapshot: SnapshotHandle,
        runtime_input: dict[str, Any],
    ) -> BrokerEngineResult:
        self.calls.append(f"engine:{request_value.workload_id}:{snapshot.snapshot_ref}")
        if self.error is not None:
            raise self.error
        return self.value


@dataclass
class EvidenceRecorder:
    value: StoredTerminalEvidence
    calls: list[str]
    error: Exception | None = None

    def record(
        self, request_value: BrokerRunRequest, result_value: BrokerEngineResult
    ) -> StoredTerminalEvidence:
        self.calls.append(
            f"evidence:{request_value.workload_id}:{result_value.runtime_instance_id}"
        )
        if self.error is not None:
            raise self.error
        return self.value


def test_durable_runner_records_evidence_before_acknowledging_run(tmp_path: Path) -> None:
    calls: list[str] = []
    request_value = request({"ok": True})
    snapshot = SnapshotHandle(request_value.snapshot_ref, "d" * 64, tmp_path)
    result_value = result()
    evidence_value = evidence(request_value)

    receipt = DurableBrokerRunner(
        snapshot_store=SnapshotResolver(snapshot, calls),
        engine=Engine(result_value, calls),
        evidence_store=EvidenceRecorder(evidence_value, calls),
    ).run(request_value, owner_worker_id="worker-1", runtime_input={"ok": True})

    assert receipt.result == result_value
    assert receipt.evidence == evidence_value
    assert calls == [
        f"resolve:{request_value.snapshot_ref}:worker-1",
        f"engine:{request_value.workload_id}:{request_value.snapshot_ref}",
        f"evidence:{request_value.workload_id}:runtime-1",
    ]


def test_durable_runner_fails_closed_when_terminal_evidence_is_not_durable(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    request_value = request()
    snapshot = SnapshotHandle(request_value.snapshot_ref, "d" * 64, tmp_path)

    with pytest.raises(BrokerRunPersistenceError, match="evidence was not durable"):
        DurableBrokerRunner(
            snapshot_store=SnapshotResolver(snapshot, calls),
            engine=Engine(result(), calls),
            evidence_store=EvidenceRecorder(
                evidence(request_value),
                calls,
                error=TerminalEvidenceStoreError("database unavailable"),
            ),
        ).run(request_value, owner_worker_id="worker-1", runtime_input={})

    assert calls == [
        f"resolve:{request_value.snapshot_ref}:worker-1",
        f"engine:{request_value.workload_id}:{request_value.snapshot_ref}",
        f"evidence:{request_value.workload_id}:runtime-1",
    ]


def test_durable_runner_does_not_record_evidence_when_engine_fails(tmp_path: Path) -> None:
    calls: list[str] = []
    request_value = request()
    snapshot = SnapshotHandle(request_value.snapshot_ref, "d" * 64, tmp_path)

    with pytest.raises(BrokerEngineError) as raised:
        DurableBrokerRunner(
            snapshot_store=SnapshotResolver(snapshot, calls),
            engine=Engine(
                result(),
                calls,
                error=BrokerEngineError("engine_timeout", "broker workload timed out"),
            ),
            evidence_store=EvidenceRecorder(evidence(request_value), calls),
        ).run(request_value, owner_worker_id="worker-1", runtime_input={})

    assert raised.value.code == "engine_timeout"
    assert calls == [
        f"resolve:{request_value.snapshot_ref}:worker-1",
        f"engine:{request_value.workload_id}:{request_value.snapshot_ref}",
    ]
