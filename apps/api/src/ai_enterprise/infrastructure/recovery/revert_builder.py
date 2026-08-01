from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.recovery.exceptions import RevertConflict, RevertFailed
from ai_enterprise.infrastructure.recovery.git_runner import IsolatedGitRunner


@dataclass(frozen=True, slots=True)
class PreparedRevert:
    integration_commit_sha: str
    changed_paths: tuple[str, ...]
    candidate_tree_sha: str


class RevertBuilder:
    def __init__(self, runner: IsolatedGitRunner | None = None) -> None:
        self._runner = runner or IsolatedGitRunner()

    def prepare(
        self,
        *,
        repository: Path,
        integration_commit_sha: str,
    ) -> PreparedRevert:
        self._require_clean(repository)
        result = self._runner.run(
            repository,
            "revert",
            "--no-commit",
            "--no-edit",
            integration_commit_sha,
        )
        if result.returncode != 0:
            conflicts = self._conflict_paths(repository)
            self._abort_and_verify_clean(repository)
            if conflicts:
                raise RevertConflict(
                    self._sanitize(result.stderr) or "The revert has conflicts.",
                    paths=conflicts,
                )
            raise RevertFailed(self._sanitize(result.stderr) or "Git revert failed.")

        changed_paths = self._changed_paths(repository)
        write_tree = self._runner.run(repository, "write-tree")
        if write_tree.returncode != 0:
            self._abort_and_verify_clean(repository)
            raise RevertFailed(self._sanitize(write_tree.stderr) or "Cannot calculate revert tree.")
        return PreparedRevert(
            integration_commit_sha=integration_commit_sha,
            changed_paths=changed_paths,
            candidate_tree_sha=write_tree.stdout.strip(),
        )

    def abort(self, repository: Path) -> None:
        self._abort_and_verify_clean(repository)

    def _require_clean(self, repository: Path) -> None:
        status = self._runner.run(repository, "status", "--porcelain=v1")
        if status.returncode != 0 or status.stdout.strip():
            raise RevertFailed("Recovery workspace must be clean before revert.")

    def _conflict_paths(self, repository: Path) -> tuple[str, ...]:
        result = self._runner.run(repository, "diff", "--name-only", "--diff-filter=U", "-z")
        if result.returncode != 0:
            return ()
        return tuple(sorted(path for path in result.stdout.split("\0") if path))

    def _changed_paths(self, repository: Path) -> tuple[str, ...]:
        result = self._runner.run(repository, "diff", "--cached", "--name-only", "-z")
        if result.returncode != 0:
            raise RevertFailed(self._sanitize(result.stderr) or "Cannot inspect revert paths.")
        return tuple(sorted(path for path in result.stdout.split("\0") if path))

    def _abort_and_verify_clean(self, repository: Path) -> None:
        abort = self._runner.run(repository, "revert", "--abort")
        if abort.returncode != 0:
            self._runner.run(repository, "reset", "--merge", "HEAD")
        status = self._runner.run(repository, "status", "--porcelain=v1")
        if status.returncode != 0 or status.stdout.strip():
            raise RevertFailed("Revert cleanup did not restore a clean workspace.")

    @staticmethod
    def _sanitize(value: str) -> str:
        return value.strip()[:2_000]

