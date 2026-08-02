from __future__ import annotations

import subprocess
from pathlib import Path


class RepositoryPreparationError(RuntimeError):
    pass


def prepare_project_repository(
    repository_path: str,
    default_branch: str,
    *,
    allowed_root: Path,
) -> dict[str, object]:
    path = Path(repository_path).expanduser().resolve()
    root = allowed_root.expanduser().resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise RepositoryPreparationError(f"Repository path must be under {root}") from exc
    path.mkdir(parents=True, exist_ok=True)
    initialized = False
    initial_commit_created = False
    if not (path / ".git").exists():
        _run(["git", "-C", str(path), "init", f"--initial-branch={default_branch}"])
        initialized = True
    if not _has_head(path):
        marker = path / ".ai-enterprise-initialized"
        if not marker.exists():
            marker.write_text(
                "Repository initialized by AI Enterprise for governed workflow execution.\n",
                encoding="utf-8",
            )
        _run(["git", "-C", str(path), "add", ".ai-enterprise-initialized"])
        _run(
            [
                "git",
                "-C",
                str(path),
                "-c",
                "user.name=AI Enterprise",
                "-c",
                "user.email=ai-enterprise@local.invalid",
                "commit",
                "-m",
                "Initialize AI Enterprise repository",
            ]
        )
        initial_commit_created = True
    return {
        "path": str(path),
        "initialized": initialized,
        "initial_commit_created": initial_commit_created,
        "head_ready": _has_head(path),
    }


def _has_head(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _run(command: list[str]) -> None:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RepositoryPreparationError(detail or f"Command failed: {' '.join(command)}")
