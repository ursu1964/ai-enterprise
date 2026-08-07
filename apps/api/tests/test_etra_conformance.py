import importlib.util
import json
import sys
from pathlib import Path

import jsonschema


def _validator_module():
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / "etra_conformance.py"
    spec = importlib.util.spec_from_file_location("etra_conformance", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_repository_conforms_to_enterprise_reference_architecture() -> None:
    module = _validator_module()
    root = Path(__file__).resolve().parents[3]
    report = module.validate(root)
    assert report.conformant, report.findings
    assert report.checks >= 100
    assert report.schema_version == "1.0"
    assert report.schema_ref == "schemas/release-artifacts/etra-conformance-report.schema.json"
    schema = json.loads((root / report.schema_ref).read_text(encoding="utf-8"))
    jsonschema.validate(module._report_document(report), schema)


def test_validator_has_ci_friendly_json_and_exit_status(capsys) -> None:
    module = _validator_module()
    root = Path(__file__).resolve().parents[3]
    assert module.main(["--root", str(root), "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["conformant"] is True
    assert output["standard_version"] == "1.0"
    assert output["schema_ref"] == "schemas/release-artifacts/etra-conformance-report.schema.json"


def test_default_root_is_independent_of_working_directory(monkeypatch, tmp_path, capsys) -> None:
    module = _validator_module()
    monkeypatch.chdir(tmp_path)
    assert module.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["conformant"] is True


def test_etra_report_fails_closed_when_schema_validation_fails(monkeypatch) -> None:
    module = _validator_module()
    original_schema = module._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    try:
        module.validate(Path(__file__).resolve().parents[3])
    except RuntimeError as exc:
        assert "etra-conformance-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid ETRA conformance report was accepted")


def test_domain_import_detection_rejects_relative_dynamic_and_invalid_source(tmp_path) -> None:
    module = _validator_module()
    relative = tmp_path / "relative.py"
    relative.write_text("from ..infrastructure import database\n", encoding="utf-8")
    imports, error = module._python_imports(relative)
    assert error is None
    assert any(module._is_forbidden_domain_import(name) for name in imports)
    dynamic = tmp_path / "dynamic.py"
    dynamic.write_text(
        'import importlib\nimportlib.import_module("sqlalchemy.orm")\n', encoding="utf-8"
    )
    imports, error = module._python_imports(dynamic)
    assert error is None and "sqlalchemy.orm" in imports
    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n", encoding="utf-8")
    _, error = module._python_imports(invalid)
    assert error is not None


def test_migration_graph_parses_quotes_branches_dangling_parents_and_cycles(tmp_path) -> None:
    module = _validator_module()
    (tmp_path / "one.py").write_text("revision = 'one'\ndown_revision = None\n", encoding="utf-8")
    (tmp_path / "two.py").write_text(
        'revision: str = "two"\ndown_revision: str = "one"\n', encoding="utf-8"
    )
    heads, issues = module._migration_graph(tmp_path)
    assert heads == {"two"} and not issues
    (tmp_path / "branch.py").write_text(
        "revision = 'branch'\ndown_revision = 'one'\n", encoding="utf-8"
    )
    _, issues = module._migration_graph(tmp_path)
    assert "expected one migration head, found 2" in issues
    (tmp_path / "dangling.py").write_text(
        "revision = 'dangling'\ndown_revision = 'missing'\n", encoding="utf-8"
    )
    _, issues = module._migration_graph(tmp_path)
    assert "dangling down_revision: missing" in issues
    (tmp_path / "one.py").write_text("revision = 'one'\ndown_revision = 'two'\n", encoding="utf-8")
    _, issues = module._migration_graph(tmp_path)
    assert any(issue.startswith("migration cycle at") for issue in issues)


def test_secret_ignore_requires_exact_env_rule() -> None:
    module = _validator_module()
    assert module._has_exact_env_ignore([".env"])
    assert module._has_exact_env_ignore(["/.env"])
    assert not module._has_exact_env_ignore([".environment", "*.local.env"])
