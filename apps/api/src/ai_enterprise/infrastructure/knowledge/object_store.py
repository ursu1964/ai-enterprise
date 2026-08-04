from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoredObject:
    provider: str
    bucket: str
    object_key: str
    content_sha256: str
    size_bytes: int


class ObjectStore(Protocol):
    async def put(self, *, project_id: UUID, content: bytes) -> StoredObject: ...

    async def get(self, stored: StoredObject) -> bytes: ...


class LocalContentAddressedObjectStore:
    """Laptop adapter for the same immutable locator contract used by S3-compatible stores."""

    def __init__(self, root: Path, *, bucket: str = "aepm-sources") -> None:
        self.root = root.resolve()
        self.bucket = bucket

    async def put(self, *, project_id: UUID, content: bytes) -> StoredObject:
        digest = hashlib.sha256(content).hexdigest()
        object_key = f"{project_id}/{digest}"
        target = self._path(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError("OBJECT-STORE-HASH-COLLISION")
        else:
            target.write_bytes(content)
        return StoredObject("local", self.bucket, object_key, digest, len(content))

    async def get(self, stored: StoredObject) -> bytes:
        if stored.provider != "local" or stored.bucket != self.bucket:
            raise ValueError("OBJECT-STORE-LOCATOR-MISMATCH")
        content = self._path(stored.object_key).read_bytes()
        if hashlib.sha256(content).hexdigest() != stored.content_sha256:
            raise ValueError("OBJECT-STORE-CONTENT-HASH-MISMATCH")
        return content

    def _path(self, object_key: str) -> Path:
        target = (self.root / self.bucket / object_key).resolve()
        expected_root = (self.root / self.bucket).resolve()
        if not target.is_relative_to(expected_root):
            raise ValueError("OBJECT-STORE-KEY-OUTSIDE-BUCKET")
        return target
