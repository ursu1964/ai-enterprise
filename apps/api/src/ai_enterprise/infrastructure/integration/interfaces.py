from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from ai_enterprise.domain.execution.policies import ExecutionScope

from .models import (
    ApprovedTestCommand,
    CandidateCommit,
    IntegrationBinding,
    RemoteEvidence,
    RepositoryPolicy,
    SnapshotEvidence,
    TestRunEvidence,
    WorkspaceEvidence,
)


class SnapshotPreparer(Protocol):
    def prepare(
        self,
        *,
        policy: RepositoryPolicy,
        expected_commit_sha: str,
        expected_tree_sha: str,
    ) -> SnapshotEvidence: ...

    def cleanup(self, snapshot: SnapshotEvidence) -> None: ...


class PatchApplicator(Protocol):
    def verify_and_apply(
        self,
        *,
        repository: Path,
        patch_path: Path,
        binding: IntegrationBinding,
        scope: ExecutionScope,
    ) -> str: ...


class WorkspaceInspector(Protocol):
    def verify(
        self,
        *,
        repository: Path,
        scope: ExecutionScope,
        expected_paths: tuple[str, ...] | None = None,
    ) -> WorkspaceEvidence: ...


class TestExecutor(Protocol):
    def run(
        self,
        *,
        repository: Path,
        commands: tuple[ApprovedTestCommand, ...],
        temporary_home: Path,
        temporary_directory: Path,
    ) -> tuple[TestRunEvidence, ...]: ...


class CommitFactory(Protocol):
    def create(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        tree_sha: str,
        parent_sha: str,
        message: str,
        timestamp: datetime,
    ) -> CandidateCommit: ...


class CommitPusher(Protocol):
    def push(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        candidate: CandidateCommit,
        approved_base_commit: str,
    ) -> None: ...


class RemoteCommitVerifier(Protocol):
    def verify(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        candidate: CandidateCommit,
    ) -> RemoteEvidence: ...
