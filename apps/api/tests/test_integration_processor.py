from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import ai_enterprise.application.integration.processor as processor_module
from ai_enterprise.application.integration.processor import (
    ControlledIntegrationProcessor,
    IntegrationCommand,
)
from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.domain.integration.enums import IntegrationAttemptStatus
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    CandidateCommit,
    IntegrationBinding,
    RemoteEvidence,
    RepositoryPolicy,
    SnapshotEvidence,
    WorkspaceEvidence,
)
from ai_enterprise.infrastructure.integration.models import (
    TestRunEvidence as IntegrationTestEvidence,
)


@pytest.fixture(autouse=True)
def _run_thread_calls_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline(function: Any, /, *args: object, **kwargs: object) -> Any:
        return function(*args, **kwargs)

    monkeypatch.setattr(processor_module.asyncio, "to_thread", inline)


def _command(tmp_path: Path) -> IntegrationCommand:
    patch = b"approved patch"
    import hashlib

    digest = hashlib.sha256(patch).hexdigest()
    return IntegrationCommand(
        attempt_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        worker_id="worker-1",
        policy=RepositoryPolicy("repo", "local", "main", ("main",)),
        binding=IntegrationBinding(
            "patch", digest, digest, digest, digest, "base", "base-tree", "approval", "attempt"
        ),
        patch_bytes=patch,
        scope=ExecutionScope(("allowed",), (".git",)),
        tests=(ApprovedTestCommand(("pytest", "test.py")),),
        commit_message="controlled\n",
        commit_timestamp=datetime(2026, 7, 31, tzinfo=UTC),
    )


class _Store:
    def __init__(self, command: IntegrationCommand) -> None:
        self.command = command
        self.transitions: list[tuple[IntegrationAttemptStatus, str]] = []
        self.failed: tuple[IntegrationAttemptStatus, str] | None = None
        self.completed = False

    async def claim_and_load(self, attempt_id: uuid.UUID, worker_id: str) -> IntegrationCommand:
        assert attempt_id == self.command.attempt_id
        assert worker_id == "worker-1"
        return self.command

    async def transition(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None:
        self.transitions.append((status, event_type))

    async def fail(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        code: str,
        message: str,
    ) -> None:
        self.failed = (status, code)

    async def complete(self, *args: object) -> None:
        self.completed = True


class _Snapshots:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.cleaned = False

    def prepare(self, **kwargs: object) -> SnapshotEvidence:
        return SnapshotEvidence(
            self.path, "local", "base", "base-tree", True, True, "config"
        )

    def cleanup(self, snapshot: SnapshotEvidence) -> None:
        self.cleaned = True


class _Patches:
    def verify_and_apply(self, **kwargs: object) -> str:
        return "hash"


class _Workspaces:
    def verify(self, **kwargs: object) -> WorkspaceEvidence:
        return WorkspaceEvidence(("allowed/file.py",), "candidate-tree")


class _Tests:
    def run(self, **kwargs: object) -> tuple[IntegrationTestEvidence, ...]:
        return (
            IntegrationTestEvidence(0, ("pytest",), "command", "passed", 0, 1, "", ""),
        )


class _Commits:
    candidate = CandidateCommit(
        "commit", "candidate-tree", "base", "controlled\n", "Bot <bot>", "Bot <bot>"
    )

    def create(self, **kwargs: object) -> CandidateCommit:
        return self.candidate


class _Pusher:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def push(self, **kwargs: object) -> None:
        if self.failure:
            raise self.failure


class _Remote:
    def verify(self, **kwargs: object) -> RemoteEvidence:
        return RemoteEvidence("main", "commit", "candidate-tree", "base")


class _Rollback:
    def __init__(self, store: _Store) -> None:
        self.store = store
        self.recorded = False

    async def record(self, **kwargs: object) -> None:
        assert not self.store.completed
        self.recorded = True


def _processor(
    tmp_path: Path, store: _Store, snapshots: _Snapshots, pusher: _Pusher, rollback: _Rollback
) -> ControlledIntegrationProcessor:
    return ControlledIntegrationProcessor(
        store=store,
        snapshots=snapshots,
        patches=_Patches(),
        workspaces=_Workspaces(),
        tests=_Tests(),
        commits=_Commits(),
        pusher=pusher,
        remote_verifier=_Remote(),
        rollback=rollback,
        runtime_temp_root=tmp_path / "runtime",
    )


@pytest.mark.asyncio
async def test_processor_records_durable_stage_sequence_and_rollback(tmp_path: Path) -> None:
    command = _command(tmp_path)
    store = _Store(command)
    snapshots = _Snapshots(tmp_path)
    rollback = _Rollback(store)
    await _processor(tmp_path, store, snapshots, _Pusher(), rollback).execute(
        attempt_id=command.attempt_id, worker_id="worker-1"
    )
    assert [status for status, _ in store.transitions] == [
        IntegrationAttemptStatus.SNAPSHOT_READY,
        IntegrationAttemptStatus.APPLYING_PATCH,
        IntegrationAttemptStatus.PATCH_APPLIED,
        IntegrationAttemptStatus.TESTING,
        IntegrationAttemptStatus.TESTING,
        IntegrationAttemptStatus.COMMIT_CREATING,
        IntegrationAttemptStatus.COMMIT_CREATED,
        IntegrationAttemptStatus.PUSHING,
        IntegrationAttemptStatus.PUSHING,
        IntegrationAttemptStatus.PUSHING,
    ]
    assert store.completed and rollback.recorded and snapshots.cleaned
    assert store.failed is None


@pytest.mark.asyncio
async def test_processor_classifies_push_failure_and_always_cleans_snapshot(
    tmp_path: Path,
) -> None:
    command = _command(tmp_path)
    store = _Store(command)
    snapshots = _Snapshots(tmp_path)
    rollback = _Rollback(store)
    with pytest.raises(RuntimeError, match="AUTHENTICATION_FAILED"):
        await _processor(
            tmp_path,
            store,
            snapshots,
            _Pusher(RuntimeError("AUTHENTICATION_FAILED")),
            rollback,
        ).execute(attempt_id=command.attempt_id, worker_id="worker-1")
    assert store.failed == (IntegrationAttemptStatus.PUSH_FAILED, "AUTHENTICATION_FAILED")
    assert snapshots.cleaned
    assert not rollback.recorded and not store.completed


@pytest.mark.asyncio
async def test_processor_rejects_artifact_before_snapshot(tmp_path: Path) -> None:
    command = _command(tmp_path)
    command = replace(command, patch_bytes=b"tampered")
    store = _Store(command)
    snapshots = _Snapshots(tmp_path)
    rollback = _Rollback(store)
    with pytest.raises(ValueError, match="PATCH_ARTIFACT_MISMATCH"):
        await _processor(tmp_path, store, snapshots, _Pusher(), rollback).execute(
            attempt_id=command.attempt_id, worker_id="worker-1"
        )
    assert store.failed == (
        IntegrationAttemptStatus.VERIFICATION_FAILED,
        "PATCH_ARTIFACT_MISMATCH",
    )
    assert not snapshots.cleaned
