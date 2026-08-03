import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Could not locate repository root with tools directory")


def _load(name: str):
    root = _repo_root()
    if name == "release_artifact":
        _load("migration_verify")
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_gate_evidence = _load("release_gate_evidence")
release_artifact = _load("release_artifact")


def test_makefile_exposes_release_gate_evidence_target() -> None:
    root = _repo_root()
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "release-gate-evidence-fast" in makefile
    assert "release-gate-evidence-ci" in makefile
    assert "release-gate-evidence-release" in makefile
    assert "--evidence-file artifacts/gate-evidence.json" in makefile
    assert (
        "--require-evidence-for compose-check,migration-check,lint,typecheck,test,"
        "secret-scan,docker-smoke,engineering-static,evolution-check,federation-check,"
        "intelligence-check,engineering-full,etra-check"
        in makefile
    )
    assert "tools/release_gate_evidence.py" in makefile
    assert "--profile fast" in makefile
    assert "--profile ci" in makefile
    assert "--profile release" in makefile
    ci_commands = {
        "engineering-static=python tools/engineering_verify.py --static --json",
        "docker-smoke=python tools/docker_smoke.py --require-worker",
        "evolution-check=python tools/evolution_verify.py --json",
        "federation-check=python tools/federation_verify.py --json",
        "intelligence-check=python tools/intelligence_verify.py --json",
        "engineering-full=python tools/engineering_verify.py --full --json",
        "etra-check=python tools/etra_conformance.py --root . --json",
    }
    assert all(
        command in {
            f"{name}={gate_command}"
            for name, gate_command in release_gate_evidence.CI_GATE_COMMANDS.items()
        }
        for command in ci_commands
    )
    check_release = next(
        line for line in makefile.splitlines() if line.startswith("check-release:")
    )
    assert "release-gate-evidence-release release-artifact" in check_release
    assert check_release.index("release-gate-evidence-release") < check_release.index(
        "release-artifact"
    )


def test_release_gate_profiles_capture_expected_commands() -> None:
    assert release_gate_evidence.FAST_GATE_COMMANDS == {
        "lint": "cd apps/api && .venv/bin/ruff check src tests ../../migrations",
        "typecheck": "cd apps/api && .venv/bin/mypy src",
        "test": "cd apps/api && .venv/bin/pytest -q",
    }
    assert release_gate_evidence.GATE_COMMAND_PROFILES["fast"] == (
        release_gate_evidence.FAST_GATE_COMMANDS
    )
    assert release_gate_evidence.GATE_COMMAND_PROFILES["ci"] == (
        release_gate_evidence.CI_GATE_COMMANDS
    )
    assert release_gate_evidence.GATE_COMMAND_PROFILES["release"] == (
        release_gate_evidence.RELEASE_GATE_COMMANDS
    )
    assert set(release_gate_evidence.RELEASE_GATE_COMMANDS) == {
        name for name, _command in release_artifact.DEFAULT_GATES
    }
    assert release_gate_evidence.RELEASE_GATE_COMMANDS["compose-check"] == (
        "docker compose config --quiet"
    )
    assert "tools/migration_verify.py --json" in (
        release_gate_evidence.RELEASE_GATE_COMMANDS["migration-check"]
    )
    assert release_gate_evidence.RELEASE_GATE_COMMANDS["secret-scan"] == (
        "python tools/secret_scan.py --all"
    )
    assert release_gate_evidence.CI_GATE_COMMANDS["docker-smoke"] == (
        "python tools/docker_smoke.py --require-worker"
    )


def test_release_gate_profiles_can_be_overridden() -> None:
    assert release_gate_evidence._resolve_gate_commands(  # noqa: SLF001
        ["fast"],
        [("test", "python -m pytest tests/smoke")],
    ) == {
        "lint": "cd apps/api && .venv/bin/ruff check src tests ../../migrations",
        "typecheck": "cd apps/api && .venv/bin/mypy src",
        "test": "python -m pytest tests/smoke",
    }


def test_release_gate_evidence_captures_outputs_and_statuses(tmp_path: Path) -> None:
    document = release_gate_evidence.write_evidence(
        root=tmp_path,
        gate_commands={
            "passing-gate": "python -c \"print('ok gate')\"",
            "failing-gate": "python -c \"import sys; print('bad gate'); sys.exit(2)\"",
        },
        output=Path("artifacts/gate-evidence.json"),
        output_dir=Path("artifacts/release-gates"),
        timeout=30,
    )

    assert document["schema_version"] == "1.0"
    assert {"commit", "branch", "dirty"} <= set(document["git"])
    assert document["gates"]["passing-gate"]["status"] == "passed"
    assert document["gates"]["passing-gate"]["return_code"] == 0
    assert document["gates"]["failing-gate"]["status"] == "failed"
    assert document["gates"]["failing-gate"]["return_code"] == 2
    passing_output = tmp_path / document["gates"]["passing-gate"]["output_path"]
    failing_output = tmp_path / document["gates"]["failing-gate"]["output_path"]
    assert passing_output.read_text(encoding="utf-8").strip() == "ok gate"
    assert failing_output.read_text(encoding="utf-8").strip() == "bad gate"
    assert (tmp_path / "artifacts/gate-evidence.json").exists()


def test_release_artifact_consumes_captured_gate_evidence(tmp_path: Path) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    evidence = release_gate_evidence.write_evidence(
        root=tmp_path,
        gate_commands={"docker-smoke": "python -c \"print('smoke ok')\""},
        output=Path("artifacts/gate-evidence.json"),
        output_dir=Path("artifacts/release-gates"),
        timeout=30,
    )

    document = release_artifact.build_artifact(
        tmp_path,
        evidence_file=Path("artifacts/gate-evidence.json"),
    )
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert evidence["gates"]["docker-smoke"]["status"] == "passed"
    assert gates["docker-smoke"]["evidence"]["return_code"] == 0
    assert gates["docker-smoke"]["evidence"]["output_path"].endswith("docker-smoke.log")


def _migration(path: Path, revision: str, down_revision: str | None) -> None:
    path.write_text(
        f'revision = "{revision}"\n'
        f"down_revision = {down_revision!r}\n"
        "def upgrade():\n"
        "    op.create_table('example')\n"
        "def downgrade():\n"
        "    op.drop_table('example')\n",
        encoding="utf-8",
    )
