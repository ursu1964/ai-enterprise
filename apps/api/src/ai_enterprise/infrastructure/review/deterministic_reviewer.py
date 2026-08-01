from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepositoryState:
    changed_files: tuple[str, ...]
    tree_hash: str
    diff_stat: str


class DeterministicReviewer:
    def inspect_repository(self, repository: Path) -> RepositoryState:
        changed_files = self._run(
            repository,
            "diff",
            "--cached",
            "--name-only",
            "-z",
        ).stdout.encode("utf-8").split(b"\0")

        normalized_files = tuple(
            sorted(
                value.decode("utf-8")
                for value in changed_files
                if value
            )
        )

        tree_hash = self._run(
            repository,
            "write-tree",
        ).stdout.strip()

        diff_stat = self._run(
            repository,
            "diff",
            "--cached",
            "--numstat",
            "--no-renames",
        ).stdout

        return RepositoryState(
            changed_files=normalized_files,
            tree_hash=tree_hash,
            diff_stat=diff_stat,
        )

    @staticmethod
    def _run(
        repository: Path,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
