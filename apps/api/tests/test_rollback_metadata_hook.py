import base64
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from ai_enterprise.application.integration.processor import IntegrationCommand
from ai_enterprise.domain.execution.policies import ExecutionScope
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    IntegrationApprovalModel,
    IntegrationAttemptModel,
    IntegrationCommitModel,
    RollbackRecordModel,
)
from ai_enterprise.infrastructure.integration.models import (
    CandidateCommit,
    IntegrationBinding,
    RemoteEvidence,
    RepositoryPolicy,
)
from ai_enterprise.infrastructure.recovery.rollback_metadata import (
    RollbackMetadataError,
    SqlAlchemyRollbackMetadataHook,
    build_sql_rollback_metadata_hook,
)


def _git(repository: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repository, check=True, capture_output=True, text=True
    ).stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, str, str]:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    (repository / "app.py").write_text("old\n")
    _git(repository, "add", ".")
    _git(repository, "-c", "user.name=T", "-c", "user.email=t@invalid", "commit", "-m", "base")
    parent = _git(repository, "rev-parse", "HEAD")
    (repository / "app.py").write_text("new\n")
    _git(repository, "add", ".")
    _git(repository, "-c", "user.name=T", "-c", "user.email=t@invalid", "commit", "-m", "change")
    return repository, parent, _git(repository, "rev-parse", "HEAD")


def _command(attempt: IntegrationAttemptModel) -> IntegrationCommand:
    return IntegrationCommand(
        attempt_id=attempt.id, project_id=attempt.project_id, worker_id="worker:1",
        policy=RepositoryPolicy("project", "remote", "main", ("main",)),
        binding=IntegrationBinding(
            patch_id="patch", patch_sha256="a" * 64, artifact_sha256="a" * 64,
            audit_patch_sha256="a" * 64, approved_patch_sha256="a" * 64,
            base_commit_sha="b" * 40, base_tree_sha="c" * 40,
            approval_id=str(attempt.integration_approval_id), attempt_id=str(attempt.id),
        ), patch_bytes=b"patch", scope=ExecutionScope(("app.py",), ()), tests=(),
        commit_message="message", commit_timestamp=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_hook_persists_inverse_artifact_commit_record_and_audit(tmp_path: Path) -> None:
    repository, parent, commit = _repository(tmp_path)
    tree = _git(repository, "rev-parse", f"{commit}^{{tree}}")
    attempt = IntegrationAttemptModel(
        id=uuid4(), execution_run_id=uuid4(), integration_approval_id=uuid4(),
        attempt_number=1, status="pushing", project_id=uuid4(), target_branch="main",
        expected_patch_sha256="a" * 64, expected_base_commit_sha=parent,
        expected_base_tree_sha="c" * 40, correlation_id=uuid4(),
    )
    approval = IntegrationApprovalModel(
        id=attempt.integration_approval_id, execution_run_id=attempt.execution_run_id,
        eligibility_id=uuid4(), approver_subject="human:1", approver_role="integration_approver",
        project_id=attempt.project_id, repository_url="remote", target_branch="main",
        approved_patch_sha256="a" * 64, approved_base_commit_sha=parent,
        approved_base_tree_sha="c" * 40, approved_test_commands=[{"argv": ["pytest"]}],
        approved_test_commands_sha256="d" * 64, decision="consumed", reason="approved",
        policy_version="v1",
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[attempt, None])
    session.get = AsyncMock(return_value=approval)
    session.commit = AsyncMock()

    await SqlAlchemyRollbackMetadataHook(session).record(
        command=_command(attempt),
        candidate=CandidateCommit(commit, tree, parent, "message", "author", "committer"),
        remote=RemoteEvidence("main", commit, tree, parent), tests=(), repository=repository,
    )

    stored = session.add_all.call_args.args[0]
    artifact = next(item for item in stored if isinstance(item, ArtifactModel))
    integration = next(item for item in stored if isinstance(item, IntegrationCommitModel))
    rollback = next(item for item in stored if isinstance(item, RollbackRecordModel))
    expected_inverse = _git(repository, "diff", "--binary", "--full-index", commit, parent)
    assert base64.b64decode(artifact.content).decode().rstrip("\n") == expected_inverse
    assert integration.remote_verified is True
    assert rollback.changed_paths[0]["path"] == "app.py"
    assert rollback.rollback_binding_sha256
    session.commit.assert_awaited_once()


def test_factory_exposes_protocol_implementation() -> None:
    assert isinstance(build_sql_rollback_metadata_hook(MagicMock()), SqlAlchemyRollbackMetadataHook)


@pytest.mark.asyncio
async def test_hook_rejects_unverified_remote_binding(tmp_path: Path) -> None:
    repository, parent, commit = _repository(tmp_path)
    attempt = MagicMock(id=uuid4(), project_id=uuid4(), integration_approval_id=uuid4())
    hook = SqlAlchemyRollbackMetadataHook(MagicMock())
    with pytest.raises(RollbackMetadataError, match="REMOTE_COMMIT_BINDING_MISMATCH"):
        await hook.record(
            command=_command(attempt),
            candidate=CandidateCommit(commit, "tree", parent, "message", "author", "committer"),
            remote=RemoteEvidence("main", "different", "tree", parent),
            tests=(), repository=repository,
        )
