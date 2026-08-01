from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.hashing import hash_text


class RepositoryInspectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositorySnapshot:
    root: Path
    commit_sha: str
    branch: str
    is_clean: bool
    tracked_files: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryFingerprint:
    head_sha: str
    tree_sha: str
    status_sha256: str
    diff_sha256: str


class GitRepositoryInspector:
    def __init__(
        self,
        *,
        allowed_root: Path,
    ) -> None:
        self._allowed_root = allowed_root.resolve()

    async def inspect(
        self,
        repository_path: str,
    ) -> RepositorySnapshot:
        root = Path(repository_path).expanduser().resolve()

        self._assert_allowed(root)

        commit_sha = await self._git(
            root,
            "rev-parse",
            "HEAD",
        )

        branch = await self._git(
            root,
            "branch",
            "--show-current",
        )

        status = await self._git(
            root,
            "status",
            "--porcelain",
        )

        file_output = await self._git(
            root,
            "ls-files",
        )

        tracked_files = tuple(line.strip() for line in file_output.splitlines() if line.strip())

        return RepositorySnapshot(
            root=root,
            commit_sha=commit_sha.strip(),
            branch=branch.strip(),
            is_clean=not bool(status.strip()),
            tracked_files=tracked_files,
        )

    async def fingerprint(
        self,
        repository_path: str,
    ) -> RepositoryFingerprint:
        root = Path(repository_path).expanduser().resolve()

        self._assert_allowed(root)

        head_sha = (await self._git(root, "rev-parse", "HEAD")).strip()
        tree_sha = (await self._git(root, "rev-parse", "HEAD^{tree}")).strip()

        status = await self._git(
            root,
            "status",
            "--porcelain=v1",
        )

        diff = await self._git(
            root,
            "diff",
            "--binary",
            "HEAD",
        )

        return RepositoryFingerprint(
            head_sha=head_sha,
            tree_sha=tree_sha,
            status_sha256=hash_text(status),
            diff_sha256=hash_text(diff),
        )

    def _assert_allowed(self, root: Path) -> None:
        try:
            root.relative_to(self._allowed_root)
        except ValueError as exc:
            raise RepositoryInspectionError(f"Repository is outside allowed root: {root}") from exc

        if not root.is_dir():
            raise RepositoryInspectionError(f"Repository directory does not exist: {root}")

        if not (root / ".git").exists():
            raise RepositoryInspectionError(f"Path is not a Git repository: {root}")

    @staticmethod
    async def _git(
        root: Path,
        *arguments: str,
    ) -> str:
        process = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(root),
            *arguments,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RepositoryInspectionError(stderr.decode("utf-8", errors="replace").strip())

        return stdout.decode("utf-8", errors="replace")
