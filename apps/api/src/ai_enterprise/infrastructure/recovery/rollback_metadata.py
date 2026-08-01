import base64
import hashlib
import uuid
from pathlib import Path, PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.integration.processor import IntegrationCommand
from ai_enterprise.domain.recovery.bindings import hash_changed_paths, rollback_binding_hash
from ai_enterprise.domain.recovery.entities import ChangedPath
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    IntegrationApprovalModel,
    IntegrationAttemptModel,
    IntegrationCommitModel,
    RollbackRecordModel,
)
from ai_enterprise.infrastructure.integration.models import (
    CandidateCommit,
    RemoteEvidence,
    TestRunEvidence,
)
from ai_enterprise.infrastructure.recovery.git_runner import IsolatedGitRunner


class RollbackMetadataError(RuntimeError):
    pass


class SqlAlchemyRollbackMetadataHook:
    """Persist immutable recovery evidence after remote commit verification."""

    POLICY_VERSION = "recovery-v1"

    def __init__(self, session: AsyncSession, runner: IsolatedGitRunner | None = None) -> None:
        self._session = session
        self._runner = runner or IsolatedGitRunner()

    async def record(
        self,
        *,
        command: IntegrationCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
        tests: tuple[TestRunEvidence, ...],
        repository: Path,
    ) -> None:
        del tests  # Test commands are copied from the immutable approval, not runtime evidence.
        self._verify_remote(candidate, remote)
        attempt = await self._session.scalar(
            select(IntegrationAttemptModel)
            .where(IntegrationAttemptModel.id == command.attempt_id)
            .with_for_update()
        )
        if attempt is None:
            raise RollbackMetadataError("INTEGRATION_ATTEMPT_NOT_FOUND")
        approval = await self._session.get(
            IntegrationApprovalModel, attempt.integration_approval_id
        )
        if approval is None:
            raise RollbackMetadataError("INTEGRATION_APPROVAL_NOT_FOUND")

        existing = await self._session.scalar(
            select(RollbackRecordModel).where(
                RollbackRecordModel.integration_attempt_id == attempt.id
            )
        )
        if existing is not None:
            self._verify_existing(existing, command, candidate, remote)
            return

        parent_tree = self._git_output(repository, "rev-parse", f"{candidate.parent_sha}^{{tree}}")
        inverse_diff = self._git_bytes(
            repository,
            "diff",
            "--binary",
            "--full-index",
            candidate.commit_sha,
            candidate.parent_sha,
        )
        inverse_hash = hashlib.sha256(inverse_diff).hexdigest()
        changed_paths = self._changed_paths(repository, candidate.parent_sha, candidate.commit_sha)
        changed_hash = hash_changed_paths(changed_paths)
        artifact = ArtifactModel(
            id=uuid.uuid4(),
            project_id=attempt.project_id,
            run_id=None,
            artifact_type="integration_inverse_diff",
            media_type="application/octet-stream;base64",
            content=base64.b64encode(inverse_diff).decode("ascii"),
            content_hash=inverse_hash,
        )
        integration_commit = IntegrationCommitModel(
            id=uuid.uuid4(),
            integration_attempt_id=attempt.id,
            commit_sha=remote.commit_sha,
            tree_sha=remote.tree_sha,
            parent_commit_sha=remote.parent_sha,
            remote_verified=True,
        )
        binding = rollback_binding_hash(
            integration_attempt_id=str(attempt.id),
            integration_commit_sha=remote.commit_sha,
            parent_commit_sha=remote.parent_sha,
            integration_tree_sha=remote.tree_sha,
            parent_tree_sha=parent_tree,
            changed_paths_sha256=changed_hash,
            inverse_diff_sha256=inverse_hash,
            original_patch_sha256=command.binding.approved_patch_sha256,
            approved_test_commands_sha256=approval.approved_test_commands_sha256,
            recovery_policy_version=self.POLICY_VERSION,
        )
        rollback = RollbackRecordModel(
            id=uuid.uuid4(),
            integration_attempt_id=attempt.id,
            integration_commit_id=integration_commit.id,
            project_id=attempt.project_id,
            target_branch=remote.branch,
            integration_commit_sha=remote.commit_sha,
            parent_commit_sha=remote.parent_sha,
            integration_tree_sha=remote.tree_sha,
            parent_tree_sha=parent_tree,
            changed_paths=[item.as_dict() for item in changed_paths],
            changed_paths_sha256=changed_hash,
            inverse_diff_artifact_id=artifact.id,
            inverse_diff_sha256=inverse_hash,
            original_patch_sha256=command.binding.approved_patch_sha256,
            approved_test_commands=approval.approved_test_commands,
            approved_test_commands_sha256=approval.approved_test_commands_sha256,
            external_side_effects_declared=False,
            database_change_detected=self._has_prefix(
                changed_paths, ("alembic/versions/", "migrations/", "db/migrations/", "schema/")
            ),
            deployment_change_detected=self._has_prefix(
                changed_paths, ("terraform/", "helm/", "k8s/", "deploy/")
            ),
            recovery_policy_version=self.POLICY_VERSION,
            rollback_binding_sha256=binding,
        )
        self._session.add_all((artifact, integration_commit, rollback))
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(), project_id=attempt.project_id,
                event_type="integration.rollback_metadata_created",
                actor_type="integration_worker", actor_id=command.worker_id,
                payload={
                    "attempt_id": str(attempt.id), "commit_sha": remote.commit_sha,
                    "tree_sha": remote.tree_sha, "parent_sha": remote.parent_sha,
                    "inverse_diff_sha256": inverse_hash,
                    "changed_paths_sha256": changed_hash,
                    "rollback_binding_sha256": binding,
                    "artifact_id": str(artifact.id),
                },
            )
        )
        await self._session.commit()

    @staticmethod
    def _verify_remote(candidate: CandidateCommit, remote: RemoteEvidence) -> None:
        if (
            candidate.commit_sha != remote.commit_sha
            or candidate.tree_sha != remote.tree_sha
            or candidate.parent_sha != remote.parent_sha
        ):
            raise RollbackMetadataError("REMOTE_COMMIT_BINDING_MISMATCH")

    @staticmethod
    def _verify_existing(
        existing: RollbackRecordModel,
        command: IntegrationCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
    ) -> None:
        if (
            existing.integration_commit_sha != remote.commit_sha
            or existing.integration_tree_sha != remote.tree_sha
            or existing.parent_commit_sha != remote.parent_sha
            or existing.original_patch_sha256 != command.binding.approved_patch_sha256
            or candidate.commit_sha != remote.commit_sha
        ):
            raise RollbackMetadataError("ROLLBACK_METADATA_REPLAY_MISMATCH")

    def _git_output(self, repository: Path, *arguments: str) -> str:
        result = self._runner.run(repository, *arguments)
        if result.returncode != 0 or not result.stdout.strip():
            raise RollbackMetadataError("ROLLBACK_GIT_EVIDENCE_FAILED")
        return result.stdout.strip()

    def _git_bytes(self, repository: Path, *arguments: str) -> bytes:
        result = self._runner.run(repository, *arguments)
        if result.returncode != 0:
            raise RollbackMetadataError("ROLLBACK_INVERSE_DIFF_FAILED")
        return result.stdout.encode("utf-8", errors="surrogateescape")

    def _changed_paths(
        self, repository: Path, parent_sha: str, commit_sha: str
    ) -> tuple[ChangedPath, ...]:
        result = self._runner.run(
            repository, "diff", "--name-status", "-z", "-M", parent_sha, commit_sha
        )
        if result.returncode != 0:
            raise RollbackMetadataError("ROLLBACK_CHANGED_PATHS_FAILED")
        tokens = [token for token in result.stdout.split("\0") if token]
        paths: list[ChangedPath] = []
        index = 0
        while index < len(tokens):
            status = tokens[index]
            index += 1
            if status.startswith(("R", "C")):
                if index + 1 >= len(tokens):
                    raise RollbackMetadataError("ROLLBACK_CHANGED_PATHS_INVALID")
                old_path, path = tokens[index], tokens[index + 1]
                index += 2
            else:
                if index >= len(tokens):
                    raise RollbackMetadataError("ROLLBACK_CHANGED_PATHS_INVALID")
                old_path, path = None, tokens[index]
                index += 1
            self._validate_path(path)
            if old_path is not None:
                self._validate_path(old_path)
            paths.append(
                ChangedPath(
                    path=path,
                    change_type=status,
                    old_mode=self._mode(repository, parent_sha, old_path or path),
                    new_mode=self._mode(repository, commit_sha, path),
                    old_path=old_path,
                )
            )
        return tuple(sorted(paths, key=lambda item: item.path))

    def _mode(self, repository: Path, commit_sha: str, path: str) -> str | None:
        result = self._runner.run(repository, "ls-tree", commit_sha, "--", path)
        if result.returncode != 0 or not result.stdout.strip():
            return None
        return result.stdout.split(maxsplit=1)[0]

    @staticmethod
    def _validate_path(path: str) -> None:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts or path == ".git":
            raise RollbackMetadataError("ROLLBACK_CHANGED_PATH_UNSAFE")

    @staticmethod
    def _has_prefix(paths: tuple[ChangedPath, ...], prefixes: tuple[str, ...]) -> bool:
        return any(item.path.startswith(prefixes) for item in paths)


def build_sql_rollback_metadata_hook(session: AsyncSession) -> SqlAlchemyRollbackMetadataHook:
    return SqlAlchemyRollbackMetadataHook(session)
