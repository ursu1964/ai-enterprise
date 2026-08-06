import importlib.util
import json
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


production_evidence_init = _load("production_evidence_init")


def _write_templates(root: Path) -> None:
    enterprise = root / "docs" / "enterprise"
    enterprise.mkdir(parents=True)
    (enterprise / "real-world-infrastructure-decisions.template.json").write_text(
        json.dumps({"domain_tls": {"domain": "ai-enterprise.example.com"}}),
        encoding="utf-8",
    )
    (enterprise / "production-readiness-evidence.template.json").write_text(
        json.dumps({"environment": "production", "proof": {"tls": {"status": "pending"}}}),
        encoding="utf-8",
    )


def test_production_evidence_init_creates_missing_inputs_without_approving_production(
    tmp_path: Path,
) -> None:
    _write_templates(tmp_path)

    report = production_evidence_init.initialize(tmp_path)

    assert report["status"] == "initialized"
    assert report["production_allowed"] is False
    assert report["created_or_replaced"] == 2
    assert (tmp_path / "docs/enterprise/real-world-infrastructure-decisions.json").is_file()
    assert (tmp_path / "docs/enterprise/production-readiness-evidence.json").is_file()
    assert "rtk make production-readiness" in report["next_commands"]


def test_production_evidence_init_refuses_to_overwrite_existing_inputs_without_force(
    tmp_path: Path,
) -> None:
    _write_templates(tmp_path)
    target = tmp_path / "docs/enterprise/production-readiness-evidence.json"
    target.write_text('{"custom": true}', encoding="utf-8")

    report = production_evidence_init.initialize(tmp_path)

    statuses = {item["name"]: item["status"] for item in report["files"]}
    assert statuses["production_readiness_evidence"] == "already_exists"
    assert json.loads(target.read_text(encoding="utf-8")) == {"custom": True}


def test_production_evidence_init_force_replaces_existing_inputs(
    tmp_path: Path,
) -> None:
    _write_templates(tmp_path)
    target = tmp_path / "docs/enterprise/production-readiness-evidence.json"
    target.write_text('{"custom": true}', encoding="utf-8")

    report = production_evidence_init.initialize(tmp_path, force=True)

    statuses = {item["name"]: item["status"] for item in report["files"]}
    assert statuses["production_readiness_evidence"] == "replaced"
    assert json.loads(target.read_text(encoding="utf-8"))["environment"] == "production"
