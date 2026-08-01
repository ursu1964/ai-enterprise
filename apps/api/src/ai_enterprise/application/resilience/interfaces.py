from __future__ import annotations

from typing import Protocol
from uuid import UUID

from ai_enterprise.domain.resilience.entities import (
    BackupManifest,
    ContinuityActivation,
    DisasterRecoveryRun,
    RecoveryObjective,
    RestoreVerification,
)


class ResilienceRepository(Protocol):
    async def get_objective(self, service_id: UUID) -> RecoveryObjective | None: ...
    async def get_active_continuity(self) -> tuple[ContinuityActivation, ...]: ...
    async def get_latest_backup(self, service_id: UUID) -> BackupManifest | None: ...
    async def save_restore(self, verification: RestoreVerification) -> None: ...
    async def save_dr_run(self, run: DisasterRecoveryRun) -> None: ...


class DatabaseBackupProvider(Protocol):
    async def create_manifest(self) -> BackupManifest:
        """Return evidence only; implementations must never infer recoverability."""
        ...


class ArtifactBackupProvider(Protocol):
    async def create_manifest(self) -> BackupManifest: ...


class RepositoryMirrorProvider(Protocol):
    async def verify_reachability(self, commit_shas: tuple[str, ...]) -> dict[str, bool]: ...


class IsolatedRestoreEnvironment(Protocol):
    production_credentials_disabled: bool
    external_dispatch_blocked: bool

    async def restore_and_verify(self, backup: BackupManifest) -> RestoreVerification: ...


class ExternalEffectReconciler(Protocol):
    async def unresolved_count(self, recovery_point: str) -> int: ...
