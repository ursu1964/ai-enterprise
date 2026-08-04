import importlib.util
import subprocess
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
        _load("infrastructure_choices")
        _load("production_readiness")
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


release_artifact = _load("release_artifact")


def test_release_artifact_records_release_gates_and_migration_summary(tmp_path: Path) -> None:
    root = _release_root(tmp_path)

    document = release_artifact.build_artifact(root)

    assert document["schema_version"] == "1.0"
    assert document["status"] == "passed"
    assert document["release_environment"] == "non-production"
    assert document["production_readiness"] is None
    assert document["migration_verification"]["conformant"] is True
    assert document["migration_verification"]["rollback_feasible_count"] == 2
    assert document["gate_summary"]["total"] == len(document["gates"])
    assert document["gate_summary"]["failed"] == 0
    assert document["gate_summary"]["captured_evidence_required"] == []
    assert document["gate_evidence_file"]["loaded"] is False
    assert "make check-release" in document["gate_summary"]["execution_model"]
    assert {gate["name"] for gate in document["gates"]} >= {
        "compose-check",
        "migration-check",
        "lint",
        "typecheck",
        "test",
        "docker-smoke",
        "dashboard-verify",
        "dashboard-browser-verify",
        "engineering-full",
        "etra-check",
    }
    assert all(gate["required"] is True for gate in document["gates"])
    assert all(
        gate["evidence"]["source"] == "make check-release dependency"
        for gate in document["gates"]
    )
    assert document["artifact_policy"]["fails_when_migration_verification_fails"] is True
    assert document["artifact_policy"]["fails_when_required_gate_evidence_missing"] is True
    assert document["artifact_policy"]["fails_when_gate_evidence_commit_mismatch"] is True
    assert len(document["artifact_hash"]) == 64


def test_release_artifact_fails_closed_for_dirty_git_tree(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    (root / ".gitignore").write_text("artifacts/\n# dirty change\n", encoding="utf-8")

    document = release_artifact.build_artifact(root)

    assert document["status"] == "failed"
    assert document["git"]["dirty"] is True
    assert document["artifact_policy"]["fails_when_git_is_dirty_or_unknown"] is True


def test_release_artifact_rejects_evidence_tree_mismatch(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence = _evidence_document(root, {"lint": {"status": "passed"}})
    evidence_git = evidence["git"]
    assert isinstance(evidence_git, dict)
    evidence_git["tree"] = "0" * 40
    evidence_file.write_text(json_document(evidence), encoding="utf-8")

    document = release_artifact.build_artifact(
        root, evidence_file=evidence_file, require_evidence_for=("lint",)
    )

    assert document["status"] == "failed"
    assert document["gate_evidence_file"]["tree_matches_current"] is False


def test_production_release_fails_closed_without_readiness_evidence(tmp_path: Path) -> None:
    root = _release_root(tmp_path)

    document = release_artifact.build_artifact(root, production=True)

    assert document["status"] == "failed"
    assert document["release_environment"] == "production"
    assert document["production_readiness"]["production_allowed"] is False
    assert document["artifact_policy"]["fails_when_production_readiness_is_blocked"] is True


def test_release_artifact_fails_when_migration_verification_fails(tmp_path: Path) -> None:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "missing")

    document = release_artifact.build_artifact(tmp_path)

    assert document["status"] == "failed"
    assert document["gate_summary"]["failed"] == len(document["gates"])
    assert document["migration_verification"]["conformant"] is False
    assert any(
        "dangling down_revision" in finding
        for finding in document["migration_verification"]["findings"]
    )


def test_release_artifact_merges_supplied_gate_evidence(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence_file.write_text(
        json_document(
            _evidence_document(
                root,
                {
                    "docker-smoke": {"status": "passed", "duration_seconds": 12.5},
                    "engineering-full": {"status": "failed", "duration_seconds": 1.2},
                },
                status="failed",
            )
        ),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(root, evidence_file=evidence_file)
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "failed"
    assert document["gate_summary"]["failed"] == 1
    assert gates["docker-smoke"]["status"] == "passed"
    assert gates["docker-smoke"]["evidence"]["duration_seconds"] == 12.5
    assert gates["engineering-full"]["status"] == "failed"


def test_release_artifact_fails_when_required_captured_evidence_is_missing(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    evidence_file.write_text(
        json_document(
            _evidence_document(root, {"lint": {"status": "passed", "return_code": 0}})
        ),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(
        root,
        evidence_file=evidence_file,
        require_evidence_for=("lint", "typecheck", "test"),
    )
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "failed"
    assert document["gate_summary"]["captured_evidence_required"] == [
        "lint",
        "test",
        "typecheck",
    ]
    assert document["gate_summary"]["captured_evidence_missing"] == [
        "typecheck",
        "test",
    ]
    assert document["gate_evidence_file"]["missing_required_gates"] == [
        "typecheck",
        "test",
    ]
    assert gates["lint"]["status"] == "passed"
    assert gates["typecheck"]["status"] == "failed"
    assert gates["typecheck"]["evidence"]["missing_required_evidence"] is True


def test_release_artifact_passes_when_all_release_gate_evidence_is_present(
    tmp_path: Path,
) -> None:
    root = _release_root(tmp_path)
    evidence_file = root / "artifacts" / "gate-evidence.json"
    evidence_file.parent.mkdir()
    required = (
        "compose-check",
        "migration-check",
        "lint",
        "typecheck",
        "test",
        "secret-scan",
        "docker-smoke",
        "dashboard-verify",
        "engineering-static",
        "evolution-check",
        "federation-check",
        "intelligence-check",
        "engineering-full",
        "etra-check",
    )
    evidence_file.write_text(
        json_document(
            _evidence_document(
                root,
                {
                    name: {"status": "passed", "return_code": 0}
                    for name in required
                },
            )
        ),
        encoding="utf-8",
    )

    document = release_artifact.build_artifact(
        root,
        evidence_file=evidence_file,
        require_evidence_for=required,
    )
    gates = {gate["name"]: gate for gate in document["gates"]}

    assert document["status"] == "passed"
    assert document["gate_summary"]["captured_evidence_missing"] == []
    assert document["gate_summary"]["captured_evidence_required"] == sorted(required)
    assert all(gates[name]["evidence_required"] is True for name in required)
    assert all(
        gates[name]["evidence"]["missing_required_evidence"] is False
        for name in required
    )


def test_release_artifact_writes_json_file(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")

    document = release_artifact.write_artifact(root, output)

    written = root / output
    assert written.exists()
    assert document["artifact_policy"]["archive_path"] == str(output)
    assert "release-verification" in written.name


def json_document(value: object) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True)


def _release_root(tmp_path: Path) -> Path:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "one")
    (tmp_path / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    _init_git(tmp_path)
    return tmp_path


def _init_git(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release@example.test",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )


def _evidence_document(
    root: Path, gates: dict[str, object], *, status: str = "passed"
) -> dict[str, object]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True
    ).strip()
    return {
        "status": status,
        "provenance_valid": True,
        "git": {"commit": commit, "tree": tree, "branch": "main", "dirty": False},
        "gates": gates,
    }


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
