import importlib.util
from pathlib import Path


def _load_backup_verify():
    for candidate in Path(__file__).resolve().parents:
        module_path = candidate / "tools/backup_verify.py"
        if module_path.exists():
            spec = importlib.util.spec_from_file_location("backup_verify", module_path)
            assert spec is not None
            assert spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise AssertionError("backup_verify module was not found")


def test_backup_verifier_checks_local_roots_without_docker(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "artifacts").mkdir()
    (root / "runtime-data").mkdir()
    module = _load_backup_verify()

    report = module.verify(root, root / "runtime-data" / "backups", docker=False)

    assert report["conformant"] is True
    assert any(item["key"] == "backup_root_writable" for item in report["checks"])
