import hashlib
import json
import uuid
from pathlib import Path

import pytest

from ai_enterprise.infrastructure.execution_broker.engine import BrokerEngineResult
from ai_enterprise.infrastructure.execution_broker.evidence import TerminalEvidenceStore
from ai_enterprise.infrastructure.execution_broker.handoff import (
    BrokerEvidenceHandoffError,
    TerminalEvidenceHandoffReplayer,
)
from ai_enterprise.infrastructure.execution_broker.policy import BrokerRunRequest


def request() -> BrokerRunRequest:
    encoded = json.dumps({}, sort_keys=True, separators=(",", ":")).encode()
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
        runtime_instance_id="runtime-opaque-1",
        image_id="sha256:" + "a" * 64,
        exit_code=0,
        output_archive=b"output",
        workspace_archive=b"workspace",
        runtime_log="log",
        retained_evidence_volumes={
            "workspace": "volume-workspace",
            "output": "volume-output",
        },
    )


class Volumes:
    def __init__(self, existing: set[str]) -> None:
        self.existing = existing
        self.removed: list[str] = []
        self.fail_on_remove: str | None = None

    def exists(self, volume_name: str) -> bool:
        return volume_name in self.existing

    def remove(self, volume_name: str) -> None:
        if volume_name == self.fail_on_remove:
            raise RuntimeError("remove failed")
        self.existing.remove(volume_name)
        self.removed.append(volume_name)


def test_handoff_replayer_removes_retained_volumes_and_marks_complete(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())
    volumes = Volumes({"volume-workspace", "volume-output"})

    replayed = TerminalEvidenceHandoffReplayer(
        evidence_store=store, volume_gateway=volumes
    ).replay_pending()
    restarted = TerminalEvidenceStore(tmp_path / "terminal-evidence")

    assert replayed[0].evidence_ref == stored.evidence_ref
    assert replayed[0].removed_volumes == ("volume-workspace", "volume-output")
    assert volumes.existing == set()
    assert restarted.pending_handoff() == ()
    assert restarted.get(stored.evidence_ref).state == "handoff_completed"


def test_handoff_replayer_does_not_start_when_retained_volume_is_missing(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())
    volumes = Volumes({"volume-workspace"})

    with pytest.raises(BrokerEvidenceHandoffError, match="volume is unavailable"):
        TerminalEvidenceHandoffReplayer(
            evidence_store=store, volume_gateway=volumes
        ).replay_pending()

    assert store.get(stored.evidence_ref).state == "retained"
    assert volumes.removed == []


def test_handoff_replayer_resumes_started_handoff_after_partial_cleanup(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())
    store.mark_handoff_started(stored.evidence_ref)
    volumes = Volumes({"volume-output"})

    replayed = TerminalEvidenceHandoffReplayer(
        evidence_store=store, volume_gateway=volumes
    ).replay_pending()

    assert replayed[0].removed_volumes == ("volume-output",)
    assert store.get(stored.evidence_ref).state == "handoff_completed"


def test_handoff_replayer_keeps_started_record_pending_when_cleanup_fails(
    tmp_path: Path,
) -> None:
    store = TerminalEvidenceStore(tmp_path / "terminal-evidence")
    stored = store.record(request(), result())
    volumes = Volumes({"volume-workspace", "volume-output"})
    volumes.fail_on_remove = "volume-output"

    with pytest.raises(RuntimeError, match="remove failed"):
        TerminalEvidenceHandoffReplayer(
            evidence_store=store, volume_gateway=volumes
        ).replay_pending()

    assert store.get(stored.evidence_ref).state == "handoff_started"
    assert store.pending_handoff()[0].evidence_ref == stored.evidence_ref
