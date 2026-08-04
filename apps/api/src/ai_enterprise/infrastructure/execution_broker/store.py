from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ai_enterprise.infrastructure.execution_broker.policy import extract_snapshot_archive


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    snapshot_ref: uuid.UUID
    archive_sha256: str
    tree_sha256: str
    manifest_sha256: str
    file_count: int
    expanded_bytes: int
    owner_worker_id: str
    created_at: datetime


class SnapshotStore:
    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise ValueError("broker snapshot root cannot be a symbolic link")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._root = root.resolve()
        self._objects = self._root / "objects"
        self._staging = self._root / ".staging"
        for directory in (self._objects, self._staging):
            if directory.is_symlink():
                raise ValueError("broker managed directories cannot be symbolic links")
            directory.mkdir(mode=0o700, exist_ok=True)
            directory.chmod(0o700)
        self._database = self._root / "registrations.sqlite3"
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS snapshot_registrations ("
                "snapshot_ref TEXT PRIMARY KEY, tree_sha256 TEXT NOT NULL, "
                "archive_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, "
                "file_count INTEGER NOT NULL, expanded_bytes INTEGER NOT NULL, "
                "owner_worker_id TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
        self._database.chmod(0o600)

    def register(self, encoded: bytes, *, owner_worker_id: str) -> StoredSnapshot:
        snapshot_ref = uuid.uuid4()
        staging = self._staging / f"{snapshot_ref}.partial"
        created_at = datetime.now(UTC)
        published = False
        try:
            staging.mkdir(mode=0o700)
            tree_root = staging / "tree"
            archive_sha256 = extract_snapshot_archive(encoded, tree_root)
            manifest, file_count, expanded_bytes = _canonical_manifest(tree_root)
            manifest_encoded = json.dumps(
                manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
            manifest_sha256 = hashlib.sha256(manifest_encoded).hexdigest()
            tree_sha256 = hashlib.sha256(b"tree-v1\0" + manifest_encoded).hexdigest()
            ready = {
                "schema_version": 1,
                "tree_sha256": tree_sha256,
                "manifest_sha256": manifest_sha256,
                "file_count": file_count,
                "expanded_bytes": expanded_bytes,
                "manifest": manifest,
            }
            _write_new_json(staging / "READY.json", ready)
            _fsync_tree(staging)
            _make_immutable(staging)
            _fsync_tree(staging)
            destination = self._objects / tree_sha256
            try:
                _rename_no_replace(staging, destination)
                published = True
                destination.chmod(0o500)
                _fsync_directory(destination)
                _fsync_directory(self._objects)
            except FileExistsError:
                _verify_ready_object(destination, tree_sha256, manifest_sha256)
                _remove_private_tree(staging)
            stored = StoredSnapshot(
                snapshot_ref=snapshot_ref,
                archive_sha256=archive_sha256,
                tree_sha256=tree_sha256,
                manifest_sha256=manifest_sha256,
                file_count=file_count,
                expanded_bytes=expanded_bytes,
                owner_worker_id=owner_worker_id,
                created_at=created_at,
            )
            self._insert_registration(stored)
            return stored
        except Exception:
            if staging.exists():
                _remove_private_tree(staging)
            if published:
                # Published content is immutable evidence. An unreferenced object is retained for
                # startup reconciliation rather than deleted after a registration failure.
                _fsync_directory(self._objects)
            raise

    def resolve(self, snapshot_ref: uuid.UUID, *, owner_worker_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT tree_sha256, manifest_sha256, owner_worker_id "
                "FROM snapshot_registrations "
                "WHERE snapshot_ref = ?",
                (str(snapshot_ref),),
            ).fetchone()
        if row is None or row[2] != owner_worker_id:
            raise KeyError("snapshot reference is unavailable")
        destination = self._objects / str(row[0])
        _verify_ready_object(destination, str(row[0]), str(row[1]))
        return destination / "tree"

    def _insert_registration(self, snapshot: StoredSnapshot) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO snapshot_registrations VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(snapshot.snapshot_ref),
                    snapshot.tree_sha256,
                    snapshot.archive_sha256,
                    snapshot.manifest_sha256,
                    snapshot.file_count,
                    snapshot.expanded_bytes,
                    snapshot.owner_worker_id,
                    snapshot.created_at.isoformat(),
                ),
            )
        _fsync_file(self._database)
        _fsync_directory(self._root)

    def _connect(self) -> sqlite3.Connection:
        descriptor = os.open(
            self._database,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            return sqlite3.connect(f"/proc/self/fd/{descriptor}")
        finally:
            os.close(descriptor)


def _canonical_manifest(root: Path) -> tuple[list[dict[str, Any]], int, int]:
    manifest: list[dict[str, Any]] = []
    file_count = 0
    expanded_bytes = 0
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("snapshot tree contains an unsupported entry")
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            manifest.append({"path": relative, "type": "directory", "mode": "0500"})
            continue
        data_sha256 = _hash_file(path)
        size = path.stat().st_size
        mode = "0500" if path.stat().st_mode & 0o111 else "0400"
        manifest.append(
            {
                "path": relative,
                "type": "file",
                "mode": mode,
                "size": size,
                "sha256": data_sha256,
            }
        )
        file_count += 1
        expanded_bytes += size
    return manifest, file_count, expanded_bytes


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())


def _make_immutable(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o500)
        elif path.is_file():
            path.chmod(0o500 if path.stat().st_mode & 0o111 else 0o400)
    # Keep the unpublished root owner-writable: Linux requires that permission when
    # moving a populated directory across parents. It is made read-only immediately
    # after the atomic publish and before a registration can expose the object.
    root.chmod(0o700)


def _verify_ready_object(
    destination: Path, tree_sha256: str, manifest_sha256: str | None
) -> None:
    if destination.is_symlink() or not destination.is_dir():
        raise ValueError("snapshot object is unavailable")
    ready_path = destination / "READY.json"
    if ready_path.is_symlink() or not ready_path.is_file():
        raise ValueError("snapshot object is incomplete")
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    if ready.get("tree_sha256") != tree_sha256:
        raise ValueError("snapshot tree identity mismatch")
    if manifest_sha256 is not None and ready.get("manifest_sha256") != manifest_sha256:
        raise ValueError("snapshot manifest identity mismatch")
    manifest, file_count, expanded_bytes = _canonical_manifest(destination / "tree")
    manifest_encoded = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    actual_manifest_sha256 = hashlib.sha256(manifest_encoded).hexdigest()
    actual_tree_sha256 = hashlib.sha256(b"tree-v1\0" + manifest_encoded).hexdigest()
    if (
        ready.get("schema_version") != 1
        or ready.get("manifest") != manifest
        or ready.get("file_count") != file_count
        or ready.get("expanded_bytes") != expanded_bytes
        or actual_manifest_sha256 != ready.get("manifest_sha256")
        or actual_tree_sha256 != tree_sha256
    ):
        raise ValueError("snapshot object content is corrupt")


def _fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_file():
            _fsync_file(path)
        elif path.is_dir():
            _fsync_directory(path)
    _fsync_directory(root)


def _fsync_file(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_private_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o700)
        elif path.is_file():
            path.chmod(0o600)
    root.chmod(0o700)
    shutil.rmtree(root)


def _rename_no_replace(source: Path, destination: Path) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOSYS, "atomic no-replace publication is unavailable")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(destination),
        1,
    )
    if result == 0:
        return
    error = ctypes.get_errno()
    if error == errno.EEXIST:
        raise FileExistsError(error, os.strerror(error), destination)
    raise OSError(error, os.strerror(error), destination)
