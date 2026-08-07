import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _repo_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "tools").is_dir():
            return candidate
    raise AssertionError("Could not locate repository root with tools directory")


def _load(name: str):
    root = _repo_root()
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


migration_verify = _load("migration_verify")
MIGRATION_GRAPH_SCHEMA = json.loads(
    (
        _repo_root() / "schemas" / "release-artifacts" / "migration-graph-report.schema.json"
    ).read_text(encoding="utf-8")
)


def test_migration_verify_accepts_linear_reversible_chain(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "one")

    report = migration_verify.verify(versions)

    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == "schemas/release-artifacts/migration-graph-report.schema.json"
    assert report["conformant"] is True
    assert report["migration_count"] == 2
    assert report["base_revisions"] == ["one"]
    assert report["head_revisions"] == ["two"]
    assert report["rollback_feasible_count"] == 2
    assert report["findings"] == []
    jsonschema.validate(report, MIGRATION_GRAPH_SCHEMA)


def test_migration_verify_rejects_dangling_parent_and_empty_downgrade(
    tmp_path: Path,
) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    _migration(versions / "one.py", "one", None)
    (versions / "two.py").write_text(
        'revision = "two"\n'
        'down_revision = "missing"\n'
        "def upgrade():\n"
        "    pass\n"
        "def downgrade():\n"
        "    pass\n",
        encoding="utf-8",
    )

    report = migration_verify.verify(versions)

    assert report["conformant"] is False
    assert "two: dangling down_revision missing" in report["findings"]
    assert "two: downgrade() is missing or not feasible" in report["findings"]
    jsonschema.validate(report, MIGRATION_GRAPH_SCHEMA)


def test_migration_verify_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    _migration(versions / "one.py", "one", None)
    original_schema = migration_verify._schema

    def stricter_schema(schema_ref: str) -> dict:
        schema = original_schema(schema_ref)
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(migration_verify, "_schema", stricter_schema)

    try:
        migration_verify.verify(versions)
    except RuntimeError as exc:
        assert "migration-graph-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid migration verification report was accepted")


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
