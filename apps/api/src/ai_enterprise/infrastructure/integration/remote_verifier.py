from __future__ import annotations

from pathlib import Path

from .exceptions import RemoteVerificationError
from .git_client import GitClient
from .models import CandidateCommit, RemoteEvidence, RepositoryPolicy


class RemoteVerifier:
    def __init__(self, *, git: GitClient | None = None) -> None:
        self._git = git or GitClient()

    def verify(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        candidate: CandidateCommit,
    ) -> RemoteEvidence:
        ref = f"refs/heads/{policy.target_branch}"
        result = self._git.run(
            ("ls-remote", "--heads", "origin", ref), cwd=repository
        ).stdout.strip().split()
        if len(result) != 2 or result[0] != candidate.commit_sha or result[1] != ref:
            raise RemoteVerificationError("REMOTE_COMMIT_MISMATCH")
        verification_ref = f"refs/ai-enterprise/verify/{candidate.commit_sha}"
        self._git.run(
            ("fetch", "--no-tags", "origin", f"{ref}:{verification_ref}"),
            cwd=repository,
        )
        tree = self._git.run(
            ("show", "-s", "--format=%T", verification_ref), cwd=repository
        ).stdout.strip()
        parents = self._git.run(
            ("show", "-s", "--format=%P", verification_ref), cwd=repository
        ).stdout.strip().split()
        if tree != candidate.tree_sha:
            raise RemoteVerificationError("REMOTE_TREE_MISMATCH")
        if parents != [candidate.parent_sha]:
            raise RemoteVerificationError("REMOTE_PARENT_MISMATCH")
        return RemoteEvidence(
            branch=policy.target_branch,
            commit_sha=candidate.commit_sha,
            tree_sha=tree,
            parent_sha=parents[0],
        )
