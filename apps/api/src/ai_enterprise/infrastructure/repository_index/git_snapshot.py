from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path


class RepositorySnapshotError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RepositorySnapshotResult:
    snapshot_path: Path
    repository_uri: str
    base_commit_sha: str
    tree_hash: str
    content_hash: str = ""


class GitSnapshotService:
    """Creates a detached, read-only archive without reading the host working tree."""

    def __init__(self, snapshots_root: Path) -> None:
        self._root = snapshots_root.resolve()

    def create_readonly_snapshot(
        self, *, repository_uri: str, base_commit_sha: str
    ) -> RepositorySnapshotResult:
        repository = self._local_repository(repository_uri)
        commit = self._git(repository, "rev-parse", "--verify", f"{base_commit_sha}^{{commit}}")
        if commit != base_commit_sha:
            raise RepositorySnapshotError("Commit must be supplied as its exact resolved SHA")
        tree_hash = self._git(repository, "rev-parse", f"{commit}^{{tree}}")
        destination = self._root / commit
        manifest = self._root / ".metadata" / f"{commit}.sha256"
        if destination.exists():
            if not manifest.is_file():
                raise RepositorySnapshotError("Repository snapshot metadata is missing")
            existing = RepositorySnapshotResult(
                destination, repository_uri, commit, tree_hash, manifest.read_text().strip()
            )
            self.verify(existing)
            return existing
        temporary = self._root / f".{commit}.creating"
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.mkdir(parents=True, mode=0o700)
        archive = temporary / "snapshot.tar"
        try:
            with archive.open("wb") as output:
                subprocess.run(
                    ["git", "-C", str(repository), "archive", "--format=tar", commit],
                    check=True,
                    stdout=output,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    env=self._git_env(),
                )
            content = temporary / "repository"
            content.mkdir()
            with tarfile.open(archive) as bundle:
                self._safe_extract(bundle, content)
            archive.unlink()
            content.rename(destination)
            temporary.rmdir()
            self._make_readonly(destination)
        except Exception as exc:
            shutil.rmtree(temporary, ignore_errors=True)
            raise RepositorySnapshotError(str(exc)) from exc
        content_hash = self.hash_snapshot(destination)
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(content_hash)
        result = RepositorySnapshotResult(
            destination, repository_uri, commit, tree_hash, content_hash
        )
        self.verify(result)
        return result

    def verify(self, snapshot: RepositorySnapshotResult) -> None:
        content_changed = snapshot.content_hash and (
            self.hash_snapshot(snapshot.snapshot_path) != snapshot.content_hash
        )
        if content_changed:
            raise RepositorySnapshotError("Repository snapshot content hash mismatch")
        repository = self._local_repository(snapshot.repository_uri)
        actual_tree = self._git(repository, "rev-parse", f"{snapshot.base_commit_sha}^{{tree}}")
        if actual_tree != snapshot.tree_hash:
            raise RepositorySnapshotError("Repository Git tree hash mismatch")

    @staticmethod
    def hash_snapshot(root: Path) -> str:
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode())
            digest.update(b"\0")
            if path.is_symlink():
                digest.update(os.readlink(path).encode())
            elif path.is_file():
                digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()

    @staticmethod
    def _local_repository(uri: str) -> Path:
        raw = uri.removeprefix("file://").removeprefix("local://")
        path = Path(raw).resolve()
        if not path.is_dir():
            raise RepositorySnapshotError("Repository URI is not a local directory")
        return path

    @staticmethod
    def _git(repository: Path, *args: str) -> str:
        try:
            return subprocess.run(
                ["git", "-C", str(repository), *args],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
                env=GitSnapshotService._git_env(),
            ).stdout.strip()
        except subprocess.SubprocessError as exc:
            raise RepositorySnapshotError("Unable to resolve immutable Git snapshot") from exc

    @staticmethod
    def _git_env() -> dict[str, str]:
        return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"}

    @staticmethod
    def _safe_extract(bundle: tarfile.TarFile, destination: Path) -> None:
        root = destination.resolve()
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != root and root not in target.parents:
                raise RepositorySnapshotError("Git archive entry escapes snapshot")
            if member.issym() or member.islnk():
                link = Path(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise RepositorySnapshotError("Git archive contains unsafe link")
        bundle.extractall(destination, filter="data")

    @staticmethod
    def _make_readonly(root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            if not path.is_symlink():
                path.chmod(0o500 if path.is_dir() else 0o400)
        root.chmod(0o500)
