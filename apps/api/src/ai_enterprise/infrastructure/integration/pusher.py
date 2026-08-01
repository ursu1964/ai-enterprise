from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .credentials import CredentialBroker
from .exceptions import IntegrationGitError, TargetBranchAdvancedError
from .git_client import GitClient
from .models import CandidateCommit, RepositoryPolicy


class RestrictedPusher:
    def __init__(self, *, credentials: CredentialBroker, git: GitClient | None = None) -> None:
        self._credentials = credentials
        self._git = git or GitClient()

    def push(
        self,
        *,
        repository: Path,
        policy: RepositoryPolicy,
        candidate: CandidateCommit,
        approved_base_commit: str,
    ) -> None:
        policy.validate_target()
        remote_url = self._git.run(
            ("remote", "get-url", "origin"), cwd=repository
        ).stdout.strip()
        if remote_url != policy.remote_url:
            raise IntegrationGitError("REMOTE_IDENTITY_MISMATCH")

        with self._credentials.acquire_push_credentials(policy.repository_id) as lease:
            remote_head = self._remote_head(
                repository, policy.target_branch, lease.environment
            )
            if remote_head != approved_base_commit:
                raise TargetBranchAdvancedError("TARGET_BRANCH_ADVANCED")
            result = self._git.run(
                (
                    "push",
                    "--porcelain",
                    "origin",
                    f"{candidate.commit_sha}:refs/heads/{policy.target_branch}",
                ),
                cwd=repository,
                extra_env=lease.environment,
                check=False,
            )
            if result.returncode != 0:
                raise IntegrationGitError("PUSH_FAILED")

    def _remote_head(
        self, repository: Path, branch: str, environment: Mapping[str, str]
    ) -> str | None:
        result = self._git.run(
            ("ls-remote", "--heads", "origin", f"refs/heads/{branch}"),
            cwd=repository,
            extra_env=environment,
        ).stdout.strip()
        if not result:
            return None
        fields = result.split()
        if len(fields) != 2 or fields[1] != f"refs/heads/{branch}":
            raise IntegrationGitError("MALFORMED_REMOTE_HEAD")
        return fields[0]
