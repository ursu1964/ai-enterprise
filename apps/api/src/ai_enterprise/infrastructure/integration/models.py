from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositoryPolicy:
    repository_id: str
    remote_url: str
    target_branch: str
    allowed_target_branches: tuple[str, ...]
    integration_name: str = "Enterprise Integration Bot"
    integration_email: str = "integration-bot@internal.invalid"

    def validate_target(self) -> None:
        if self.target_branch not in self.allowed_target_branches:
            raise ValueError(f"Target branch is not allowed: {self.target_branch}")
        if not self.target_branch or self.target_branch.startswith("-"):
            raise ValueError("Invalid target branch")


@dataclass(frozen=True, slots=True)
class IntegrationBinding:
    patch_id: str
    patch_sha256: str
    artifact_sha256: str
    audit_patch_sha256: str
    approved_patch_sha256: str
    base_commit_sha: str
    base_tree_sha: str
    approval_id: str
    attempt_id: str


@dataclass(frozen=True, slots=True)
class SnapshotEvidence:
    path: Path
    remote_url: str
    commit_sha: str
    tree_sha: str
    clean: bool
    submodules_verified: bool
    git_config_sha256: str


@dataclass(frozen=True, slots=True)
class WorkspaceEvidence:
    changed_paths: tuple[str, ...]
    tree_sha: str


@dataclass(frozen=True, slots=True)
class ApprovedTestCommand:
    argv: tuple[str, ...]
    timeout_seconds: int = 300
    environment: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TestRunEvidence:
    command_index: int
    argv: tuple[str, ...]
    command_sha256: str
    status: str
    exit_code: int | None
    duration_ms: int
    stdout: str
    stderr: str


@dataclass(frozen=True, slots=True)
class CandidateCommit:
    commit_sha: str
    tree_sha: str
    parent_sha: str
    message: str
    author_identity: str
    committer_identity: str


@dataclass(frozen=True, slots=True)
class RemoteEvidence:
    branch: str
    commit_sha: str
    tree_sha: str
    parent_sha: str
