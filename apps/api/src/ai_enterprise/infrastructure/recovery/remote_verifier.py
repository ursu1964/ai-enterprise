from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.recovery.entities import RemoteState
from ai_enterprise.domain.recovery.exceptions import RecoveryRemoteVerificationFailed
from ai_enterprise.infrastructure.recovery.git_runner import IsolatedGitRunner


@dataclass(frozen=True, slots=True)
class VerifiedRecoveryCommit:
    commit_sha: str
    tree_sha: str
    parent_sha: str


class RecoveryRepositoryVerifier:
    def __init__(self, runner: IsolatedGitRunner | None = None) -> None:
        self._runner = runner or IsolatedGitRunner()

    def inspect_fetched_remote(
        self,
        *,
        repository: Path,
        remote_name: str,
        target_branch: str,
        integration_commit_sha: str,
    ) -> RemoteState:
        remote_ref = self._remote_ref(remote_name, target_branch)
        head = self._required_output(repository, "rev-parse", "--verify", remote_ref)
        tree = self._required_output(repository, "rev-parse", f"{head}^{{tree}}")
        ancestor = self._runner.run(
            repository, "merge-base", "--is-ancestor", integration_commit_sha, head
        )
        if ancestor.returncode not in (0, 1):
            raise RecoveryRemoteVerificationFailed("Cannot verify integration ancestry.")
        return RemoteState(head, tree, ancestor.returncode == 0)

    def verify_recovery_result(
        self,
        *,
        repository: Path,
        remote_name: str,
        target_branch: str,
        expected_commit_sha: str,
        expected_tree_sha: str,
        expected_parent_sha: str,
        reverted_integration_commit_sha: str,
    ) -> VerifiedRecoveryCommit:
        state = self.inspect_fetched_remote(
            repository=repository,
            remote_name=remote_name,
            target_branch=target_branch,
            integration_commit_sha=reverted_integration_commit_sha,
        )
        parent = self._required_output(repository, "rev-parse", f"{state.head_sha}^")
        if (
            state.head_sha != expected_commit_sha
            or state.head_tree_sha != expected_tree_sha
            or parent != expected_parent_sha
            or not state.integration_commit_is_ancestor
        ):
            raise RecoveryRemoteVerificationFailed(
                "Remote recovery commit, tree, parent, or ancestry does not match approval."
            )
        return VerifiedRecoveryCommit(state.head_sha, state.head_tree_sha, parent)

    @staticmethod
    def _remote_ref(remote_name: str, target_branch: str) -> str:
        if not remote_name or not target_branch or any(
            token in remote_name + target_branch for token in ("..", " ", "~", "^")
        ):
            raise RecoveryRemoteVerificationFailed("Unsafe remote or branch name.")
        return f"refs/remotes/{remote_name}/{target_branch}"

    def _required_output(self, repository: Path, *arguments: str) -> str:
        result = self._runner.run(repository, *arguments)
        if result.returncode != 0 or not result.stdout.strip():
            raise RecoveryRemoteVerificationFailed("Git verification command failed.")
        return result.stdout.strip()
