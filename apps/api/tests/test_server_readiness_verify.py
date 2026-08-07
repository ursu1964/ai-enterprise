import importlib.util
import json
from pathlib import Path

import jsonschema


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/migration_verify.py").exists() and (
            candidate / "docker-compose.server.example.yml"
        ).exists():
            return candidate
    raise AssertionError("Repository root was not found")


def _load_migration_verify():
    root = repo_root()
    spec = importlib.util.spec_from_file_location(
        "migration_verify", root / "tools/migration_verify.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_server_readiness_verifier_accepts_template_with_placeholders_allowed() -> None:
    root = repo_root()
    module = _load_migration_verify()
    schema = json.loads(
        (
            root / "schemas" / "production-readiness" / "server-readiness-report.schema.json"
        ).read_text(encoding="utf-8")
    )

    report = module.verify_server_readiness(
        root=root,
        env_file=root / ".env.server.example",
        compose_file=root / "docker-compose.server.example.yml",
        allow_placeholders=True,
    )

    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/production-readiness/server-readiness-report.schema.json"
    )
    assert report["conformant"] is True
    assert report["mode"] == "server_readiness"
    assert any(item["key"] == "server_storage_roots" for item in report["checks"])
    assert any(item["key"] == "migration_gate" for item in report["checks"])
    assert any(item["key"] == "observability_alerts" for item in report["checks"])
    assert any(item["key"] == "github_access_hooks" for item in report["checks"])
    assert any(item["key"] == "deployment_blueprint" for item in report["checks"])
    assert any(item["key"] == "infrastructure_choices_gate" for item in report["checks"])
    jsonschema.validate(report, schema)


def test_server_readiness_fails_closed_when_schema_validation_fails(monkeypatch) -> None:
    root = repo_root()
    module = _load_migration_verify()
    original_schema = module._schema

    def stricter_schema(schema_ref: str) -> dict:
        schema = original_schema(schema_ref)
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    try:
        module.verify_server_readiness(
            root=root,
            env_file=root / ".env.server.example",
            compose_file=root / "docker-compose.server.example.yml",
            allow_placeholders=True,
        )
    except RuntimeError as exc:
        assert "server-readiness-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid server readiness report was accepted")
