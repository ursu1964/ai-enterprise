from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from ai_enterprise.domain.resilience.entities import BackupManifest, RestoreVerification
from ai_enterprise.domain.resilience.enums import BackupStatus, RestoreStatus
from ai_enterprise.infrastructure.security.local_activation import (
    LocalActivationSecurityError,
    require_bounded_bare_remote,
    require_confined_backup_path,
)


class LocalProviderError(RuntimeError):
    pass


def _require_private_file(path: Path) -> bytes:
    if path.is_symlink():
        raise LocalProviderError("Sensitive local file cannot be a symlink")
    resolved = path.resolve(strict=True)
    mode = resolved.stat().st_mode & 0o777
    if mode & 0o077:
        raise LocalProviderError(
            f"Sensitive local file must not be group/world accessible: {mode:o}"
        )
    data = resolved.read_bytes()
    if not data:
        raise LocalProviderError("Sensitive local file is empty")
    return data


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(slots=True)
class LocalBackupCatalog:
    paths: dict[uuid.UUID, Path] = field(default_factory=dict)


class LocalDatabaseBackupProvider:
    """Development-only copy of a configured SQLite/database snapshot file."""

    def __init__(self, source: Path, backup_root: Path, catalog: LocalBackupCatalog) -> None:
        self._source = source
        self._root = backup_root
        self._catalog = catalog

    async def create_manifest(self) -> BackupManifest:
        source = self._source.resolve(strict=True)
        if not source.is_file():
            raise LocalProviderError("Configured local database source is not a file")
        backup_id = uuid.uuid4()
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            destination = require_confined_backup_path(
                candidate=self._root / f"database-{backup_id}.snapshot",
                allowed_root=self._root,
            )
        except LocalActivationSecurityError as exc:
            raise LocalProviderError(str(exc)) from exc
        with source.open("rb") as reader, destination.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
            writer.flush()
            os.fsync(writer.fileno())
        digest = _hash_file(destination)
        self._catalog.paths[backup_id] = destination
        return BackupManifest(
            backup_id,
            "database_file",
            digest,
            1,
            destination.stat().st_size,
            "local-development-none",
            "local-file-v1",
            digest,
            (str(destination),),
            BackupStatus.CREATED,
        )


class LocalArtifactBackupProvider:
    def __init__(self, source: Path, backup_root: Path, catalog: LocalBackupCatalog) -> None:
        self._source = source
        self._root = backup_root
        self._catalog = catalog

    async def create_manifest(self) -> BackupManifest:
        source = self._source.resolve(strict=True)
        if not source.is_dir():
            raise LocalProviderError("Artifact source is not a directory")
        backup_id = uuid.uuid4()
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            destination = require_confined_backup_path(
                candidate=self._root / f"artifacts-{backup_id}.tar",
                allowed_root=self._root,
            )
        except LocalActivationSecurityError as exc:
            raise LocalProviderError(str(exc)) from exc
        with tarfile.open(destination, "x") as archive:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise LocalProviderError("Symlinks are prohibited in local artifact backup")
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(source), recursive=False)
        files = tuple(path for path in source.rglob("*") if path.is_file())
        digest = _hash_file(destination)
        self._catalog.paths[backup_id] = destination
        return BackupManifest(
            backup_id,
            "artifact_tar",
            digest,
            len(files),
            destination.stat().st_size,
            "local-development-none",
            "tar-v1",
            digest,
            (str(destination),),
            BackupStatus.CREATED,
        )


class LocalIsolatedRestoreVerifier:
    production_credentials_disabled = True
    external_dispatch_blocked = True

    def __init__(self, catalog: LocalBackupCatalog, restore_root: Path) -> None:
        self._catalog = catalog
        self._root = restore_root

    async def restore_and_verify(self, backup: BackupManifest) -> RestoreVerification:
        source = self._catalog.paths.get(backup.id)
        if source is None or not source.is_file():
            raise LocalProviderError("Backup object is unavailable")
        actual = _hash_file(source)
        if not hmac.compare_digest(actual, backup.content_hash):
            raise LocalProviderError("Backup content hash mismatch")
        self._root.mkdir(parents=True, exist_ok=True)
        destination = Path(tempfile.mkdtemp(prefix="restore-", dir=self._root))
        try:
            if backup.backup_type == "artifact_tar":
                with tarfile.open(source, "r") as archive:
                    archive.extractall(destination, filter="data")
            else:
                shutil.copy2(source, destination / "database.snapshot")
            checks = {
                name: False
                for name in (
                    "schema",
                    "references",
                    "artifacts",
                    "audit_chain",
                    "git_reachability",
                    "jobs",
                )
            }
            if backup.backup_type == "artifact_tar":
                checks["artifacts"] = True
            else:
                database_path = destination / "database.snapshot"
                connection: sqlite3.Connection | None = None
                try:
                    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
                    integrity = connection.execute("PRAGMA integrity_check").fetchone()
                    foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
                    tables = {
                        row[0]
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    checks["schema"] = bool(tables) and integrity == ("ok",)
                    checks["references"] = not foreign_keys
                    checks["jobs"] = "jobs" in tables
                    checks["audit_chain"] = "audit_events" in tables
                except sqlite3.DatabaseError:
                    pass
                finally:
                    if connection is not None:
                        connection.close()
            status = RestoreStatus.PASSED if all(checks.values()) else RestoreStatus.FAILED
            return RestoreVerification(uuid.uuid4(), backup.id, status, True, True, True, checks)
        finally:
            shutil.rmtree(destination, ignore_errors=True)


class LocalBareGitMirror:
    def __init__(self, remote: str, mirror: Path, allowed_root: Path | None = None) -> None:
        self._remote = remote
        self._mirror = mirror
        self._allowed_root = allowed_root or mirror.parent

    async def synchronize(self) -> str:
        try:
            remote_path = Path(unquote(urlsplit(self._remote).path))
            require_bounded_bare_remote(
                remote_url=self._remote,
                allowed_root=remote_path.parent,
            )
            mirror = require_confined_backup_path(
                candidate=self._mirror,
                allowed_root=self._allowed_root,
            )
        except (LocalActivationSecurityError, OSError) as exc:
            raise LocalProviderError(str(exc)) from exc
        if mirror.exists():
            result = subprocess.run(
                ["git", "--git-dir", str(mirror), "remote", "update", "--prune"],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                },
            )
        else:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                ["git", "clone", "--mirror", "--", self._remote, str(mirror)],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_TERMINAL_PROMPT": "0",
                },
            )
        if result.returncode:
            raise LocalProviderError("Local Git mirror synchronization failed")
        return hashlib.sha256(result.stdout.encode()).hexdigest()

    async def verify_reachability(self, commit_shas: tuple[str, ...]) -> dict[str, bool]:
        if not self._mirror.is_dir():
            raise LocalProviderError("Local Git mirror does not exist")
        return {
            value: subprocess.run(
                ["git", "--git-dir", str(self._mirror), "cat-file", "-e", f"{value}^{{commit}}"],
                check=False,
                capture_output=True,
                timeout=30,
            ).returncode
            == 0
            for value in commit_shas
        }


class FileRegionWitness:
    def __init__(self, state_file: Path) -> None:
        self._path = state_file

    async def acquire_fencing_token(self, resource_id: uuid.UUID, region: str) -> tuple[int, str]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.seek(0)
            state = json.loads(handle.read() or "{}")
            key = str(resource_id)
            token = int(state.get(key, {}).get("token", 0)) + 1
            state[key] = {"token": token, "region": region}
            encoded = json.dumps(state, sort_keys=True, separators=(",", ":"))
            handle.seek(0)
            handle.truncate()
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
            evidence = hashlib.sha256(f"{key}:{region}:{token}".encode()).hexdigest()
            return token, evidence


class LocalOllamaGateway:
    def __init__(self, base_url: str, models: dict[uuid.UUID, str]) -> None:
        self._base_url = base_url.rstrip("/")
        self._models = models

    async def generate(self, model_id: uuid.UUID, request: dict[str, object]) -> dict[str, object]:
        model = self._models.get(model_id)
        prompt = request.get("prompt")
        if model is None or not isinstance(prompt, str) or not prompt:
            raise LocalProviderError("Approved local model mapping and prompt are required")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self._base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
        response.raise_for_status()
        data = response.json()
        output = str(data.get("response", ""))
        evidence = hashlib.sha256(
            json.dumps(
                {
                    "model": model,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "response_sha256": hashlib.sha256(output.encode()).hexdigest(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return {
            "response": output,
            "model": model,
            "provider": "local-ollama",
            "evidence_sha256": evidence,
        }


class FileHmacSigningProvider:
    def __init__(self, key_path: Path) -> None:
        self._key_path = key_path
        self._key = _require_private_file(key_path)
        self.key_id = f"local-hmac:{hashlib.sha256(self._key).hexdigest()[:16]}"

    async def sign(self, provider_reference: str, content_hash: str) -> tuple[bytes, str]:
        if provider_reference != self.key_id:
            raise LocalProviderError("Signing provider reference mismatch")
        signature = hmac.new(self._key, content_hash.encode(), hashlib.sha256).digest()
        return signature, self.key_id

    def sign_digest(self, digest: bytes) -> str:
        return hmac.new(self._key, digest, hashlib.sha256).hexdigest()

    def verify_digest(self, digest: bytes, signature: str) -> bool:
        return hmac.compare_digest(self.sign_digest(digest), signature)


class FoundationFileHmacSigner:
    def __init__(self, provider: FileHmacSigningProvider) -> None:
        self._provider = provider

    @property
    def key_id(self) -> str:
        return self._provider.key_id

    def sign(self, digest: bytes) -> str:
        return self._provider.sign_digest(digest)

    def verify(self, digest: bytes, signature: str) -> bool:
        return self._provider.verify_digest(digest, signature)


class LocalTrustedIdentityProvider:
    def __init__(self, allowlist_file: Path) -> None:
        raw = _require_private_file(allowlist_file).decode("utf-8")
        self._subjects = frozenset(line.strip() for line in raw.splitlines() if line.strip())

    async def strongly_authenticate(self, principal_id: str) -> bool:
        return principal_id in self._subjects


class LocalVendorExportProvider:
    def __init__(self, source: Path, export_root: Path) -> None:
        self._source = source
        self._root = export_root

    async def export(self, plan_id: uuid.UUID) -> tuple[str, str]:
        source = self._source.resolve(strict=True)
        if not source.is_dir():
            raise LocalProviderError("Vendor export source must be a directory")
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            destination = require_confined_backup_path(
                candidate=self._root / f"vendor-export-{plan_id}.tar",
                allowed_root=self._root,
            )
        except LocalActivationSecurityError as exc:
            raise LocalProviderError(str(exc)) from exc
        with tarfile.open(destination, "x") as archive:
            for path in sorted(source.rglob("*")):
                if path.is_symlink():
                    raise LocalProviderError("Vendor export refuses symlinks")
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(source), recursive=False)
        return str(destination), _hash_file(destination)


class LocalArchiveVerifier:
    def __init__(self, allowed_root: Path) -> None:
        self._root = allowed_root.resolve()

    async def verify(self, archive_location: str, checkpoint_hash: str) -> tuple[bool, str]:
        path = Path(archive_location).resolve(strict=True)
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise LocalProviderError("Archive is outside the configured local root") from exc
        actual = _hash_file(path)
        return hmac.compare_digest(actual, checkpoint_hash), actual


class SafeNoopChaosProvider:
    def __init__(self, approved_experiments: frozenset[uuid.UUID]) -> None:
        self._approved = approved_experiments

    async def execute(self, experiment_id: uuid.UUID) -> tuple[str, str]:
        if experiment_id not in self._approved:
            raise LocalProviderError("Experiment is not explicitly approved for safe no-op")
        evidence = json.dumps(
            {"experiment_id": str(experiment_id), "action": "noop", "bounded": True},
            sort_keys=True,
        )
        return "passed", hashlib.sha256(evidence.encode()).hexdigest()
