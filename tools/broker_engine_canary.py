#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import io
import json
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any

from ai_enterprise.infrastructure.execution_broker.engine import DockerEngineAdapter
from ai_enterprise.infrastructure.execution_broker.evidence import TerminalEvidenceStore
from ai_enterprise.infrastructure.execution_broker.policy import (
    BrokerPolicy,
    BrokerRunRequest,
)
from ai_enterprise.infrastructure.execution_broker.runner import DurableBrokerRunner
from ai_enterprise.infrastructure.execution_broker.store import SnapshotStore

EXECUTION_IMAGE = "ai-enterprise-execution-agent:local"
REVIEW_IMAGE = "ai-enterprise-review-agent:local"


def _snapshot_archive() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        content = b"original\n"
        info = tarfile.TarInfo("seed.txt")
        info.mode = 0o644
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _result(archive_bytes: bytes) -> dict[str, Any]:
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        matches = [member for member in archive.getmembers() if member.name.endswith("result.json")]
        if len(matches) != 1:
            raise RuntimeError("canary output must contain exactly one result.json")
        handle = archive.extractfile(matches[0])
        if handle is None:
            raise RuntimeError("canary result.json is unreadable")
        value = json.loads(handle.read())
    if not isinstance(value, dict) or value.get("success") is not True:
        raise RuntimeError("canary result contract did not report success")
    return value


def _runtime_input(kind: str, uid: int) -> dict[str, Any]:
    input_name = "execution.json" if kind == "execution" else "review.json"
    probe = f"""import os
from pathlib import Path

assert os.getuid() == {uid}
runtime_input = Path('/runtime-input/{input_name}')
runtime_input.read_text(encoding='utf-8')
try:
    runtime_input.write_text('forbidden', encoding='utf-8')
except OSError:
    pass
else:
    raise SystemExit(41)
seed = Path('/workspace/seed.txt')
assert seed.read_text(encoding='utf-8') == 'original\\n'
seed.write_text('changed\\n', encoding='utf-8')
Path('/workspace/created.txt').write_text('created\\n', encoding='utf-8')
"""
    command = {"argv": ["python", "-c", probe], "timeout_seconds": 20, "required": True}
    if kind == "execution":
        return {"implementation": command, "tests": []}
    return {"approved_tests": [command], "review_checks": []}


def _run_kind(client: Any, policy: BrokerPolicy, kind: str, uid: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"broker-{kind}-canary-") as temporary:
        temporary_root = Path(temporary)
        store = SnapshotStore(temporary_root / "store")
        evidence_store = TerminalEvidenceStore(temporary_root / "terminal-evidence")
        stored = store.register(_snapshot_archive(), owner_worker_id="canary")
        runtime_input = _runtime_input(kind, uid)
        encoded = json.dumps(
            runtime_input, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        workload_id = uuid.uuid4()
        request = BrokerRunRequest.model_validate(
            {
                "schema_version": 1,
                "idempotency_key": uuid.uuid4(),
                "workload_id": workload_id,
                "kind": kind,
                "image_policy_key": f"{kind}-agent",
                "resource_profile": "small",
                "snapshot_ref": stored.snapshot_ref,
                "input_sha256": hashlib.sha256(encoded).hexdigest(),
                "correlation_id": uuid.uuid4(),
            }
        )
        receipt = DurableBrokerRunner(
            snapshot_store=store,
            engine=DockerEngineAdapter(client, policy),
            evidence_store=evidence_store,
        ).run(
            request,
            owner_worker_id="canary",
            runtime_input=runtime_input,
        )
        result = receipt.result
        if result.exit_code != 0:
            raise RuntimeError(f"{kind} canary exited {result.exit_code}: {result.runtime_log}")
        _result(result.output_archive)
        restarted_evidence_store = TerminalEvidenceStore(temporary_root / "terminal-evidence")
        pending_handoff = restarted_evidence_store.pending_handoff()
        if (
            len(pending_handoff) != 1
            or pending_handoff[0].evidence_ref != receipt.evidence.evidence_ref
        ):
            raise RuntimeError("broker canary evidence handoff did not survive restart")
        retained = result.retained_evidence_volumes
        if set(retained) != {"workspace", "output"}:
            raise RuntimeError("broker canary did not retain terminal evidence volumes")
        retained_volumes = [
            client.volumes.get(retained["workspace"]),
            client.volumes.get(retained["output"]),
        ]
        resolved = store.resolve(stored.snapshot_ref, owner_worker_id="canary")
        if (resolved.root / "seed.txt").read_bytes() != b"original\n":
            raise RuntimeError("immutable snapshot changed during canary")
        label = f"ai.enterprise.workload-id={workload_id}"
        if client.containers.list(all=True, filters={"label": label}):
            raise RuntimeError("broker canary left a container behind")
        visible_volumes = client.volumes.list(filters={"label": label})
        visible_names = {volume.name for volume in visible_volumes}
        if visible_names != set(retained.values()):
            raise RuntimeError("broker canary volume retention did not match terminal evidence")
        for volume in retained_volumes:
            volume.remove(force=True)
        restarted_evidence_store.mark_handoff_completed(receipt.evidence.evidence_ref)
        if client.volumes.list(filters={"label": label}):
            raise RuntimeError("broker canary cleanup left a volume behind")
        return {
            "kind": kind,
            "runtime_uid": uid,
            "input_read_only": True,
            "workspace_writable": True,
            "output_writable": True,
            "snapshot_unchanged": True,
            "terminal_evidence_retained": True,
            "terminal_evidence_manifest_durable": True,
            "cleanup_proven_after_handoff": True,
            "tree_sha256": stored.tree_sha256,
        }


def main() -> int:
    docker_module = importlib.import_module("docker")
    client = docker_module.from_env()
    execution_id = client.images.get(EXECUTION_IMAGE).id
    review_id = client.images.get(REVIEW_IMAGE).id
    policy = BrokerPolicy(execution_image_id=execution_id, review_image_id=review_id)
    canaries = [
        _run_kind(client, policy, "execution", 10001),
        _run_kind(client, policy, "review", 10002),
    ]
    print(json.dumps({"status": "passed", "canaries": canaries}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
