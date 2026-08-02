import subprocess
from pathlib import Path

from ai_enterprise.infrastructure.review.secret_scanner import SecretScanner


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_full_repo_secret_scan_detects_unstaged_secret(tmp_path: Path) -> None:
    init_repo(tmp_path)
    secret_file = tmp_path / "config.txt"
    token = "Bearer " + "abcdefghijklmnopqrstuvwxyz12345"
    secret_file.write_text(f"Authorization: {token}\n")

    findings = SecretScanner().scan_all(tmp_path)

    assert len(findings) == 1
    assert findings[0].rule_id == "generic-bearer-token"
    assert findings[0].file_path == "config.txt"


def test_full_repo_secret_scan_skips_runtime_and_private_env(tmp_path: Path) -> None:
    init_repo(tmp_path)
    token = "Bearer " + "abcdefghijklmnopqrstuvwxyz12345"
    runtime_secret = tmp_path / "runtime-data" / "dev-secrets.env"
    runtime_secret.parent.mkdir()
    runtime_secret.write_text(
        f"Authorization: {token} # allow-secret-test-fixture\n"
    )
    private_env = tmp_path / ".env"
    private_env.write_text(
        f"Authorization: {token} # allow-secret-test-fixture\n"
    )

    assert SecretScanner().scan_all(tmp_path) == ()


def test_staged_secret_scan_uses_git_index(tmp_path: Path) -> None:
    init_repo(tmp_path)
    clean_file = tmp_path / "clean.txt"
    clean_file.write_text("safe\n")
    secret_file = tmp_path / "secret.txt"
    token = "Bearer " + "abcdefghijklmnopqrstuvwxyz12345"
    secret_file.write_text(f"Authorization: {token}\n")
    subprocess.run(["git", "add", "secret.txt"], cwd=tmp_path, check=True)

    findings = SecretScanner().scan(tmp_path)

    assert len(findings) == 1
    assert findings[0].file_path == "secret.txt"
