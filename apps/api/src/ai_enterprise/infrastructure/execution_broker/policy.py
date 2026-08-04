from __future__ import annotations

import hashlib
import io
import tarfile
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAXIMUM_ARCHIVE_BYTES = 64 * 1024 * 1024
MAXIMUM_ARCHIVE_FILES = 10_000


class BrokerPolicyError(ValueError):
    pass


class BrokerRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    idempotency_key: uuid.UUID
    workload_id: uuid.UUID
    kind: Literal["execution", "review"]
    image_policy_key: Literal["execution-agent", "review-agent"]
    resource_profile: Literal["small", "standard", "large"]
    snapshot_ref: uuid.UUID
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    correlation_id: uuid.UUID

    @model_validator(mode="after")
    def validate_kind_image_pair(self) -> BrokerRunRequest:
        expected = f"{self.kind}-agent"
        if self.image_policy_key != expected:
            raise ValueError("image policy does not match workload kind")
        return self


@dataclass(frozen=True, slots=True)
class ResourcePolicy:
    nano_cpus: int
    memory_bytes: int
    memory_swap_bytes: int
    pids_limit: int
    tmpfs_size_bytes: int
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class ResolvedBrokerPolicy:
    image_id: str
    runtime_uid: int
    runtime_gid: int
    resources: ResourcePolicy


class BrokerPolicy:
    _profiles = {
        "small": ResourcePolicy(500_000_000, 512 << 20, 512 << 20, 128, 64 << 20, 300),
        "standard": ResourcePolicy(1_000_000_000, 1 << 30, 1 << 30, 256, 128 << 20, 900),
        "large": ResourcePolicy(2_000_000_000, 2 << 30, 2 << 30, 384, 256 << 20, 1800),
    }

    def __init__(self, *, execution_image_id: str, review_image_id: str) -> None:
        self._images = {
            "execution-agent": self._require_image_id(execution_image_id),
            "review-agent": self._require_image_id(review_image_id),
        }

    def resolve(self, request: BrokerRunRequest) -> ResolvedBrokerPolicy:
        runtime_id = 10001 if request.kind == "execution" else 10002
        return ResolvedBrokerPolicy(
            image_id=self._images[request.image_policy_key],
            runtime_uid=runtime_id,
            runtime_gid=runtime_id,
            resources=self._profiles[request.resource_profile],
        )

    @staticmethod
    def _require_image_id(value: str) -> str:
        if not value.startswith("sha256:") or len(value) != 71:
            raise BrokerPolicyError("broker images must use immutable sha256 image IDs")
        try:
            int(value.removeprefix("sha256:"), 16)
        except ValueError as exc:
            raise BrokerPolicyError("broker image ID is not valid hexadecimal") from exc
        return value


def extract_snapshot_archive(
    encoded: bytes,
    destination: Path,
    *,
    maximum_bytes: int = MAXIMUM_ARCHIVE_BYTES,
    maximum_files: int = MAXIMUM_ARCHIVE_FILES,
) -> str:
    if len(encoded) > maximum_bytes:
        raise BrokerPolicyError("snapshot archive exceeds size limit")
    if destination.exists():
        raise BrokerPolicyError("snapshot destination must be a new private directory")
    destination.mkdir(parents=True, mode=0o700)
    destination_root = destination.resolve()
    total_size = 0
    file_count = 0
    portable_paths: set[str] = set()
    try:
        archive = tarfile.open(fileobj=io.BytesIO(encoded), mode="r:gz")
    except tarfile.TarError as exc:
        raise BrokerPolicyError("snapshot archive is invalid") from exc
    with archive:
        for member in archive.getmembers():
            file_count += 1
            if file_count > maximum_files:
                raise BrokerPolicyError("snapshot archive contains too many entries")
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts:
                raise BrokerPolicyError("snapshot archive contains an unsafe path")
            if (
                "\\" in member.name
                or unicodedata.normalize("NFC", member.name) != member.name
                or any(ord(character) < 32 or ord(character) == 127 for character in member.name)
            ):
                raise BrokerPolicyError("snapshot archive path is not portable")
            portable_key = member.name.casefold()
            if portable_key in portable_paths:
                raise BrokerPolicyError("snapshot archive contains a path collision")
            portable_paths.add(portable_key)
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise BrokerPolicyError("snapshot archive contains a forbidden entry type")
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination_root):
                raise BrokerPolicyError("snapshot archive escapes its assigned root")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True, mode=0o700)
                continue
            if not member.isfile():
                raise BrokerPolicyError("snapshot archive entry type is unsupported")
            total_size += member.size
            if total_size > maximum_bytes:
                raise BrokerPolicyError("expanded snapshot exceeds size limit")
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            source = archive.extractfile(member)
            if source is None:
                raise BrokerPolicyError("snapshot archive file is unreadable")
            with target.open("xb") as handle:
                remaining = member.size
                while remaining:
                    chunk = source.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        raise BrokerPolicyError("snapshot archive file is truncated")
                    handle.write(chunk)
                    remaining -= len(chunk)
            target.chmod(0o700 if member.mode & 0o111 else 0o600)
    return hashlib.sha256(encoded).hexdigest()
