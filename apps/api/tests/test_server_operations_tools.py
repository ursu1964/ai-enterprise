import importlib.util
import json
import sys
from pathlib import Path

import jsonschema
import pytest


def repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "tools/sign_proxy_assertion.py").exists() and (
            candidate / "deploy/kubernetes/api-deployment.yaml"
        ).exists():
            return candidate
    raise AssertionError("Repository root was not found")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))
    return module


def test_server_secret_generator_replaces_placeholders(tmp_path: Path) -> None:
    root = repo_root()
    module = _load("generate_server_secrets", root / "tools/generate_server_secrets.py")

    generated = module.generate_env(root / ".env.server.example")

    assert "change-me-with-a-long-random-secret" not in generated
    assert "TRUSTED_PROXY_HMAC_SECRET=" in generated
    assert "MANAGED_POSTGRES_URL=" in generated


def test_model_endpoint_verifier_reports_missing_model_with_mocked_urlopen(monkeypatch) -> None:
    root = repo_root()
    module = _load("model_endpoint_verify", root / "tools/model_endpoint_verify.py")

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps({"models": [{"name": "available:latest"}]}).encode()

    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response())

    report = module.verify("http://ollama:11434", "required:latest")

    assert report["conformant"] is False
    assert report["findings"] == ["model_service: model required:latest not listed"]
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/production-readiness/model-endpoint-verification-report.schema.json"
    )
    schema = json.loads((root / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)


def test_model_endpoint_report_fails_closed_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = repo_root()
    module = _load("model_endpoint_verify", root / "tools/model_endpoint_verify.py")
    original_schema = module._schema

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self) -> bytes:
            return json.dumps({"models": [{"name": "required:latest"}]}).encode()

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "urlopen", lambda *args, **kwargs: Response())
    monkeypatch.setattr(module, "_schema", stricter_schema)

    with pytest.raises(
        RuntimeError,
        match="model-endpoint-verification-report.schema.json",
    ):
        module.verify("http://ollama:11434", "required:latest")


def test_proxy_signer_and_kubernetes_templates_are_present() -> None:
    root = repo_root()
    api = (root / "deploy/kubernetes/api-deployment.yaml").read_text(encoding="utf-8")
    worker = (root / "deploy/kubernetes/worker-deployment.yaml").read_text(encoding="utf-8")
    signer = (root / "tools/sign_proxy_assertion.py").read_text(encoding="utf-8")

    assert "kind: Deployment" in api
    assert "replicas: 2" in api
    assert "replicas: 3" in worker
    assert "X-Proxy-Signature" in signer


def test_deployment_blueprint_reports_all_migration_phases() -> None:
    root = repo_root()
    module = _load("deployment_blueprint", root / "tools/deployment_blueprint.py")

    report = module.build_blueprint(root)

    assert report["status"] == "ready"
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/production-readiness/deployment-blueprint-report.schema.json"
    )
    schema = json.loads((root / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    assert [phase["phase"] for phase in report["phases"]] == [1, 2, 3, 4, 5, 6]
    assert report["artifacts"]["prometheus_alerts"]["exists"] is True


def test_deployment_blueprint_fails_closed_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = repo_root()
    module = _load("deployment_blueprint", root / "tools/deployment_blueprint.py")
    original_schema = module._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    with pytest.raises(RuntimeError, match="deployment-blueprint-report.schema.json"):
        module.build_blueprint(root)


def test_infrastructure_choices_template_is_verifiable_with_placeholders() -> None:
    root = repo_root()
    module = _load("infrastructure_choices", root / "tools/infrastructure_choices.py")

    report = module.verify(
        root / "docs/enterprise/real-world-infrastructure-decisions.template.json",
        allow_placeholders=True,
    )

    assert report["status"] == "ready"
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == (
        "schemas/production-readiness/infrastructure-choices-report.schema.json"
    )
    schema = json.loads((root / report["schema_ref"]).read_text(encoding="utf-8"))
    jsonschema.validate(report, schema)
    assert "domain_tls" in report["sections"]


def test_infrastructure_choices_report_fails_closed_when_schema_validation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = repo_root()
    module = _load("infrastructure_choices", root / "tools/infrastructure_choices.py")
    original_schema = module._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(module, "_schema", stricter_schema)

    with pytest.raises(RuntimeError, match="infrastructure-choices-report.schema.json"):
        module.verify(
            root / "docs/enterprise/real-world-infrastructure-decisions.template.json",
            allow_placeholders=True,
        )
