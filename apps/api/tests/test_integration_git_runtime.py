from __future__ import annotations

import hashlib
import os
import subprocess
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.infrastructure.integration.commit_creator import (
    DeterministicCommitCreator,
)
from ai_enterprise.infrastructure.integration.credentials import CredentialLease
from ai_enterprise.infrastructure.integration.exceptions import (
    ApprovedTestError,
    PatchVerificationError,
    RemoteVerificationError,
    SnapshotVerificationError,
    TargetBranchAdvancedError,
    WorkspaceVerificationError,
)
from ai_enterprise.infrastructure.integration.git_client import GitClient
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    IntegrationBinding,
    RepositoryPolicy,
)
from ai_enterprise.infrastructure.integration.patch_verifier import VerifiedPatchApplier
from ai_enterprise.infrastructure.integration.pusher import RestrictedPusher
from ai_enterprise.infrastructure.integration.remote_verifier import RemoteVerifier
from ai_enterprise.infrastructure.integration.snapshot_manager import FreshSnapshotManager
from ai_enterprise.infrastructure.integration.test_runner import ApprovedTestRunner
from ai_enterprise.infrastructure.integration.workspace_verifier import WorkspaceVerifier


def _run(*argv: str, cwd: Path | None = None) -> str:
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    return subprocess.run(
        argv,
        cwd=cwd,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repository(tmp_path: Path) -> tuple[Path, str, str]:
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    _run("git", "init", "-b", "main", cwd=source)
    (source / "allowed").mkdir()
    (source / "allowed" / "value.txt").write_text("before\n", encoding="utf-8")
    _run("git", "add", ".", cwd=source)
    _run("git", "commit", "-m", "base", cwd=source)
    _run("git", "init", "--bare", str(remote))
    _run("git", "remote", "add", "origin", str(remote), cwd=source)
    _run("git", "push", "origin", "main", cwd=source)
    commit = _run("git", "rev-parse", "HEAD", cwd=source)
    tree = _run("git", "rev-parse", "HEAD^{tree}", cwd=source)
    return remote, commit, tree


def _policy(remote: Path) -> RepositoryPolicy:
    return RepositoryPolicy(
        repository_id="repo-1",
        remote_url=str(remote),
        target_branch="main",
        allowed_target_branches=("main",),
    )


def _patch(snapshot: Path, tmp_path: Path) -> tuple[Path, str]:
    target = snapshot / "allowed" / "value.txt"
    target.write_text("after\n", encoding="utf-8")
    patch = subprocess.run(
        ["git", "diff", "--binary", "HEAD"],
        cwd=snapshot,
        check=True,
        capture_output=True,
    ).stdout
    _run("git", "checkout", "--", "allowed/value.txt", cwd=snapshot)
    path = tmp_path / "approved.patch"
    path.write_bytes(patch)
    return path, hashlib.sha256(patch).hexdigest()


def _binding(sha256: str, commit: str, tree: str) -> IntegrationBinding:
    return IntegrationBinding(
        patch_id="patch-1",
        patch_sha256=sha256,
        artifact_sha256=sha256,
        audit_patch_sha256=sha256,
        approved_patch_sha256=sha256,
        base_commit_sha=commit,
        base_tree_sha=tree,
        approval_id="approval-1",
        attempt_id="attempt-1",
    )


def test_full_local_integration_pipeline(
    repository: tuple[Path, str, str], tmp_path: Path
) -> None:
    remote, base, base_tree = repository
    manager = FreshSnapshotManager(work_root=tmp_path / "work")
    snapshot = manager.prepare(
        policy=_policy(remote), expected_commit_sha=base, expected_tree_sha=base_tree
    )
    patch_path, patch_hash = _patch(snapshot.path, tmp_path)
    scope = ExecutionScope(("allowed",), (".git",))
    VerifiedPatchApplier().verify_and_apply(
        repository=snapshot.path,
        patch_path=patch_path,
        binding=_binding(patch_hash, base, base_tree),
        scope=scope,
    )
    workspace = WorkspaceVerifier().verify(repository=snapshot.path, scope=scope)
    assert workspace.changed_paths == ("allowed/value.txt",)

    runner = ApprovedTestRunner(allowed_executables={"python"})
    evidence = runner.run(
        repository=snapshot.path,
        commands=(
            ApprovedTestCommand(
                ("python", "-c", "assert open('allowed/value.txt').read() == 'after\\n'")
            ),
        ),
        temporary_home=tmp_path / "home",
        temporary_directory=tmp_path / "tmp",
    )
    assert evidence[0].status == "passed"
    WorkspaceVerifier().verify(
        repository=snapshot.path,
        scope=scope,
        expected_paths=workspace.changed_paths,
    )

    timestamp = datetime(2026, 7, 31, tzinfo=UTC)
    creator = DeterministicCommitCreator()
    candidate = creator.create(
        repository=snapshot.path,
        policy=_policy(remote),
        tree_sha=workspace.tree_sha,
        parent_sha=base,
        message="Apply approved patch\n",
        timestamp=timestamp,
    )
    RestrictedPusher(credentials=_TrackingBroker()).push(
        repository=snapshot.path,
        policy=_policy(remote),
        candidate=candidate,
        approved_base_commit=base,
    )
    remote_evidence = RemoteVerifier().verify(
        repository=snapshot.path, policy=_policy(remote), candidate=candidate
    )
    assert remote_evidence.commit_sha == candidate.commit_sha
    assert remote_evidence.tree_sha == workspace.tree_sha
    manager.cleanup(snapshot)
    assert not snapshot.path.exists()


class _TrackingBroker:
    def __init__(self) -> None:
        self.acquired = False
        self.released = False

    @contextmanager
    def acquire_push_credentials(self, repository_id: str):  # type: ignore[no-untyped-def]
        self.acquired = True
        try:
            yield CredentialLease({})
        finally:
            self.released = True


def test_commit_is_deterministic(repository: tuple[Path, str, str], tmp_path: Path) -> None:
    remote, base, base_tree = repository
    manager = FreshSnapshotManager(work_root=tmp_path / "work")
    commits = []
    for _ in range(2):
        snapshot = manager.prepare(
            policy=_policy(remote), expected_commit_sha=base, expected_tree_sha=base_tree
        )
        patch_path, patch_hash = _patch(snapshot.path, tmp_path)
        scope = ExecutionScope(("allowed",), (".git",))
        VerifiedPatchApplier().verify_and_apply(
            repository=snapshot.path,
            patch_path=patch_path,
            binding=_binding(patch_hash, base, base_tree),
            scope=scope,
        )
        tree = WorkspaceVerifier().verify(repository=snapshot.path, scope=scope).tree_sha
        commits.append(
            DeterministicCommitCreator().create(
                repository=snapshot.path,
                policy=_policy(remote),
                tree_sha=tree,
                parent_sha=base,
                message="same\n",
                timestamp=datetime(2026, 7, 31, tzinfo=UTC),
            ).commit_sha
        )
        manager.cleanup(snapshot)
    assert commits[0] == commits[1]


def test_patch_hash_scope_and_test_command_are_enforced(
    repository: tuple[Path, str, str], tmp_path: Path
) -> None:
    remote, base, tree = repository
    snapshot = FreshSnapshotManager(work_root=tmp_path / "work").prepare(
        policy=_policy(remote), expected_commit_sha=base, expected_tree_sha=tree
    )
    patch_path, patch_hash = _patch(snapshot.path, tmp_path)
    bad = _binding("0" * 64, base, tree)
    with pytest.raises(PatchVerificationError, match="PATCH_ARTIFACT_MISMATCH"):
        VerifiedPatchApplier().verify_and_apply(
            repository=snapshot.path,
            patch_path=patch_path,
            binding=bad,
            scope=ExecutionScope(("allowed",), (".git",)),
        )
    with pytest.raises(ApprovedTestError, match="UNAPPROVED_EXECUTABLE"):
        ApprovedTestRunner(allowed_executables={"python"}).run(
            repository=snapshot.path,
            commands=(ApprovedTestCommand(("sh", "-c", "exit 0")),),
            temporary_home=tmp_path / "home",
            temporary_directory=tmp_path / "tmp",
        )
    (snapshot.path / "outside.txt").write_text("bad", encoding="utf-8")
    with pytest.raises(WorkspaceVerificationError, match="PATCH_SCOPE_VIOLATION"):
        WorkspaceVerifier().verify(
            repository=snapshot.path,
            scope=ExecutionScope(("allowed",), (".git",)),
        )


def test_advanced_remote_branch_prevents_push(
    repository: tuple[Path, str, str], tmp_path: Path
) -> None:
    remote, base, tree = repository
    manager = FreshSnapshotManager(work_root=tmp_path / "work")
    snapshot = manager.prepare(
        policy=_policy(remote), expected_commit_sha=base, expected_tree_sha=tree
    )
    patch_path, patch_hash = _patch(snapshot.path, tmp_path)
    scope = ExecutionScope(("allowed",), (".git",))
    VerifiedPatchApplier().verify_and_apply(
        repository=snapshot.path,
        patch_path=patch_path,
        binding=_binding(patch_hash, base, tree),
        scope=scope,
    )
    candidate_tree = WorkspaceVerifier().verify(repository=snapshot.path, scope=scope).tree_sha
    candidate = DeterministicCommitCreator().create(
        repository=snapshot.path,
        policy=_policy(remote),
        tree_sha=candidate_tree,
        parent_sha=base,
        message="candidate\n",
        timestamp=datetime(2026, 7, 31, tzinfo=UTC),
    )

    other = tmp_path / "other"
    _run("git", "clone", str(remote), str(other))
    _run("git", "checkout", "main", cwd=other)
    (other / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    _run("git", "add", ".", cwd=other)
    _run("git", "commit", "-m", "advance", cwd=other)
    _run("git", "push", "origin", "main", cwd=other)

    broker = _TrackingBroker()
    with pytest.raises(TargetBranchAdvancedError):
        RestrictedPusher(credentials=broker).push(
            repository=snapshot.path,
            policy=_policy(remote),
            candidate=candidate,
            approved_base_commit=base,
        )
    assert broker.acquired and broker.released


def test_git_client_ignores_ambient_global_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_home = tmp_path / "host-home"
    fake_home.mkdir()
    (fake_home / ".gitconfig").write_text("[alias]\n  forbidden = status\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(fake_home))
    result = GitClient().run(("forbidden",), check=False)
    assert result.returncode != 0


def test_snapshot_tree_mismatch_is_cleaned_up(
    repository: tuple[Path, str, str], tmp_path: Path
) -> None:
    remote, base, _ = repository
    work = tmp_path / "work"
    with pytest.raises(SnapshotVerificationError, match="BASE_TREE_MISMATCH"):
        FreshSnapshotManager(work_root=work).prepare(
            policy=_policy(remote),
            expected_commit_sha=base,
            expected_tree_sha="0" * 40,
        )
    assert list(work.iterdir()) == []


def test_failed_test_stops_and_preserves_evidence(tmp_path: Path) -> None:
    runner = ApprovedTestRunner(allowed_executables={"python"})
    commands = (
        ApprovedTestCommand(("python", "-c", "raise SystemExit(7)")),
        ApprovedTestCommand(("python", "-c", "raise SystemExit(0)")),
    )
    with pytest.raises(ApprovedTestError) as captured:
        runner.run(
            repository=tmp_path,
            commands=commands,
            temporary_home=tmp_path,
            temporary_directory=tmp_path,
        )
    assert len(captured.value.evidence) == 1


def test_remote_verification_rejects_wrong_candidate(
    repository: tuple[Path, str, str], tmp_path: Path
) -> None:
    remote, base, tree = repository
    snapshot = FreshSnapshotManager(work_root=tmp_path / "work").prepare(
        policy=_policy(remote), expected_commit_sha=base, expected_tree_sha=tree
    )
    candidate = DeterministicCommitCreator().create(
        repository=snapshot.path,
        policy=_policy(remote),
        tree_sha=tree,
        parent_sha=base,
        message="not pushed\n",
        timestamp=datetime(2026, 7, 31, tzinfo=UTC),
    )
    with pytest.raises(RemoteVerificationError, match="REMOTE_COMMIT_MISMATCH"):
        RemoteVerifier().verify(
            repository=snapshot.path,
            policy=_policy(remote),
            candidate=candidate,
        )
