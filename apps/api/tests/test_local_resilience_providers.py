from __future__ import annotations

import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest

from ai_enterprise.config import Settings
from ai_enterprise.infrastructure.resilience.local_providers import (
    FileHmacSigningProvider,
    FileRegionWitness,
    LocalArchiveVerifier,
    LocalArtifactBackupProvider,
    LocalBackupCatalog,
    LocalBareGitMirror,
    LocalDatabaseBackupProvider,
    LocalIsolatedRestoreVerifier,
    LocalOllamaGateway,
    LocalProviderError,
    LocalTrustedIdentityProvider,
    LocalVendorExportProvider,
    SafeNoopChaosProvider,
)
from ai_enterprise.infrastructure.resilience.provider_factory import (
    build_resilience_provider_bundle,
)


@pytest.mark.asyncio
async def test_local_file_backups_emit_hashes_but_restore_checks_fail_closed(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.sqlite"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE example(id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "evidence.txt").write_text("evidence", encoding="utf-8")
    catalog = LocalBackupCatalog()
    db_manifest = await LocalDatabaseBackupProvider(
        database, tmp_path / "backups", catalog
    ).create_manifest()
    artifact_manifest = await LocalArtifactBackupProvider(
        artifacts, tmp_path / "backups", catalog
    ).create_manifest()
    verifier = LocalIsolatedRestoreVerifier(catalog, tmp_path / "restores")
    db_restore = await verifier.restore_and_verify(db_manifest)
    artifact_restore = await verifier.restore_and_verify(artifact_manifest)
    assert db_manifest.content_hash and artifact_manifest.content_hash
    assert db_restore.status == "failed" and not db_restore.checks["git_reachability"]
    assert artifact_restore.status == "failed" and artifact_restore.checks["artifacts"]


@pytest.mark.asyncio
async def test_file_region_witness_increments_durable_fence(tmp_path: Path) -> None:
    witness = FileRegionWitness(tmp_path / "witness.json")
    resource = uuid.uuid4()
    first, first_evidence = await witness.acquire_fencing_token(resource, "eu-1")
    second, second_evidence = await witness.acquire_fencing_token(resource, "eu-2")
    assert (first, second) == (1, 2)
    assert first_evidence != second_evidence


@pytest.mark.asyncio
async def test_hmac_signer_requires_private_external_key_file(tmp_path: Path) -> None:
    key = tmp_path / "signing.key"
    key.write_bytes(os.urandom(32))
    key.chmod(0o600)
    signer = FileHmacSigningProvider(key)
    signature, key_id = await signer.sign(signer.key_id, "abc123")
    assert signature and key_id == signer.key_id
    key.chmod(0o644)
    with pytest.raises(LocalProviderError):
        FileHmacSigningProvider(key)


@pytest.mark.asyncio
async def test_identity_vendor_archive_and_safe_chaos_are_evidence_bound(
    tmp_path: Path,
) -> None:
    identities = tmp_path / "identities"
    identities.write_text("operator-1\n", encoding="utf-8")
    identities.chmod(0o600)
    identity = LocalTrustedIdentityProvider(identities)
    assert await identity.strongly_authenticate("operator-1")
    assert not await identity.strongly_authenticate("unknown")

    source = tmp_path / "vendor"
    source.mkdir()
    (source / "export.json").write_text("{}", encoding="utf-8")
    path, digest = await LocalVendorExportProvider(source, tmp_path / "exports").export(
        uuid.uuid4()
    )
    verified, actual = await LocalArchiveVerifier(tmp_path).verify(path, digest)
    assert verified and actual == digest

    experiment = uuid.uuid4()
    chaos = SafeNoopChaosProvider(frozenset({experiment}))
    status, evidence = await chaos.execute(experiment)
    assert status == "passed" and evidence
    with pytest.raises(LocalProviderError):
        await chaos.execute(uuid.uuid4())


@pytest.mark.asyncio
async def test_local_bare_mirror_verifies_commit_reachability(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init"], cwd=source, check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=f@invalid",
            "commit",
            "--allow-empty",
            "-m",
            "base",
        ],
        cwd=source,
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=source, check=True, capture_output=True, text=True
    ).stdout.strip()
    bare_source = tmp_path / "source.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare_source)],
        check=True,
        capture_output=True,
    )
    mirror = LocalBareGitMirror(bare_source.as_uri(), tmp_path / "mirror.git")
    assert await mirror.synchronize()
    result = await mirror.verify_reachability((commit, "0" * 40))
    assert result == {commit: True, "0" * 40: False}


@pytest.mark.asyncio
async def test_ollama_gateway_rejects_unmapped_model_without_network() -> None:
    with pytest.raises(LocalProviderError):
        await LocalOllamaGateway("http://127.0.0.1:11434", {}).generate(
            uuid.uuid4(), {"prompt": "hello"}
        )


def test_provider_factory_is_explicit_and_development_only(tmp_path: Path) -> None:
    unconfigured = build_resilience_provider_bundle(
        Settings(resilience_provider_profile="unconfigured")
    )
    with pytest.raises(RuntimeError):
        unconfigured.region_witness.acquire_fencing_token(uuid.uuid4(), "local")
    with pytest.raises(RuntimeError):
        build_resilience_provider_bundle(
            Settings(
                app_env="production",
                resilience_provider_profile="local-development",
                resilience_local_root=tmp_path,
            )
        )
