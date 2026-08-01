from pathlib import Path

import pytest

from ai_enterprise.infrastructure.resilience.local_providers import (
    FileHmacSigningProvider,
    LocalBackupCatalog,
    LocalBareGitMirror,
    LocalDatabaseBackupProvider,
    LocalProviderError,
)
from ai_enterprise.infrastructure.security.local_activation import (
    HmacSigner,
    LocalActivationSecurityError,
    RestoreIsolationEvidence,
    require_bounded_bare_remote,
    require_configured_endpoint,
    require_confined_backup_path,
    require_provider_environment,
    require_restore_isolation,
    require_safe_log_metadata,
    sign_identity_assertion,
    verify_identity_assertion,
)

HASH = "a" * 64


@pytest.mark.parametrize("environment", ["production", "staging", "PRODUCTION"])
def test_production_like_environments_never_select_local_provider(environment: str) -> None:
    with pytest.raises(LocalActivationSecurityError, match="forbidden"):
        require_provider_environment(app_env=environment, provider_kind="local")


def test_model_gateway_accepts_only_the_configured_endpoint() -> None:
    configured = "http://127.0.0.1:11434/api"
    assert (
        require_configured_endpoint(requested=f"{configured}/", configured=configured) == configured
    )
    with pytest.raises(LocalActivationSecurityError, match="configured"):
        require_configured_endpoint(requested="http://127.0.0.1:11435/api", configured=configured)
    with pytest.raises(LocalActivationSecurityError, match="credentials"):
        require_configured_endpoint(requested="http://token@127.0.0.1:11434", configured=configured)


def test_local_push_is_confined_to_configured_bare_remote(tmp_path: Path) -> None:
    root = tmp_path / "remotes"
    bare = root / "project.git"
    for name in ("objects", "refs"):
        (bare / name).mkdir(parents=True, exist_ok=True)
    (bare / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    assert require_bounded_bare_remote(remote_url=bare.as_uri(), allowed_root=root) == bare

    outside = tmp_path / "outside.git"
    for name in ("objects", "refs"):
        (outside / name).mkdir(parents=True, exist_ok=True)
    (outside / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    with pytest.raises(LocalActivationSecurityError, match="escapes"):
        require_bounded_bare_remote(remote_url=outside.as_uri(), allowed_root=root)


def test_backup_path_rejects_escape_and_symlink_traversal(tmp_path: Path) -> None:
    root = tmp_path / "backups"
    root.mkdir()
    assert require_confined_backup_path(candidate=root / "daily" / "archive.bin", allowed_root=root)
    with pytest.raises(LocalActivationSecurityError, match="escapes"):
        require_confined_backup_path(candidate=root / ".." / "outside.bin", allowed_root=root)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(LocalActivationSecurityError, match="Symlink"):
        require_confined_backup_path(candidate=root / "linked" / "archive.bin", allowed_root=root)


def test_restore_requires_isolation_and_bound_evidence() -> None:
    evidence = RestoreIsolationEvidence(True, True, True, HASH, "b" * 64)
    require_restore_isolation(evidence)
    with pytest.raises(LocalActivationSecurityError, match="incomplete"):
        require_restore_isolation(RestoreIsolationEvidence(True, False, True, HASH, "b" * 64))


def test_signatures_and_identity_hmac_detect_tampering_without_exposing_secret() -> None:
    secret = b"x" * 32
    signer = HmacSigner("local-test-key", secret)
    signature = signer.sign(b"record")
    assert signer.verify(b"record", signature)
    assert not signer.verify(b"tampered", signature)
    assert secret.decode() not in repr(signer)

    identity_signature = sign_identity_assertion(
        secret=secret,
        actor_id="developer",
        actor_type="human",
        actor_role="local_operator",
        timestamp=123,
    )
    assert verify_identity_assertion(
        secret=secret,
        actor_id="developer",
        actor_type="human",
        actor_role="local_operator",
        timestamp=123,
        signature=identity_signature,
    )
    assert not verify_identity_assertion(
        secret=secret,
        actor_id="attacker",
        actor_type="human",
        actor_role="local_operator",
        timestamp=123,
        signature=identity_signature,
    )


def test_secret_bearing_metadata_is_rejected_before_logging() -> None:
    assert require_safe_log_metadata({"provider": "ollama", "duration_ms": 4})
    with pytest.raises(LocalActivationSecurityError, match="cannot be logged"):
        require_safe_log_metadata({"token": "do-not-log"})


@pytest.mark.asyncio
async def test_git_mirror_rejects_non_file_remote_and_out_of_root_destination(
    tmp_path: Path,
) -> None:
    with pytest.raises(LocalProviderError):
        await LocalBareGitMirror(
            "https://example.invalid/repository.git", tmp_path / "mirror.git", tmp_path
        ).synchronize()

    remote_root = tmp_path / "remotes"
    remote = remote_root / "project.git"
    for name in ("objects", "refs"):
        (remote / name).mkdir(parents=True, exist_ok=True)
    (remote / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    with pytest.raises(LocalProviderError, match="escapes"):
        await LocalBareGitMirror(
            remote.as_uri(), tmp_path / "outside" / "mirror.git", remote_root
        ).synchronize()


@pytest.mark.asyncio
async def test_backup_destination_and_signing_key_reject_symlink_indirection(
    tmp_path: Path,
) -> None:
    database = tmp_path / "database.sqlite"
    database.write_bytes(b"database")
    outside = tmp_path / "outside"
    outside.mkdir()
    linked_root = tmp_path / "backups"
    linked_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(LocalProviderError, match="Symlink"):
        await LocalDatabaseBackupProvider(
            database, linked_root, LocalBackupCatalog()
        ).create_manifest()

    key = tmp_path / "real-key"
    key.write_bytes(b"x" * 32)
    key.chmod(0o600)
    linked_key = tmp_path / "signing-key"
    linked_key.symlink_to(key)
    with pytest.raises(LocalProviderError, match="symlink"):
        FileHmacSigningProvider(linked_key)
