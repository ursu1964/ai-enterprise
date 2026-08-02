import importlib.util
import sys
from pathlib import Path


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


migration_verify = _load("migration_verify")


def test_migration_verify_accepts_linear_reversible_chain(tmp_path: Path) -> None:
    versions = tmp_path / "versions"
    versions.mkdir()
    _migration(versions / "one.py", "one", None)
    _migration(versions / "two.py", "two", "one")

    report = migration_verify.verify(versions)

    assert report["conformant"] is True
    assert report["migration_count"] == 2
    assert report["base_revisions"] == ["one"]
    assert report["head_revisions"] == ["two"]
    assert report["rollback_feasible_count"] == 2
    assert report["findings"] == []


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
