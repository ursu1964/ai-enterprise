from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.execution.exceptions import ScopeViolationError
from ai_enterprise.domain.execution.policies import ExecutionScope


@dataclass(frozen=True, slots=True)
class ChangeStatistics:
    files: tuple[str, ...]
    insertions: int
    deletions: int

    @property
    def file_count(self) -> int:
        return len(self.files)


class ScopeValidator:
    def inspect(
        self,
        *,
        repository: Path,
        scope: ExecutionScope,
        maximum_changed_files: int,
    ) -> ChangeStatistics:
        files = self._changed_files(repository)

        self._validate_changed_symlinks(repository, files)
        self._validate_no_submodule_pointer_changes(repository)

        violations: list[str] = []

        for changed_file in files:
            try:
                allowed = scope.is_allowed(changed_file)
            except ValueError:
                allowed = False

            if not allowed:
                violations.append(changed_file)

        if len(files) > maximum_changed_files:
            raise ScopeViolationError(
                f"Changed {len(files)} files; maximum is "
                f"{maximum_changed_files}"
            )

        if violations:
            raise ScopeViolationError(
                "Files outside approved scope: " + ", ".join(violations)
            )

        insertions, deletions = self._line_statistics(repository)

        return ChangeStatistics(
            files=tuple(files),
            insertions=insertions,
            deletions=deletions,
        )

    @staticmethod
    def _changed_files(repository: Path) -> list[str]:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

        fields = result.stdout.split(b"\0")
        files: list[str] = []

        index = 0

        while index < len(fields):
            entry = fields[index]

            if not entry:
                break

            text = entry.decode("utf-8", errors="strict")
            status = text[:2]
            path = text[3:]

            if "R" in status or "C" in status:
                index += 1

                if index >= len(fields):
                    raise ScopeViolationError("Malformed Git rename record")

                source_path = fields[index].decode("utf-8", errors="strict")
                files.append(source_path)

            files.append(path)
            index += 1

        return sorted(set(files))

    @staticmethod
    def _validate_changed_symlinks(repository: Path, files: list[str]) -> None:
        root = repository.resolve()

        for relative_path in files:
            path = repository / relative_path

            if not path.is_symlink():
                continue

            target = path.resolve(strict=False)

            if target != root and root not in target.parents:
                raise ScopeViolationError(
                    f"Changed symlink escapes snapshot: {relative_path}"
                )

    @staticmethod
    def _validate_no_submodule_pointer_changes(repository: Path) -> None:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--raw",
                "--no-renames",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        for line in result.stdout.splitlines():
            metadata = line.split("\t", maxsplit=1)[0].split()

            modes = {value.lstrip(":") for value in metadata[:2]}

            if "160000" in modes:
                raise ScopeViolationError(
                    "Submodule pointer changes require explicit approval"
                )

    @staticmethod
    def _line_statistics(repository: Path) -> tuple[int, int]:
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "diff",
                "--numstat",
                "--no-renames",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        untracked = subprocess.run(
            [
                "git",
                "-C",
                str(repository),
                "ls-files",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )

        insertions = 0
        deletions = 0

        for line in tracked.stdout.splitlines():
            added, removed, _ = line.split("\t", maxsplit=2)

            if added.isdigit():
                insertions += int(added)

            if removed.isdigit():
                deletions += int(removed)

        for raw_path in untracked.stdout.split(b"\0"):
            if not raw_path:
                continue

            path = repository / raw_path.decode("utf-8")

            try:
                data = path.read_bytes()
            except OSError:
                continue

            if b"\0" not in data:
                insertions += len(data.splitlines())

        return insertions, deletions
