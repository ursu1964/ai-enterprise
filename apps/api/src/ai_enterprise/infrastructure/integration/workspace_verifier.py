from __future__ import annotations

from pathlib import Path, PurePosixPath

from ai_enterprise.domain.execution.policies import ExecutionScope

from .exceptions import WorkspaceVerificationError
from .git_client import GitClient
from .models import WorkspaceEvidence


class WorkspaceVerifier:
    def __init__(self, *, git: GitClient | None = None) -> None:
        self._git = git or GitClient()

    def verify(
        self,
        *,
        repository: Path,
        scope: ExecutionScope,
        expected_paths: tuple[str, ...] | None = None,
    ) -> WorkspaceEvidence:
        records = self._git.run(
            ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
            cwd=repository,
        ).stdout.encode("utf-8", errors="surrogateescape").split(b"\0")
        changed: set[str] = set()
        index = 0
        while index < len(records) and records[index]:
            record = records[index]
            if len(record) < 4:
                raise WorkspaceVerificationError("MALFORMED_GIT_STATUS")
            status = record[:2].decode("ascii", errors="strict")
            path = record[3:].decode("utf-8", errors="strict")
            changed.add(path)
            if "R" in status or "C" in status:
                index += 1
                if index >= len(records) or not records[index]:
                    raise WorkspaceVerificationError("MALFORMED_GIT_STATUS")
                changed.add(records[index].decode("utf-8", errors="strict"))
            index += 1

        for value in changed:
            normalized_path = PurePosixPath(value)
            if normalized_path.is_absolute() or ".." in normalized_path.parts:
                raise WorkspaceVerificationError("PATH_ESCAPE_DETECTED")
            if normalized_path.parts and normalized_path.parts[0] == ".git":
                raise WorkspaceVerificationError("FORBIDDEN_GIT_METADATA")
            try:
                allowed = scope.is_allowed(value)
            except ValueError:
                allowed = False
            if not allowed:
                raise WorkspaceVerificationError(f"PATCH_SCOPE_VIOLATION: {value}")
            disk_path = repository / value
            if disk_path.is_symlink():
                target = disk_path.resolve(strict=False)
                root = repository.resolve()
                if target != root and root not in target.parents:
                    raise WorkspaceVerificationError("SYMLINK_POLICY_VIOLATION")

        raw = self._git.run(("diff", "--cached", "--raw", "HEAD"), cwd=repository).stdout
        if any(" 160000 " in f" {line.split(chr(9), 1)[0]} " for line in raw.splitlines()):
            raise WorkspaceVerificationError("SUBMODULE_POLICY_VIOLATION")

        normalized = tuple(sorted(changed))
        if expected_paths is not None and normalized != tuple(sorted(expected_paths)):
            raise WorkspaceVerificationError("UNEXPECTED_FILESYSTEM_CHANGE")
        if not normalized:
            raise WorkspaceVerificationError("EMPTY_PATCH")

        tree = self._git.run(("write-tree",), cwd=repository).stdout.strip()
        return WorkspaceEvidence(changed_paths=normalized, tree_sha=tree)
