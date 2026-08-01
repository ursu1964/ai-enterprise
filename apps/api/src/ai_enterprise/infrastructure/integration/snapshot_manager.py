from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path

from .exceptions import SnapshotVerificationError
from .git_client import GitClient
from .models import RepositoryPolicy, SnapshotEvidence


class FreshSnapshotManager:
    def __init__(self, *, work_root: Path, git: GitClient | None = None) -> None:
        self._work_root = work_root.resolve()
        self._git = git or GitClient()

    def prepare(
        self,
        *,
        policy: RepositoryPolicy,
        expected_commit_sha: str,
        expected_tree_sha: str,
    ) -> SnapshotEvidence:
        policy.validate_target()
        self._work_root.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="integration-", dir=self._work_root))
        repository = root / "repository"
        try:
            self._git.run(
                ("clone", "--no-checkout", "--", policy.remote_url, str(repository))
            )
            remote = self._git.run(
                ("remote", "get-url", "origin"), cwd=repository
            ).stdout.strip()
            if remote != policy.remote_url:
                raise SnapshotVerificationError("REMOTE_IDENTITY_MISMATCH")

            self._git.run(
                ("fetch", "--no-tags", "origin", expected_commit_sha),
                cwd=repository,
            )
            self._git.run(
                ("checkout", "--detach", expected_commit_sha), cwd=repository
            )
            commit = self._git.run(("rev-parse", "HEAD"), cwd=repository).stdout.strip()
            tree = self._git.run(
                ("rev-parse", "HEAD^{tree}"), cwd=repository
            ).stdout.strip()
            if commit != expected_commit_sha:
                raise SnapshotVerificationError("BASE_COMMIT_MISMATCH")
            if tree != expected_tree_sha:
                raise SnapshotVerificationError("BASE_TREE_MISMATCH")

            status = self._git.run(
                ("status", "--porcelain=v1", "--untracked-files=all"),
                cwd=repository,
            ).stdout
            if status:
                raise SnapshotVerificationError("DIRTY_WORKTREE")

            gitlinks = self._git.run(
                ("ls-files", "--stage"), cwd=repository
            ).stdout.splitlines()
            if any(line.startswith("160000 ") for line in gitlinks):
                raise SnapshotVerificationError("UNEXPECTED_SUBMODULE_STATE")

            config = self._git.run(
                ("config", "--local", "--list", "--show-origin"), cwd=repository
            ).stdout
            return SnapshotEvidence(
                path=repository,
                remote_url=remote,
                commit_sha=commit,
                tree_sha=tree,
                clean=True,
                submodules_verified=True,
                git_config_sha256=hashlib.sha256(config.encode()).hexdigest(),
            )
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def cleanup(self, snapshot: SnapshotEvidence) -> None:
        root = snapshot.path.parent.resolve()
        if root.parent != self._work_root or not root.name.startswith("integration-"):
            raise SnapshotVerificationError("Refusing unsafe snapshot cleanup")
        shutil.rmtree(root, ignore_errors=True)
