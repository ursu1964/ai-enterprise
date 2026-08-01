from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .exceptions import CommitVerificationError
from .git_client import GitClient
from .models import CandidateCommit, RepositoryPolicy


class DeterministicCommitCreator:
    def __init__(self, *, git: GitClient | None = None) -> None:
        self._git = git or GitClient()

    def create(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        tree_sha: str,
        parent_sha: str,
        message: str,
        timestamp: datetime,
    ) -> CandidateCommit:
        if timestamp.tzinfo is None:
            raise ValueError("Commit timestamp must be timezone-aware")
        if not message.endswith("\n"):
            message += "\n"
        date = timestamp.isoformat()
        identity = f"{policy.integration_name} <{policy.integration_email}>"
        environment = {
            "GIT_AUTHOR_NAME": policy.integration_name,
            "GIT_AUTHOR_EMAIL": policy.integration_email,
            "GIT_COMMITTER_NAME": policy.integration_name,
            "GIT_COMMITTER_EMAIL": policy.integration_email,
            "GIT_AUTHOR_DATE": date,
            "GIT_COMMITTER_DATE": date,
        }
        commit = self._git.run(
            ("commit-tree", tree_sha, "-p", parent_sha),
            cwd=repository,
            extra_env=environment,
            input_bytes=message.encode("utf-8"),
        ).stdout.strip()
        self._git.run(("update-ref", "HEAD", commit, parent_sha), cwd=repository)
        self.verify(
            repository=repository,
            commit_sha=commit,
            tree_sha=tree_sha,
            parent_sha=parent_sha,
            message=message,
            identity=identity,
        )
        return CandidateCommit(
            commit_sha=commit,
            tree_sha=tree_sha,
            parent_sha=parent_sha,
            message=message,
            author_identity=identity,
            committer_identity=identity,
        )

    def verify(
        self,
        *,
        repository: Path,
        commit_sha: str,
        tree_sha: str,
        parent_sha: str,
        message: str,
        identity: str,
    ) -> None:
        actual_tree = self._git.run(
            ("show", "-s", "--format=%T", commit_sha), cwd=repository
        ).stdout.strip()
        parents = self._git.run(
            ("show", "-s", "--format=%P", commit_sha), cwd=repository
        ).stdout.strip().split()
        actual_message = self._git.run(
            ("show", "-s", "--format=%B", commit_sha), cwd=repository
        ).stdout
        author = self._git.run(
            ("show", "-s", "--format=%an <%ae>", commit_sha), cwd=repository
        ).stdout.strip()
        committer = self._git.run(
            ("show", "-s", "--format=%cn <%ce>", commit_sha), cwd=repository
        ).stdout.strip()
        if actual_tree != tree_sha:
            raise CommitVerificationError("COMMIT_TREE_MISMATCH")
        if parents != [parent_sha]:
            raise CommitVerificationError("COMMIT_PARENT_MISMATCH")
        if actual_message.rstrip("\n") != message.rstrip("\n"):
            raise CommitVerificationError("COMMIT_MESSAGE_MISMATCH")
        if author != identity or committer != identity:
            raise CommitVerificationError("COMMIT_IDENTITY_MISMATCH")
