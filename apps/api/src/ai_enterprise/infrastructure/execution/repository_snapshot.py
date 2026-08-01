from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

from ai_enterprise.domain.execution.exceptions import (
    BaseCommitMismatchError,
    SnapshotCreationError,
)


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    path: Path
    base_commit: str
    snapshot_sha256: str


class RepositorySnapshotService:
    def __init__(
        self,
        *,
        source_repository: Path,
        snapshots_root: Path,
        runtime_uid: int = 10001,
        runtime_gid: int = 10001,
    ) -> None:
        self._source_repository = source_repository.resolve()
        self._snapshots_root = snapshots_root.resolve()
        self._runtime_uid = runtime_uid
        self._runtime_gid = runtime_gid

    def verify_commit(self, expected_commit: str) -> str:
        result = self._git(
            "-C",
            str(self._source_repository),
            "rev-parse",
            "--verify",
            f"{expected_commit}^{{commit}}",
        )

        resolved = result.stdout.strip()

        if resolved != expected_commit:
            raise BaseCommitMismatchError(
                f"Expected commit {expected_commit}, resolved {resolved}"
            )

        return resolved

    def create(
        self,
        *,
        execution_id: str,
        expected_commit: str,
    ) -> RepositorySnapshot:
        self.verify_commit(expected_commit)

        execution_root = self._snapshots_root / execution_id
        snapshot_path = execution_root / "repository"

        if execution_root.exists():
            shutil.rmtree(execution_root)

        execution_root.mkdir(parents=True, mode=0o700)

        archive_path = execution_root / "repository.tar"

        try:
            with archive_path.open("wb") as archive:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(self._source_repository),
                        "archive",
                        "--format=tar",
                        expected_commit,
                    ],
                    check=True,
                    stdout=archive,
                    stderr=subprocess.PIPE,
                    timeout=120,
                )

            snapshot_path.mkdir(mode=0o700)

            with tarfile.open(archive_path, mode="r") as archive:
                self._safe_extract(archive, snapshot_path)

            archive_path.unlink()

            self._initialize_snapshot_repository(
                snapshot_path=snapshot_path,
                expected_commit=expected_commit,
            )

            self._make_tree_writable(snapshot_path)

            return RepositorySnapshot(
                path=snapshot_path,
                base_commit=expected_commit,
                snapshot_sha256=self._hash_tree(snapshot_path),
            )
        except Exception as exc:
            shutil.rmtree(execution_root, ignore_errors=True)
            raise SnapshotCreationError(str(exc)) from exc

    def delete(self, execution_id: str) -> None:
        execution_root = self._snapshots_root / execution_id
        shutil.rmtree(execution_root, ignore_errors=True)

    def _initialize_snapshot_repository(
        self,
        *,
        snapshot_path: Path,
        expected_commit: str,
    ) -> None:
        self._git("-C", str(snapshot_path), "init", "--quiet")
        self._git(
            "-C",
            str(snapshot_path),
            "config",
            "user.name",
            "AI Enterprise Runtime",
        )
        self._git(
            "-C",
            str(snapshot_path),
            "config",
            "user.email",
            "runtime@localhost",
        )
        self._git("-C", str(snapshot_path), "add", "--all")
        self._git(
            "-C",
            str(snapshot_path),
            "commit",
            "--quiet",
            "--message",
            f"runtime-base:{expected_commit}",
        )

    def _make_tree_writable(self, root: Path) -> None:
        for path in root.rglob("*"):
            if path.is_symlink():
                continue

            mode = 0o700 if path.is_dir() else 0o600

            if path.is_file() and path.stat().st_mode & 0o111:
                mode = 0o700

            path.chmod(mode)
            os.chown(path, self._runtime_uid, self._runtime_gid)

        root.chmod(0o700)
        os.chown(root, self._runtime_uid, self._runtime_gid)

    @staticmethod
    def _safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
        root = destination.resolve()

        for member in archive.getmembers():
            target = (destination / member.name).resolve()

            if target != root and root not in target.parents:
                raise SnapshotCreationError(
                    f"Archive entry escapes snapshot: {member.name}"
                )

            if member.issym() or member.islnk():
                link_target = Path(member.linkname)

                if link_target.is_absolute() or ".." in link_target.parts:
                    raise SnapshotCreationError(
                        f"Unsafe archive link: {member.name}"
                    )

        archive.extractall(destination, filter="data")

    @staticmethod
    def _hash_tree(root: Path) -> str:
        digest = hashlib.sha256()

        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)

            if relative.parts and relative.parts[0] == ".git":
                continue

            digest.update(str(relative).encode("utf-8"))
            digest.update(b"\0")

            if path.is_file() and not path.is_symlink():
                with path.open("rb") as handle:
                    for block in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(block)

        return digest.hexdigest()

    @staticmethod
    def _git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
            env={
                **os.environ,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            },
        )
