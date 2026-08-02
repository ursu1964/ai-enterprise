import importlib.util
from pathlib import Path


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

    report = module.verify_server_readiness(
        root=root,
        env_file=root / ".env.server.example",
        compose_file=root / "docker-compose.server.example.yml",
        allow_placeholders=True,
    )

    assert report["conformant"] is True
    assert report["mode"] == "server_readiness"
    assert any(item["key"] == "server_storage_roots" for item in report["checks"])
    assert any(item["key"] == "migration_gate" for item in report["checks"])
    assert any(item["key"] == "observability_alerts" for item in report["checks"])
    assert any(item["key"] == "github_access_hooks" for item in report["checks"])
    assert any(item["key"] == "deployment_blueprint" for item in report["checks"])
    assert any(item["key"] == "infrastructure_choices_gate" for item in report["checks"])
