from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.integration.processor import (
    ControlledIntegrationProcessor,
    IntegrationWorkerEntry,
    RollbackMetadataHook,
)
from ai_enterprise.config import Settings
from ai_enterprise.infrastructure.integration.attempt_store import (
    SqlAlchemyIntegrationAttemptStore,
)
from ai_enterprise.infrastructure.integration.commit_creator import (
    DeterministicCommitCreator,
)
from ai_enterprise.infrastructure.integration.credentials import CredentialBroker
from ai_enterprise.infrastructure.integration.git_client import GitClient
from ai_enterprise.infrastructure.integration.patch_verifier import VerifiedPatchApplier
from ai_enterprise.infrastructure.integration.pusher import RestrictedPusher
from ai_enterprise.infrastructure.integration.remote_verifier import RemoteVerifier
from ai_enterprise.infrastructure.integration.snapshot_manager import FreshSnapshotManager
from ai_enterprise.infrastructure.integration.test_runner import ApprovedTestRunner
from ai_enterprise.infrastructure.integration.workspace_verifier import WorkspaceVerifier


def build_integration_worker_entry(
    *,
    session: AsyncSession,
    settings: Settings,
    worker_id: str,
    credential_broker: CredentialBroker,
    rollback_hook: RollbackMetadataHook,
) -> IntegrationWorkerEntry:
    """Build a worker only when credentials and rollback recording are explicit.

    There is intentionally no default credential broker: production wiring must
    choose a restricted, ephemeral implementation rather than silently acquiring
    ambient credentials or enabling unauthenticated pushes.
    """

    git = GitClient()
    processor = ControlledIntegrationProcessor(
        store=SqlAlchemyIntegrationAttemptStore(session),
        snapshots=FreshSnapshotManager(
            work_root=settings.integration_work_root,
            git=git,
        ),
        patches=VerifiedPatchApplier(git=git),
        workspaces=WorkspaceVerifier(git=git),
        tests=ApprovedTestRunner(
            allowed_executables={
                "mypy",
                "node",
                "npm",
                "python",
                "python3",
                "pytest",
                "ruff",
            }
        ),
        commits=DeterministicCommitCreator(git=git),
        pusher=RestrictedPusher(credentials=credential_broker, git=git),
        remote_verifier=RemoteVerifier(git=git),
        rollback=rollback_hook,
        runtime_temp_root=settings.integration_work_root / "tmp",
    )
    return IntegrationWorkerEntry(processor, worker_id)
