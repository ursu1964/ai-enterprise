import os
import stat
import subprocess
from pathlib import Path

import pytest

from ai_enterprise.bootstrap import RUNTIME_DIRECTORIES, prepare_owned_paths, prepare_runtime


def test_prepare_runtime_is_idempotent_and_keeps_secrets_private(tmp_path: Path) -> None:
    first = prepare_runtime(tmp_path)
    secret_file = tmp_path / "dev-secrets.env"
    original = secret_file.read_text(encoding="utf-8")
    second = prepare_runtime(tmp_path)

    assert first == second
    assert first.startswith("file://")
    assert secret_file.read_text(encoding="utf-8") == original
    assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
    assert (
        subprocess.run(
            [
                "git",
                "--git-dir",
                str(tmp_path / "remotes" / "ai-enterprise.git"),
                "rev-parse",
                "--is-bare-repository",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "true"
    )


def test_bootstrap_source_contains_no_generated_secret(tmp_path: Path) -> None:
    prepare_runtime(tmp_path)
    contents = (tmp_path / "dev-secrets.env").read_text(encoding="utf-8")
    assert "TRUSTED_PROXY_HMAC_SECRET=" in contents
    assert "LOCAL_SIGNING_SECRET=" in contents
    assert "changeme" not in contents


def test_prepare_runtime_creates_every_worker_output_directory(tmp_path: Path) -> None:
    prepare_runtime(tmp_path)

    assert all((tmp_path / name).is_dir() for name in RUNTIME_DIRECTORIES)


def test_prepare_owned_paths_is_recursive_and_idempotent(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    nested = runtime_root / "snapshots" / "existing-evidence"
    nested.mkdir(parents=True)
    evidence = nested / "result.json"
    evidence.write_text("preserved", encoding="utf-8")

    prepare_owned_paths(
        [runtime_root], owner_uid=os.getuid(), owner_gid=os.getgid()
    )
    prepare_owned_paths(
        [runtime_root], owner_uid=os.getuid(), owner_gid=os.getgid()
    )

    assert evidence.read_text(encoding="utf-8") == "preserved"
    assert evidence.stat().st_uid == os.getuid()
    assert evidence.stat().st_gid == os.getgid()


def test_prepare_owned_paths_refuses_symbolic_links(tmp_path: Path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    (runtime_root / "escape").symlink_to(tmp_path)

    with pytest.raises(ValueError, match="symbolic links"):
        prepare_owned_paths(
            [runtime_root], owner_uid=os.getuid(), owner_gid=os.getgid()
        )


def test_laptop_model_overlay_does_not_grant_container_execution_access() -> None:
    root = Path(__file__).resolve().parents[3]
    overlay = (root / "docker-compose.laptop.yml").read_text(encoding="utf-8")

    assert "network_mode: host" in overlay
    assert "http://127.0.0.1:11434" in overlay
    assert "127.0.0.1:5432" in overlay
    assert "docker.sock" not in overlay
    assert "cap_add" not in overlay
