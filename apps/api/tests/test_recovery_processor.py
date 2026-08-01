from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import ai_enterprise.application.recovery.processor as processor_module
from ai_enterprise.application.recovery.processor import (
    ControlledRecoveryProcessor,
    RecoveryCommand,
)
from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.domain.recovery.enums import (
    FailureClass,
    PipelineStage,
    RecoveryAttemptStatus,
)
from ai_enterprise.domain.recovery.exceptions import RevertConflict
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    CandidateCommit,
    RemoteEvidence,
    RepositoryPolicy,
    SnapshotEvidence,
    WorkspaceEvidence,
)
from ai_enterprise.infrastructure.recovery.revert_builder import PreparedRevert


@pytest.fixture(autouse=True)
def _inline_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    async def inline(function: Any, /, *args: object, **kwargs: object) -> Any:
        return function(*args, **kwargs)

    monkeypatch.setattr(processor_module.asyncio, "to_thread", inline)


def _command(status: RecoveryAttemptStatus = RecoveryAttemptStatus.QUEUED) -> RecoveryCommand:
    return RecoveryCommand(
        uuid.uuid4(),
        uuid.uuid4(),
        "recovery-worker",
        status,
        RepositoryPolicy("repo", "remote", "main", ("main",)),
        "head",
        "integrated",
        uuid.uuid4(),
        uuid.uuid4(),
        "binding",
        ExecutionScope(("allowed",), (".git",)),
        (ApprovedTestCommand(("pytest",)),),
        "Revert controlled integration\n",
        datetime(2026, 7, 31, tzinfo=UTC),
    )


class _Store:
    def __init__(self, command: RecoveryCommand) -> None:
        self.command = command
        self.transitions: list[tuple[RecoveryAttemptStatus, PipelineStage]] = []
        self.failed: tuple[RecoveryAttemptStatus, FailureClass] | None = None
        self.conflict: tuple[str, ...] | None = None
        self.completed = False

    async def claim_and_load(self, *args: object) -> RecoveryCommand:
        return self.command

    async def transition(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        stage: PipelineStage,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None:
        self.transitions.append((status, stage))

    async def record_tests(self, *args: object) -> None:
        pass

    async def record_commit(self, *args: object) -> None:
        pass

    async def record_remote(self, *args: object) -> None:
        pass

    async def record_conflict(
        self, command: RecoveryCommand, paths: tuple[str, ...], message: str
    ) -> None:
        self.conflict = paths

    async def fail(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        failure_class: FailureClass,
        code: str,
        message: str,
    ) -> None:
        self.failed = status, failure_class

    async def complete(self, *args: object) -> None:
        self.completed = True


class _Snapshots:
    cleaned = False

    def prepare(self, **kwargs: object) -> SnapshotEvidence:
        expected = str(kwargs["expected_commit_sha"])
        return SnapshotEvidence(
            Path("/tmp/recovery-fake"), "remote", expected, "tree", True, True, "config"
        )

    def cleanup(self, snapshot: SnapshotEvidence) -> None:
        self.cleaned = True


class _Reverts:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def prepare(self, **kwargs: object) -> PreparedRevert:
        if self.failure:
            raise self.failure
        return PreparedRevert("integrated", ("allowed/file.py",), "revert-tree")


class _Workspace:
    def verify(self, **kwargs: object) -> WorkspaceEvidence:
        return WorkspaceEvidence(("allowed/file.py",), "revert-tree")


class _Tests:
    def run(self, **kwargs: object) -> tuple[()]:
        return ()


_CANDIDATE = CandidateCommit("recovery", "revert-tree", "head", "message", "Bot", "Bot")


class _Commits:
    def create(self, **kwargs: object) -> CandidateCommit:
        return _CANDIDATE


class _Pusher:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def push(self, **kwargs: object) -> None:
        if self.failure:
            raise self.failure


class _Remote:
    def verify(self, **kwargs: object) -> RemoteEvidence:
        candidate = kwargs["candidate"]
        assert isinstance(candidate, CandidateCommit)
        return RemoteEvidence(
            "main", candidate.commit_sha, candidate.tree_sha, candidate.parent_sha
        )


def _processor(
    tmp_path: Path,
    store: _Store,
    snapshots: _Snapshots,
    reverts: _Reverts,
    pusher: _Pusher,
) -> ControlledRecoveryProcessor:
    return ControlledRecoveryProcessor(
        store=store,
        snapshots=snapshots,
        reverts=reverts,
        workspaces=_Workspace(),
        tests=_Tests(),
        commits=_Commits(),
        pusher=pusher,
        remote_verifier=_Remote(),
        runtime_temp_root=tmp_path,
    )


@pytest.mark.asyncio
async def test_recovery_success_records_stages_and_completes(tmp_path: Path) -> None:
    command = _command()
    store, snapshots = _Store(command), _Snapshots()
    await _processor(tmp_path, store, snapshots, _Reverts(), _Pusher()).execute(
        attempt_id=command.attempt_id, worker_id=command.worker_id
    )
    assert store.completed and snapshots.cleaned
    assert store.transitions[-1] == (
        RecoveryAttemptStatus.VERIFYING_REMOTE_RESULT,
        PipelineStage.REMOTE_RESULT_VERIFICATION,
    )


@pytest.mark.asyncio
async def test_revert_conflict_records_paths_and_fails(tmp_path: Path) -> None:
    command = _command()
    store, snapshots = _Store(command), _Snapshots()
    with pytest.raises(RevertConflict):
        await _processor(
            tmp_path,
            store,
            snapshots,
            _Reverts(RevertConflict("conflict", paths=("allowed/file.py",))),
            _Pusher(),
        ).execute(attempt_id=command.attempt_id, worker_id=command.worker_id)
    assert store.conflict == ("allowed/file.py",)
    assert store.failed == (
        RecoveryAttemptStatus.REVERT_CONFLICT,
        FailureClass.DETERMINISTIC_VALIDATION,
    )
    assert snapshots.cleaned


@pytest.mark.asyncio
async def test_ambiguous_push_is_reconciled_without_second_push(tmp_path: Path) -> None:
    command = _command()
    store = _Store(command)
    pusher = _Pusher(RuntimeError("connection lost"))
    await _processor(tmp_path, store, _Snapshots(), _Reverts(), pusher).execute(
        attempt_id=command.attempt_id, worker_id=command.worker_id
    )
    assert store.completed


@pytest.mark.asyncio
async def test_push_uncertain_resume_only_verifies_existing_commit(tmp_path: Path) -> None:
    base = _command(RecoveryAttemptStatus.PUSH_UNCERTAIN)
    command = replace(base, existing_candidate=_CANDIDATE)
    store = _Store(command)
    await _processor(
        tmp_path,
        store,
        _Snapshots(),
        _Reverts(AssertionError("revert must not run")),
        _Pusher(AssertionError("push must not run")),
    ).execute(attempt_id=command.attempt_id, worker_id=command.worker_id)
    assert store.completed
