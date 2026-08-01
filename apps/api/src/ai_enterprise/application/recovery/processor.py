from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.domain.recovery.enums import (
    FailureClass,
    PipelineStage,
    RecoveryAttemptStatus,
)
from ai_enterprise.domain.recovery.exceptions import RevertConflict
from ai_enterprise.infrastructure.integration.exceptions import TargetBranchAdvancedError
from ai_enterprise.infrastructure.integration.interfaces import (
    CommitFactory,
    CommitPusher,
    RemoteCommitVerifier,
    TestExecutor,
    WorkspaceInspector,
)
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    CandidateCommit,
    RemoteEvidence,
    RepositoryPolicy,
    SnapshotEvidence,
    TestRunEvidence,
)
from ai_enterprise.infrastructure.recovery.revert_builder import PreparedRevert


@dataclass(frozen=True, slots=True)
class RecoveryCommand:
    attempt_id: uuid.UUID
    project_id: uuid.UUID
    worker_id: str
    initial_status: RecoveryAttemptStatus
    policy: RepositoryPolicy
    expected_remote_head_sha: str
    integration_commit_sha: str
    rollback_record_id: uuid.UUID
    approval_id: uuid.UUID
    approval_binding_sha256: str
    scope: ExecutionScope
    tests: tuple[ApprovedTestCommand, ...]
    commit_message: str
    commit_timestamp: datetime
    existing_candidate: CandidateCommit | None = None


class RecoverySnapshotPreparer(Protocol):
    def prepare(
        self, *, policy: RepositoryPolicy, expected_commit_sha: str
    ) -> SnapshotEvidence: ...

    def cleanup(self, snapshot: SnapshotEvidence) -> None: ...


class RecoveryRevertBuilder(Protocol):
    def prepare(
        self, *, repository: Path, integration_commit_sha: str
    ) -> PreparedRevert: ...


class RecoveryAttemptStore(Protocol):
    async def claim_and_load(self, attempt_id: uuid.UUID, worker_id: str) -> RecoveryCommand: ...

    async def transition(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        stage: PipelineStage,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None: ...

    async def record_tests(
        self, command: RecoveryCommand, tests: tuple[TestRunEvidence, ...]
    ) -> None: ...

    async def record_commit(self, command: RecoveryCommand, candidate: CandidateCommit) -> None: ...

    async def record_remote(self, command: RecoveryCommand, remote: RemoteEvidence) -> None: ...

    async def record_conflict(
        self, command: RecoveryCommand, paths: tuple[str, ...], message: str
    ) -> None: ...

    async def fail(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        failure_class: FailureClass,
        code: str,
        message: str,
    ) -> None: ...

    async def complete(
        self,
        command: RecoveryCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
    ) -> None: ...


class ControlledRecoveryProcessor:
    def __init__(
        self,
        *,
        store: RecoveryAttemptStore,
        snapshots: RecoverySnapshotPreparer,
        reverts: RecoveryRevertBuilder,
        workspaces: WorkspaceInspector,
        tests: TestExecutor,
        commits: CommitFactory,
        pusher: CommitPusher,
        remote_verifier: RemoteCommitVerifier,
        runtime_temp_root: Path,
    ) -> None:
        self._store = store
        self._snapshots = snapshots
        self._reverts = reverts
        self._workspaces = workspaces
        self._tests = tests
        self._commits = commits
        self._pusher = pusher
        self._remote = remote_verifier
        self._runtime_temp_root = runtime_temp_root

    async def execute(self, *, attempt_id: uuid.UUID, worker_id: str) -> None:
        command = await self._store.claim_and_load(attempt_id, worker_id)
        if command.initial_status == RecoveryAttemptStatus.PUSH_UNCERTAIN:
            await self._reconcile_only(command)
            return

        snapshot: SnapshotEvidence | None = None
        failure_status = RecoveryAttemptStatus.REMOTE_STATE_CHANGED
        failure_class = FailureClass.CONCURRENCY_CONFLICT
        try:
            await self._store.transition(
                command,
                RecoveryAttemptStatus.PREPARING_WORKSPACE,
                PipelineStage.SNAPSHOT,
                "recovery.snapshot_started",
                {"expected_remote_head_sha": command.expected_remote_head_sha},
            )
            snapshot = await asyncio.to_thread(
                self._snapshots.prepare,
                policy=command.policy,
                expected_commit_sha=command.expected_remote_head_sha,
            )
            await self._store.transition(
                command,
                RecoveryAttemptStatus.CREATING_REVERT,
                PipelineStage.REVERT,
                "recovery.snapshot_verified",
                {"commit_sha": snapshot.commit_sha, "tree_sha": snapshot.tree_sha},
            )
            failure_status = RecoveryAttemptStatus.REVERT_CONFLICT
            failure_class = FailureClass.DETERMINISTIC_VALIDATION
            prepared: PreparedRevert = await asyncio.to_thread(
                self._reverts.prepare,
                repository=snapshot.path,
                integration_commit_sha=command.integration_commit_sha,
            )
            workspace = await asyncio.to_thread(
                self._workspaces.verify,
                repository=snapshot.path,
                scope=command.scope,
                expected_paths=prepared.changed_paths,
            )
            if workspace.tree_sha != prepared.candidate_tree_sha:
                raise ValueError("RECOVERY_TREE_MISMATCH")

            failure_status = RecoveryAttemptStatus.TEST_FAILED
            await self._store.transition(
                command,
                RecoveryAttemptStatus.RUNNING_TESTS,
                PipelineStage.TEST,
                "recovery.tests_started",
                {"command_count": len(command.tests)},
            )
            self._runtime_temp_root.mkdir(parents=True, exist_ok=True)
            home = self._runtime_temp_root / f"home-{command.attempt_id}"
            temporary = self._runtime_temp_root / f"tmp-{command.attempt_id}"
            home.mkdir(parents=True, exist_ok=True)
            temporary.mkdir(parents=True, exist_ok=True)
            test_evidence = await asyncio.to_thread(
                self._tests.run,
                repository=snapshot.path,
                commands=command.tests,
                temporary_home=home,
                temporary_directory=temporary,
            )
            tested = await asyncio.to_thread(
                self._workspaces.verify,
                repository=snapshot.path,
                scope=command.scope,
                expected_paths=prepared.changed_paths,
            )
            if tested.tree_sha != prepared.candidate_tree_sha:
                raise ValueError("RECOVERY_TEST_CHANGED_TREE")
            await self._store.record_tests(command, test_evidence)

            failure_status = RecoveryAttemptStatus.COMMIT_FAILED
            await self._store.transition(
                command,
                RecoveryAttemptStatus.CREATING_COMMIT,
                PipelineStage.COMMIT,
                "recovery.commit_started",
                {"tree_sha": tested.tree_sha},
            )
            candidate = await asyncio.to_thread(
                self._commits.create,
                repository=snapshot.path,
                policy=command.policy,
                tree_sha=tested.tree_sha,
                parent_sha=command.expected_remote_head_sha,
                message=command.commit_message,
                timestamp=command.commit_timestamp,
            )
            await self._store.record_commit(command, candidate)

            failure_status = RecoveryAttemptStatus.PUSH_UNCERTAIN
            failure_class = FailureClass.TRANSIENT_INFRASTRUCTURE
            await self._store.transition(
                command,
                RecoveryAttemptStatus.PUSHING,
                PipelineStage.PUSH,
                "recovery.push_started",
                {"commit_sha": candidate.commit_sha},
            )
            try:
                await asyncio.to_thread(
                    self._pusher.push,
                    repository=snapshot.path,
                    policy=command.policy,
                    candidate=candidate,
                    approved_base_commit=command.expected_remote_head_sha,
                )
            except TargetBranchAdvancedError:
                failure_status = RecoveryAttemptStatus.REMOTE_STATE_CHANGED
                failure_class = FailureClass.CONCURRENCY_CONFLICT
                raise
            except Exception:
                remote = await self._try_reconcile(snapshot.path, command, candidate)
                if remote is None:
                    raise
            else:
                failure_status = RecoveryAttemptStatus.REMOTE_VERIFICATION_FAILED
                failure_class = FailureClass.INTEGRITY
                remote = await asyncio.to_thread(
                    self._remote.verify,
                    repository=snapshot.path,
                    policy=command.policy,
                    candidate=candidate,
                )
            await self._finish(command, candidate, remote)
        except RevertConflict as exc:
            await self._store.record_conflict(command, exc.paths, str(exc))
            await self._store.fail(
                command,
                RecoveryAttemptStatus.REVERT_CONFLICT,
                FailureClass.DETERMINISTIC_VALIDATION,
                exc.code,
                str(exc),
            )
            raise
        except Exception as exc:
            await self._store.fail(
                command,
                failure_status,
                failure_class,
                self._code(exc),
                str(exc)[:2000],
            )
            raise
        finally:
            if snapshot is not None:
                await asyncio.to_thread(self._snapshots.cleanup, snapshot)

    async def _reconcile_only(self, command: RecoveryCommand) -> None:
        if command.existing_candidate is None:
            raise ValueError("RECOVERY_COMMIT_EVIDENCE_MISSING")
        snapshot = await asyncio.to_thread(
            self._snapshots.prepare,
            policy=command.policy,
            expected_commit_sha=command.existing_candidate.commit_sha,
        )
        try:
            remote = await asyncio.to_thread(
                self._remote.verify,
                repository=snapshot.path,
                policy=command.policy,
                candidate=command.existing_candidate,
            )
            await self._finish(command, command.existing_candidate, remote)
        except Exception as exc:
            await self._store.fail(
                command,
                RecoveryAttemptStatus.PUSH_UNCERTAIN,
                FailureClass.CONCURRENCY_CONFLICT,
                self._code(exc),
                str(exc)[:2000],
            )
            raise
        finally:
            await asyncio.to_thread(self._snapshots.cleanup, snapshot)

    async def _try_reconcile(
        self, repository: Path, command: RecoveryCommand, candidate: CandidateCommit
    ) -> RemoteEvidence | None:
        try:
            return await asyncio.to_thread(
                self._remote.verify,
                repository=repository,
                policy=command.policy,
                candidate=candidate,
            )
        except Exception:
            return None

    async def _finish(
        self,
        command: RecoveryCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
    ) -> None:
        await self._store.transition(
            command,
            RecoveryAttemptStatus.VERIFYING_REMOTE_RESULT,
            PipelineStage.REMOTE_RESULT_VERIFICATION,
            "recovery.remote_verified",
            {"commit_sha": remote.commit_sha, "tree_sha": remote.tree_sha},
        )
        await self._store.record_remote(command, remote)
        await self._store.complete(command, candidate, remote)

    @staticmethod
    def _code(exc: Exception) -> str:
        return str(getattr(exc, "code", type(exc).__name__)).upper()[:128]


class RecoveryWorkerEntry:
    def __init__(self, processor: ControlledRecoveryProcessor, worker_id: str) -> None:
        self._processor = processor
        self._worker_id = worker_id

    async def handle(self, attempt_id: uuid.UUID) -> None:
        await self._processor.execute(attempt_id=attempt_id, worker_id=self._worker_id)
