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


release_artifact = _load("release_artifact")


def test_release_artifact_records_release_gates_and_migration_summary(tmp_path: Path) -> None:
    root = _release_root(tmp_path)

    document = release_artifact.build_artifact(root)

    assert document["schema_version"] == "1.0"
    assert document["status"] == "passed"
    assert document["migration_verification"]["conformant"] is True
    assert document["migration_verification"]["rollback_feasible_count"] == 2
    assert {gate["name"] for gate in document["gates"]} >= {
        "compose-check",
        "migration-check",
        "docker-smoke",
        "engineering-full",
        "etra-check",
    }
    assert len(document["artifact_hash"]) == 64


def test_release_artifact_writes_json_file(tmp_path: Path) -> None:
    root = _release_root(tmp_path)
    output = Path("artifacts/release-verification.json")

    document = release_artifact.write_artifact(root, output)

    written = root / output
    assert written.exists()
    assert document["artifact_policy"]["archive_path"] == str(output)
    assert "release-verification" in written.name


def _release_root(tmp_path: Path) -> Path:
    versions = tmp_path / "migrations" / "versions"
    versions.mkdir(parents=True)
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "one")
    return tmp_path


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
