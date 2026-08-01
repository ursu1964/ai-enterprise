from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.recovery.processor import (
    ControlledRecoveryProcessor,
    RecoveryWorkerEntry,
)
from ai_enterprise.config import Settings
from ai_enterprise.infrastructure.integration.commit_creator import (
    DeterministicCommitCreator,
)
from ai_enterprise.infrastructure.integration.credentials import CredentialBroker
from ai_enterprise.infrastructure.integration.git_client import GitClient
from ai_enterprise.infrastructure.integration.pusher import RestrictedPusher
from ai_enterprise.infrastructure.integration.remote_verifier import RemoteVerifier
from ai_enterprise.infrastructure.integration.test_runner import ApprovedTestRunner
from ai_enterprise.infrastructure.integration.workspace_verifier import WorkspaceVerifier
from ai_enterprise.infrastructure.recovery.attempt_store import SqlAlchemyRecoveryAttemptStore
from ai_enterprise.infrastructure.recovery.revert_builder import RevertBuilder
from ai_enterprise.infrastructure.recovery.snapshot import FreshRecoverySnapshotManager


def build_recovery_worker_entry(
    *,
    session: AsyncSession,
    settings: Settings,
    worker_id: str,
    credential_broker: CredentialBroker,
) -> RecoveryWorkerEntry:
    """Build recovery execution with an explicit restricted credential source."""

    git = GitClient()
    processor = ControlledRecoveryProcessor(
        store=SqlAlchemyRecoveryAttemptStore(session),
        snapshots=FreshRecoverySnapshotManager(
            work_root=settings.recovery_work_root,
            git=git,
        ),
        reverts=RevertBuilder(),
        workspaces=WorkspaceVerifier(git=git),
        tests=ApprovedTestRunner(
            allowed_executables={"pytest", "ruff", "mypy", "python", "python3"}
        ),
        commits=DeterministicCommitCreator(git=git),
        pusher=RestrictedPusher(credentials=credential_broker, git=git),
        remote_verifier=RemoteVerifier(git=git),
        runtime_temp_root=settings.recovery_artifacts_root,
    )
    return RecoveryWorkerEntry(processor, worker_id)
