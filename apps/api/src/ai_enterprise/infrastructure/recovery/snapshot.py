from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from ai_enterprise.infrastructure.integration.exceptions import SnapshotVerificationError
from ai_enterprise.infrastructure.integration.git_client import GitClient
from ai_enterprise.infrastructure.integration.models import RepositoryPolicy, SnapshotEvidence


class FreshRecoverySnapshotManager:
    """Clone and verify the exact approval-bound remote head in a new workspace."""

    def __init__(self, *, work_root: Path, git: GitClient | None = None) -> None:
        self._work_root = work_root.resolve()
        self._git = git or GitClient()

    def prepare(self, *, policy: RepositoryPolicy, expected_commit_sha: str) -> SnapshotEvidence:
        policy.validate_target()
        self._work_root.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="recovery-", dir=self._work_root))
        repository = root / "repository"
        try:
            self._git.run(("clone", "--no-checkout", "--", policy.remote_url, str(repository)))
            remote = self._git.run(("remote", "get-url", "origin"), cwd=repository).stdout.strip()
            if remote != policy.remote_url:
                raise SnapshotVerificationError("REMOTE_IDENTITY_MISMATCH")
            head_line = (
                self._git.run(
                    ("ls-remote", "--heads", "origin", f"refs/heads/{policy.target_branch}"),
                    cwd=repository,
                )
                .stdout.strip()
                .split()
            )
            if len(head_line) != 2 or head_line[0] != expected_commit_sha:
                raise SnapshotVerificationError("RECOVERY_REMOTE_STATE_CHANGED")
            self._git.run(("checkout", "--detach", expected_commit_sha), cwd=repository)
            commit = self._git.run(("rev-parse", "HEAD"), cwd=repository).stdout.strip()
            tree = self._git.run(("rev-parse", "HEAD^{tree}"), cwd=repository).stdout.strip()
            status = self._git.run(
                ("status", "--porcelain=v1", "--untracked-files=all"), cwd=repository
            ).stdout
            if commit != expected_commit_sha or status:
                raise SnapshotVerificationError("RECOVERY_SNAPSHOT_INVALID")
            gitlinks = self._git.run(("ls-files", "--stage"), cwd=repository).stdout
            if any(line.startswith("160000 ") for line in gitlinks.splitlines()):
                raise SnapshotVerificationError("UNEXPECTED_SUBMODULE_STATE")
            config = self._git.run(
                ("config", "--local", "--list", "--show-origin"), cwd=repository
            ).stdout
            return SnapshotEvidence(
                repository,
                remote,
                commit,
                tree,
                True,
                True,
                hashlib.sha256(config.encode()).hexdigest(),
            )
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def cleanup(self, snapshot: SnapshotEvidence) -> None:
        root = snapshot.path.parent.resolve()
        if root.parent != self._work_root or not root.name.startswith("recovery-"):
            raise SnapshotVerificationError("Refusing unsafe recovery cleanup")
        shutil.rmtree(root, ignore_errors=True)
