from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from ai_enterprise.application.resilience.extended_interfaces import (
    UnconfiguredExternalProvider,
)
from ai_enterprise.config import Settings

from .local_providers import (
    FileHmacSigningProvider,
    FileRegionWitness,
    FoundationFileHmacSigner,
    LocalArchiveVerifier,
    LocalArtifactBackupProvider,
    LocalBackupCatalog,
    LocalBareGitMirror,
    LocalDatabaseBackupProvider,
    LocalIsolatedRestoreVerifier,
    LocalOllamaGateway,
    LocalTrustedIdentityProvider,
    LocalVendorExportProvider,
    SafeNoopChaosProvider,
)


@dataclass(frozen=True, slots=True)
class ResilienceProviderBundle:
    database_backup: Any
    artifact_backup: Any
    repository_mirror: Any
    restore_environment: Any
    region_witness: Any
    model_gateway: Any
    signing_provider: Any
    foundation_signer: Any
    identity_provider: Any
    vendor_export: Any
    archive_verifier: Any
    chaos_provider: Any


def build_resilience_provider_bundle(settings: Settings) -> ResilienceProviderBundle:
    unavailable = UnconfiguredExternalProvider()
    if settings.resilience_provider_profile == "unconfigured":
        return ResilienceProviderBundle(*(unavailable for _ in range(12)))
    if settings.resilience_provider_profile != "local-development":
        raise RuntimeError("Unknown resilience provider profile")
    if settings.app_env != "development":
        raise RuntimeError("Local resilience providers are development-only")

    root = settings.resilience_local_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    catalog = LocalBackupCatalog()
    database = (
        LocalDatabaseBackupProvider(
            settings.resilience_local_database_path, root / "backups", catalog
        )
        if settings.resilience_local_database_path
        else unavailable
    )
    artifacts = LocalArtifactBackupProvider(settings.artifact_root, root / "backups", catalog)
    restore = LocalIsolatedRestoreVerifier(catalog, root / "restore-tests")
    mirror = (
        LocalBareGitMirror(
            settings.resilience_local_git_remote,
            settings.resilience_local_git_mirror_path,
            root,
        )
        if settings.resilience_local_git_remote and settings.resilience_local_git_mirror_path
        else unavailable
    )
    models: dict[uuid.UUID, str] = {}
    for key, value in settings.resilience_local_ollama_models.items():
        try:
            models[uuid.UUID(key)] = value
        except ValueError as exc:
            raise RuntimeError("Local Ollama model map keys must be UUIDs") from exc
    approved_experiments: set[uuid.UUID] = set()
    for value in settings.resilience_local_approved_noop_experiments:
        try:
            approved_experiments.add(uuid.UUID(value))
        except ValueError as exc:
            raise RuntimeError("Approved no-op experiment IDs must be UUIDs") from exc
    model_gateway = LocalOllamaGateway(settings.ollama_base_url, models)
    signing: Any
    if settings.resilience_local_signing_key_path:
        signing = FileHmacSigningProvider(settings.resilience_local_signing_key_path)
        foundation_signer: Any = FoundationFileHmacSigner(signing)
    else:
        signing = unavailable
        foundation_signer = unavailable
    identity = (
        LocalTrustedIdentityProvider(settings.resilience_local_identity_file)
        if settings.resilience_local_identity_file
        else unavailable
    )
    vendor = (
        LocalVendorExportProvider(settings.resilience_local_vendor_source, root / "vendor-exports")
        if settings.resilience_local_vendor_source
        else unavailable
    )
    return ResilienceProviderBundle(
        database,
        artifacts,
        mirror,
        restore,
        FileRegionWitness(root / "region-witness.json"),
        model_gateway,
        signing,
        foundation_signer,
        identity,
        vendor,
        LocalArchiveVerifier(root),
        SafeNoopChaosProvider(frozenset(approved_experiments)),
    )
