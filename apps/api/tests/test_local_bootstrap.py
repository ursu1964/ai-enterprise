import stat
import subprocess
from pathlib import Path

from ai_enterprise.bootstrap import prepare_runtime


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
