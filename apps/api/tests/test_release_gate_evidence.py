import importlib.util
import sys
from pathlib import Path


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
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
    root = Path(__file__).resolve().parents[3]
    makefile = (root / "Makefile").read_text(encoding="utf-8")

    assert "release-gate-evidence-fast" in makefile
    assert "--evidence-file artifacts/gate-evidence.json" in makefile
    assert "--require-evidence-for lint,typecheck,test" in makefile
    assert "tools/release_gate_evidence.py" in makefile
    assert "check-release: compose-check migration-check check-fast" in makefile


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
