import hashlib
import json
import uuid
from pathlib import Path

import pytest

from ai_enterprise.infrastructure.execution_broker.engine import BrokerEngineResult
from ai_enterprise.infrastructure.execution_broker.evidence import (
    TerminalEvidenceStore,
    TerminalEvidenceStoreError,
)
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest


def request() -> BrokerRunRequest:
    runtime_input = {"task": "prove evidence"}
    encoded = json.dumps(
        runtime_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
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


def result(
    retained_evidence_volumes: dict[str, str] | None = None,
) -> BrokerEngineResult:
    return BrokerEngineResult(
        runtime_instance_id="runtime-opaque-1",
        image_id="sha256:" + "a" * 64,
        exit_code=7,
        output_archive=b"output tar bytes",
        workspace_archive=b"workspace tar bytes",
        runtime_log="bounded runtime log",
        retained_evidence_volumes=retained_evidence_volumes
        or {
            "workspace": "ai-broker-workload-nonce-workspace",
            "output": "ai-broker-workload-nonce-output",
        },
    )


def test_terminal_evidence_survives_restart_and_lists_pending_handoff(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    request_value = request()

    stored = store.record(request_value, result())
    restarted = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    pending = restarted.pending_handoff()
    assert len(pending) == 1
    assert pending[0] == stored
    assert pending[0].state == "retained"
    assert pending[0].workload_id == request_value.workload_id
    assert pending[0].retained_volumes == {
        "workspace": "ai-broker-workload-nonce-workspace",
        "output": "ai-broker-workload-nonce-output",
    }
    assert pending[0].output_archive_sha256 == hashlib.sha256(b"output tar bytes").hexdigest()
    assert restarted.reconciliation.retained_records == 1
    assert restarted.reconciliation.started_records == 0
    assert restarted.reconciliation.completed_records == 0


def test_terminal_evidence_handoff_started_state_survives_restart(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())

    started = store.mark_handoff_started(stored.evidence_ref)
    restarted = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    assert started.state == "handoff_started"
    assert restarted.pending_handoff()[0].state == "handoff_started"
    assert restarted.reconciliation.retained_records == 0
    assert restarted.reconciliation.started_records == 1
    assert restarted.reconciliation.completed_records == 0
    assert (
        restarted.mark_handoff_started(stored.evidence_ref).state
        == "handoff_started"
    )


def test_terminal_evidence_handoff_completion_is_durable(tmp_path: Path) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())

    completed = store.mark_handoff_completed(stored.evidence_ref)
    restarted = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    assert completed.state == "handoff_completed"
    assert restarted.pending_handoff() == ()
    assert restarted.get(stored.evidence_ref).state == "handoff_completed"
    assert restarted.reconciliation.retained_records == 0
    assert restarted.reconciliation.started_records == 0
    assert restarted.reconciliation.completed_records == 1


def test_terminal_evidence_rejects_incomplete_retained_volume_manifest(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    with pytest.raises(TerminalEvidenceStoreError, match="volumes are incomplete"):
        store.record(request(), result({"workspace": "only-workspace"}))


def test_terminal_evidence_rejects_unsafe_volume_names(tmp_path: Path) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    with pytest.raises(TerminalEvidenceStoreError, match="volume name is invalid"):
        store.record(
            request(),
            result(
                {
                    "workspace": "ai-broker-workload-nonce-workspace",
                    "output": "../not-a-volume",
                }
            ),
        )
