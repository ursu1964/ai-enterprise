import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest


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
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/production-readiness/backup-verification-report.schema.json"
    )
    schema_path = Path(module.__file__).resolve().parents[1] / report["schema_ref"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    assert any(item["key"] == "backup_root_writable" for item in report["checks"])


def test_backup_report_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "artifacts").mkdir()
    (root / "runtime-data").mkdir()
    module = _load_backup_verify()
    original_schema = module._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    with pytest.raises(RuntimeError, match="backup-verification-report.schema.json"):
        module.verify(root, root / "runtime-data" / "backups", docker=False)
