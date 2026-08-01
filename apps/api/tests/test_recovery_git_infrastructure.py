import subprocess
from pathlib import Path

import pytest

from ai_enterprise.domain.recovery.exceptions import RevertConflict
from ai_enterprise.infrastructure.recovery.remote_verifier import RecoveryRepositoryVerifier
from ai_enterprise.infrastructure.recovery.revert_builder import RevertBuilder


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repository, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _commit(repository: Path, message: str) -> str:
    _git(repository, "add", ".")
    _git(
        repository,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "HEAD")


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    (repository / "value.txt").write_text("base\n")
    _commit(repository, "base")
    return repository


def test_revert_builder_prepares_inverse_tree(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "value.txt").write_text("integrated\n")
    integration_commit = _commit(repository, "integration")

    prepared = RevertBuilder().prepare(
        repository=repository, integration_commit_sha=integration_commit
    )

    assert prepared.changed_paths == ("value.txt",)
    assert _git(repository, "show", f"{prepared.candidate_tree_sha}:value.txt") == "base"


def test_revert_conflict_is_not_resolved_and_workspace_is_clean(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    (repository / "value.txt").write_text("integrated\n")
    integration_commit = _commit(repository, "integration")
    (repository / "value.txt").write_text("later incompatible value\n")
    _commit(repository, "later")

    with pytest.raises(RevertConflict) as error:
        RevertBuilder().prepare(
            repository=repository, integration_commit_sha=integration_commit
        )

    assert error.value.paths == ("value.txt",)
    assert _git(repository, "status", "--porcelain=v1") == ""


def test_remote_verifier_checks_commit_tree_parent_and_ancestry(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    base = _git(repository, "rev-parse", "HEAD")
    (repository / "value.txt").write_text("integrated\n")
    integration = _commit(repository, "integration")
    (repository / "value.txt").write_text("base\n")
    recovery = _commit(repository, "recovery")
    tree = _git(repository, "rev-parse", f"{recovery}^{{tree}}")
    _git(repository, "update-ref", "refs/remotes/origin/main", recovery)

    result = RecoveryRepositoryVerifier().verify_recovery_result(
        repository=repository,
        remote_name="origin",
        target_branch="main",
        expected_commit_sha=recovery,
        expected_tree_sha=tree,
        expected_parent_sha=integration,
        reverted_integration_commit_sha=integration,
    )
    assert result.commit_sha == recovery
    assert base != recovery
