from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
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


@dataclass(frozen=True, slots=True)
class SnapshotHandle:
    snapshot_ref: uuid.UUID
    tree_sha256: str
    root: Path


class SnapshotStoreCorruptionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    stale_staging_quarantined: int
    orphan_objects_quarantined: int
    referenced_objects_verified: int
    blocking_references: int


class SnapshotStore:
    def __init__(
        self, root: Path, *, checkpoint: Callable[[str], None] | None = None
    ) -> None:
        if root.is_symlink():
            raise ValueError("broker snapshot root cannot be a symbolic link")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._root = root.resolve()
        self._checkpoint = checkpoint or (lambda _name: None)
        self._objects = self._root / "objects"
        self._staging = self._root / ".staging"
        self._quarantine = self._root / ".quarantine"
        for directory in (self._objects, self._staging, self._quarantine):
            if directory.is_symlink():
                raise ValueError("broker managed directories cannot be symbolic links")
            directory.mkdir(mode=0o700, exist_ok=True)
            directory.chmod(0o700)
        self._database = self._root / "registrations.sqlite3"
        self._lock_path = self._root / ".store.lock"
        database_existed = self._database.exists()
        if not database_existed and (
            (self._root / "reconciliation.json").exists()
            or any(self._objects.iterdir())
            or any(self._staging.iterdir())
            or any(self._quarantine.iterdir())
        ):
            raise SnapshotStoreCorruptionError(
                "snapshot registration database is missing from an initialized store"
            )
        lock_descriptor = os.open(
            self._lock_path,
            os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        os.close(lock_descriptor)
        self._lock_path.chmod(0o600)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS snapshot_registrations ("
                "snapshot_ref TEXT PRIMARY KEY, tree_sha256 TEXT NOT NULL, "
                "archive_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, "
                "file_count INTEGER NOT NULL, expanded_bytes INTEGER NOT NULL, "
                "owner_worker_id TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
        self._database.chmod(0o600)
        with self._exclusive():
            self.reconciliation = self._reconcile()

    def register(self, encoded: bytes, *, owner_worker_id: str) -> StoredSnapshot:
        with self._exclusive():
            return self._register(encoded, owner_worker_id=owner_worker_id)

    def _register(self, encoded: bytes, *, owner_worker_id: str) -> StoredSnapshot:
        snapshot_ref = uuid.uuid4()
        staging = self._staging / f"{snapshot_ref}.partial"
        created_at = datetime.now(UTC)
        published = False
        try:
            staging.mkdir(mode=0o700)
            self._checkpoint("staging_created")
            tree_root = staging / "tree"
            archive_sha256 = extract_snapshot_archive(encoded, tree_root)
            self._checkpoint("archive_extracted")
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
            self._checkpoint("ready_written")
            _fsync_tree(staging)
            self._checkpoint("content_fsynced")
            _make_immutable(staging)
            self._checkpoint("sealed")
            _fsync_tree(staging)
            self._checkpoint("sealed_fsynced")
            destination = self._objects / tree_sha256
            try:
                _rename_no_replace(staging, destination)
                published = True
                self._checkpoint("object_renamed")
                destination.chmod(0o500)
                _fsync_directory(destination)
                _fsync_directory(self._objects)
                self._checkpoint("objects_parent_fsynced")
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
            self._checkpoint("after_registration_commit")
            return stored
        except Exception:
            if staging.exists():
                _remove_private_tree(staging)
            if published:
                # Published content is immutable evidence. An unreferenced object is retained for
                # startup reconciliation rather than deleted after a registration failure.
                _fsync_directory(self._objects)
            raise

    def resolve(self, snapshot_ref: uuid.UUID, *, owner_worker_id: str) -> SnapshotHandle:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT tree_sha256, manifest_sha256, owner_worker_id, file_count, "
                "expanded_bytes "
                "FROM snapshot_registrations "
                "WHERE snapshot_ref = ?",
                (str(snapshot_ref),),
            ).fetchone()
        if row is None or row[2] != owner_worker_id:
            raise KeyError("snapshot reference is unavailable")
        destination = self._objects / str(row[0])
        _verify_ready_object(
            destination, str(row[0]), str(row[1]), int(row[3]), int(row[4])
        )
        return SnapshotHandle(snapshot_ref, str(row[0]), destination / "tree")

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
            connection = sqlite3.connect(f"/proc/self/fd/{descriptor}")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        finally:
            os.close(descriptor)

    @contextmanager
    def _exclusive(self) -> Any:
        descriptor = os.open(
            self._lock_path,
            os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _reconcile(self) -> ReconciliationReport:
        stale_staging = 0
        orphan_objects = 0
        verified_objects = 0
        actions = self._recover_quarantine_intents()
        for entry in sorted(self._staging.iterdir(), key=lambda value: value.name):
            actions.append(self._quarantine_entry(entry, reason="interrupted-staging"))
            stale_staging += 1

        with self._connect() as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()
            if integrity != ("ok",):
                raise SnapshotStoreCorruptionError("snapshot registration database is corrupt")
            rows = connection.execute(
                "SELECT snapshot_ref, tree_sha256, archive_sha256, manifest_sha256, "
                "file_count, expanded_bytes, owner_worker_id, created_at "
                "FROM snapshot_registrations"
            ).fetchall()
        registrations: dict[str, set[tuple[str, int, int]]] = {}
        for row in rows:
            _validate_registration_row(row)
            (
                _snapshot_ref,
                tree_sha256,
                _archive_sha256,
                manifest_sha256,
                file_count,
                expanded_bytes,
                *_remainder,
            ) = row
            registrations.setdefault(str(tree_sha256), set()).add(
                (str(manifest_sha256), int(file_count), int(expanded_bytes))
            )

        corrupt_references: list[str] = []
        for tree_sha256, expected_values in registrations.items():
            if len(expected_values) != 1:
                corrupt_references.append(tree_sha256)
                continue
            destination = self._objects / tree_sha256
            try:
                manifest_sha256, file_count, expanded_bytes = next(iter(expected_values))
                _verify_ready_object(
                    destination,
                    tree_sha256,
                    manifest_sha256,
                    file_count,
                    expanded_bytes,
                )
            except (OSError, ValueError):
                if destination.exists() or destination.is_symlink():
                    actions.append(
                        self._quarantine_entry(
                            destination, reason="referenced-object-corrupt"
                        )
                    )
                corrupt_references.append(tree_sha256)
            else:
                verified_objects += 1

        for entry in sorted(self._objects.iterdir(), key=lambda value: value.name):
            if entry.name not in registrations:
                try:
                    _verify_ready_object(entry, entry.name, None)
                except (OSError, ValueError):
                    reason = "unreferenced-object-corrupt"
                else:
                    reason = "unreferenced-object-valid"
                actions.append(self._quarantine_entry(entry, reason=reason))
                orphan_objects += 1

        report = ReconciliationReport(
            stale_staging_quarantined=stale_staging,
            orphan_objects_quarantined=orphan_objects,
            referenced_objects_verified=verified_objects,
            blocking_references=len(corrupt_references),
        )
        _write_atomic_json(
            self._root / "reconciliation.json",
            {
                "schema_version": 1,
                "stale_staging_quarantined": report.stale_staging_quarantined,
                "orphan_objects_quarantined": report.orphan_objects_quarantined,
                "referenced_objects_verified": report.referenced_objects_verified,
                "blocking_references": report.blocking_references,
                "actions": sorted(
                    actions,
                    key=lambda action: (
                        str(action["reason"]), str(action["original_name"])
                    ),
                ),
            },
        )
        if corrupt_references:
            raise SnapshotStoreCorruptionError(
                "snapshot registrations reference missing or corrupt objects"
            )
        return report

    def _quarantine_entry(self, source: Path, *, reason: str) -> dict[str, str]:
        source_area = source.parent.name
        evidence_id = hashlib.sha256(
            f"{source_area}\0{source.name}\0{reason}".encode()
        ).hexdigest()[:32]
        payload_name = f"{evidence_id}-{source.name}"
        destination = self._quarantine / payload_name
        evidence_path = self._quarantine / f"{evidence_id}.json"
        evidence = {
            "schema_version": 1,
            "evidence_id": evidence_id,
            "reason": reason,
            "source_area": source_area,
            "original_name": source.name,
            "payload_name": payload_name,
            "state": "intent",
        }
        _write_atomic_json(evidence_path, evidence)
        if source.is_dir() and not source.is_symlink():
            source.chmod(0o700)
        _rename_no_replace(source, destination)
        evidence["state"] = "quarantined"
        _write_atomic_json(evidence_path, evidence)
        _fsync_directory(self._quarantine)
        _fsync_directory(source.parent)
        return {
            "evidence_id": evidence_id,
            "reason": reason,
            "original_name": source.name,
        }

    def _recover_quarantine_intents(self) -> list[dict[str, str]]:
        recovered: list[dict[str, str]] = []
        for evidence_path in sorted(self._quarantine.glob("*.json")):
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence.get("state") != "intent":
                continue
            payload = self._quarantine / str(evidence.get("payload_name", ""))
            source_area = str(evidence.get("source_area", ""))
            source_parent = self._staging if source_area == ".staging" else self._objects
            source = source_parent / str(evidence.get("original_name", ""))
            if not payload.exists() and not payload.is_symlink():
                if source.exists() or source.is_symlink():
                    continue
                raise SnapshotStoreCorruptionError(
                    "quarantine intent has neither source nor payload"
                )
            evidence["state"] = "quarantined"
            _write_atomic_json(evidence_path, evidence)
            recovered.append(
                {
                    "evidence_id": str(evidence["evidence_id"]),
                    "reason": str(evidence["reason"]),
                    "original_name": str(evidence["original_name"]),
                }
            )
        return recovered


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


def _validate_registration_row(row: tuple[Any, ...]) -> None:
    if len(row) != 8:
        raise SnapshotStoreCorruptionError("snapshot registration row is malformed")
    (
        snapshot_ref,
        tree_sha256,
        archive_sha256,
        manifest_sha256,
        file_count,
        expanded_bytes,
        owner,
        created,
    ) = row
    try:
        uuid.UUID(str(snapshot_ref))
        datetime.fromisoformat(str(created))
    except ValueError as exc:
        raise SnapshotStoreCorruptionError("snapshot registration row is malformed") from exc
    hashes = (str(tree_sha256), str(archive_sha256), str(manifest_sha256))
    if any(
        len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
        for value in hashes
    ):
        raise SnapshotStoreCorruptionError("snapshot registration row is malformed")
    if (
        not isinstance(file_count, int)
        or file_count < 0
        or not isinstance(expanded_bytes, int)
        or expanded_bytes < 0
        or not isinstance(owner, str)
        or not owner
        or len(owner) > 255
    ):
        raise SnapshotStoreCorruptionError("snapshot registration row is malformed")


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


def _write_atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4()}.partial")
    try:
        _write_new_json(temporary, value)
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


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
    destination: Path,
    tree_sha256: str,
    manifest_sha256: str | None,
    expected_file_count: int | None = None,
    expected_expanded_bytes: int | None = None,
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
        or (expected_file_count is not None and file_count != expected_file_count)
        or (expected_expanded_bytes is not None and expanded_bytes != expected_expanded_bytes)
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
