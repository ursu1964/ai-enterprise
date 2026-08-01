from __future__ import annotations

import asyncio
import hashlib
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.domain.integration.enums import IntegrationAttemptStatus
from ai_enterprise.infrastructure.integration.interfaces import (
    CommitFactory,
    CommitPusher,
    PatchApplicator,
    RemoteCommitVerifier,
    SnapshotPreparer,
    TestExecutor,
    WorkspaceInspector,
)
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    CandidateCommit,
    IntegrationBinding,
    RemoteEvidence,
    RepositoryPolicy,
    TestRunEvidence,
)


@dataclass(frozen=True, slots=True)
class IntegrationCommand:
    attempt_id: uuid.UUID
    project_id: uuid.UUID
    worker_id: str
    policy: RepositoryPolicy
    binding: IntegrationBinding
    patch_bytes: bytes
    scope: ExecutionScope
    tests: tuple[ApprovedTestCommand, ...]
    commit_message: str
    commit_timestamp: datetime


class IntegrationAttemptStore(Protocol):
    async def claim_and_load(
        self, attempt_id: uuid.UUID, worker_id: str
    ) -> IntegrationCommand: ...

    async def transition(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None: ...

    async def fail(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        code: str,
        message: str,
    ) -> None: ...

    async def complete(
        self,
        command: IntegrationCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
        tests: tuple[TestRunEvidence, ...],
    ) -> None: ...


class RollbackMetadataHook(Protocol):
    async def record(
        self,
        *,
        command: IntegrationCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
        tests: tuple[TestRunEvidence, ...],
        repository: Path,
    ) -> None: ...


class NullRollbackMetadataHook:
    async def record(self, **kwargs: object) -> None:
        return None


class ControlledIntegrationProcessor:
    def __init__(
        self,
        *,
        store: IntegrationAttemptStore,
        snapshots: SnapshotPreparer,
        patches: PatchApplicator,
        workspaces: WorkspaceInspector,
        tests: TestExecutor,
        commits: CommitFactory,
        pusher: CommitPusher,
        remote_verifier: RemoteCommitVerifier,
        rollback: RollbackMetadataHook,
        runtime_temp_root: Path,
    ) -> None:
        self._store = store
        self._snapshots = snapshots
        self._patches = patches
        self._workspaces = workspaces
        self._tests = tests
        self._commits = commits
        self._pusher = pusher
        self._remote = remote_verifier
        self._rollback = rollback
        self._runtime_temp_root = runtime_temp_root

    async def execute(self, *, attempt_id: uuid.UUID, worker_id: str) -> None:
        command = await self._store.claim_and_load(attempt_id, worker_id)
        snapshot = None
        failure_status = IntegrationAttemptStatus.VERIFICATION_FAILED
        try:
            calculated = hashlib.sha256(command.patch_bytes).hexdigest()
            if calculated != command.binding.approved_patch_sha256:
                raise ValueError("PATCH_ARTIFACT_MISMATCH")

            snapshot = await asyncio.to_thread(
                self._snapshots.prepare,
                policy=command.policy,
                expected_commit_sha=command.binding.base_commit_sha,
                expected_tree_sha=command.binding.base_tree_sha,
            )
            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.SNAPSHOT_READY,
                "integration.snapshot_prepared",
                {
                    "actual_base_commit_sha": snapshot.commit_sha,
                    "actual_base_tree_sha": snapshot.tree_sha,
                    "remote_url": snapshot.remote_url,
                    "git_config_sha256": snapshot.git_config_sha256,
                },
            )

            failure_status = IntegrationAttemptStatus.PATCH_APPLY_FAILED
            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.APPLYING_PATCH,
                "integration.patch_applying",
                {"patch_sha256": calculated},
            )
            self._runtime_temp_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="integration-input-", dir=self._runtime_temp_root
            ) as temp:
                temp_root = Path(temp)
                patch_path = temp_root / "approved.patch"
                patch_path.write_bytes(command.patch_bytes)
                await asyncio.to_thread(
                    self._patches.verify_and_apply,
                    repository=snapshot.path,
                    patch_path=patch_path,
                    binding=command.binding,
                    scope=command.scope,
                )
                workspace = await asyncio.to_thread(
                    self._workspaces.verify,
                    repository=snapshot.path,
                    scope=command.scope,
                )
                await self._store.transition(
                    attempt_id,
                    IntegrationAttemptStatus.PATCH_APPLIED,
                    "integration.patch_applied",
                    {
                        "changed_paths": list(workspace.changed_paths),
                        "candidate_tree_sha": workspace.tree_sha,
                    },
                )

                failure_status = IntegrationAttemptStatus.TESTS_FAILED
                await self._store.transition(
                    attempt_id,
                    IntegrationAttemptStatus.TESTING,
                    "integration.tests_started",
                    {"command_count": len(command.tests)},
                )
                home = temp_root / "home"
                temporary = temp_root / "tmp"
                home.mkdir(mode=0o700)
                temporary.mkdir(mode=0o700)
                test_evidence = await asyncio.to_thread(
                    self._tests.run,
                    repository=snapshot.path,
                    commands=command.tests,
                    temporary_home=home,
                    temporary_directory=temporary,
                )
                tested_workspace = await asyncio.to_thread(
                    self._workspaces.verify,
                    repository=snapshot.path,
                    scope=command.scope,
                    expected_paths=workspace.changed_paths,
                )
                if tested_workspace.tree_sha != workspace.tree_sha:
                    raise ValueError("TESTED_TREE_MISMATCH")
                await self._store.transition(
                    attempt_id,
                    IntegrationAttemptStatus.TESTING,
                    "integration.tests_completed",
                    {
                        "tested_tree_sha": tested_workspace.tree_sha,
                        "test_runs": [
                            {
                                "command_index": item.command_index,
                                "command_sha256": item.command_sha256,
                                "status": item.status,
                                "exit_code": item.exit_code,
                                "duration_ms": item.duration_ms,
                            }
                            for item in test_evidence
                        ],
                    },
                )

                failure_status = IntegrationAttemptStatus.COMMIT_FAILED
                await self._store.transition(
                    attempt_id,
                    IntegrationAttemptStatus.COMMIT_CREATING,
                    "integration.commit_creating",
                    {"tested_tree_sha": tested_workspace.tree_sha},
                )
                candidate = await asyncio.to_thread(
                    self._commits.create,
                    repository=snapshot.path,
                    policy=command.policy,
                    tree_sha=tested_workspace.tree_sha,
                    parent_sha=command.binding.base_commit_sha,
                    message=command.commit_message,
                    timestamp=command.commit_timestamp,
                )

            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.COMMIT_CREATED,
                "integration.commit_created",
                self._candidate_evidence(candidate),
            )
            failure_status = IntegrationAttemptStatus.PUSH_FAILED
            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.PUSHING,
                "integration.push_started",
                {"target_branch": command.policy.target_branch},
            )
            await asyncio.to_thread(
                self._pusher.push,
                repository=snapshot.path,
                policy=command.policy,
                candidate=candidate,
                approved_base_commit=command.binding.base_commit_sha,
            )
            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.PUSHING,
                "integration.push_completed",
                {"commit_sha": candidate.commit_sha},
            )
            remote = await asyncio.to_thread(
                self._remote.verify,
                repository=snapshot.path,
                policy=command.policy,
                candidate=candidate,
            )
            await self._store.transition(
                attempt_id,
                IntegrationAttemptStatus.PUSHING,
                "integration.remote_verified",
                {
                    "commit_sha": remote.commit_sha,
                    "tree_sha": remote.tree_sha,
                    "parent_sha": remote.parent_sha,
                    "branch": remote.branch,
                },
            )
            await self._rollback.record(
                command=command,
                candidate=candidate,
                remote=remote,
                tests=test_evidence,
                repository=snapshot.path,
            )
            await self._store.complete(command, candidate, remote, test_evidence)
        except Exception as exc:
            await self._store.fail(
                attempt_id,
                failure_status,
                self._failure_code(exc),
                str(exc)[:2000],
            )
            raise
        finally:
            if snapshot is not None:
                await asyncio.to_thread(self._snapshots.cleanup, snapshot)

    @staticmethod
    def _candidate_evidence(candidate: CandidateCommit) -> dict[str, Any]:
        return {
            "commit_sha": candidate.commit_sha,
            "tree_sha": candidate.tree_sha,
            "parent_sha": candidate.parent_sha,
            "author_identity": candidate.author_identity,
            "committer_identity": candidate.committer_identity,
        }

    @staticmethod
    def _failure_code(exc: Exception) -> str:
        text = str(exc).strip()
        if text and text.replace("_", "").isalnum() and " " not in text:
            return text[:128]
        return type(exc).__name__.upper()[:128]


class IntegrationWorkerEntry:
    def __init__(self, processor: ControlledIntegrationProcessor, worker_id: str) -> None:
        self._processor = processor
        self._worker_id = worker_id

    async def handle(self, attempt_id: uuid.UUID) -> None:
        await self._processor.execute(attempt_id=attempt_id, worker_id=self._worker_id)
