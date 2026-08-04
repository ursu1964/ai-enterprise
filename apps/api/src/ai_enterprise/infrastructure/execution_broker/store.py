from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_enterprise.infrastructure.execution_broker.policy import extract_snapshot_archive


@dataclass(frozen=True, slots=True)
class StoredSnapshot:
    snapshot_ref: uuid.UUID
    archive_sha256: str
    owner_worker_id: str
    created_at: datetime


class SnapshotStore:
    def __init__(self, root: Path) -> None:
        if root.is_symlink():
            raise ValueError("broker snapshot root cannot be a symbolic link")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        self._root = root.resolve()

    def register(self, encoded: bytes, *, owner_worker_id: str) -> StoredSnapshot:
        snapshot_ref = uuid.uuid4()
        staging = self._root / f".staging-{snapshot_ref}"
        destination = self._root / str(snapshot_ref)
        created_at = datetime.now(UTC)
        try:
            staging.mkdir(mode=0o700)
            archive_sha256 = extract_snapshot_archive(encoded, staging / "snapshot")
            metadata = {
                "schema_version": 1,
                "snapshot_ref": str(snapshot_ref),
                "archive_sha256": archive_sha256,
                "owner_worker_id": owner_worker_id,
                "created_at": created_at.isoformat(),
            }
            metadata_path = staging / "metadata.json"
            descriptor = os.open(
                metadata_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(metadata, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            staging.rename(destination)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return StoredSnapshot(
            snapshot_ref=snapshot_ref,
            archive_sha256=archive_sha256,
            owner_worker_id=owner_worker_id,
            created_at=created_at,
        )
