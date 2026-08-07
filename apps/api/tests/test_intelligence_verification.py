import importlib.util
import json
import shutil
import sys
from pathlib import Path

import jsonschema


def _load(name: str):
    if name == "intelligence_verify":
        dependencies = ("etra_conformance", "generate_engineering_artifacts", "engineering_verify")
        for dependency in dependencies:
            _load(dependency)
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _root(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    target = tmp_path / "specifications" / "intelligence"
    target.parent.mkdir(parents=True)
    shutil.copytree(source / "specifications" / "intelligence", target)
    workflow = tmp_path / ".github" / "workflows" / "engineering-verification.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("run: python tools/intelligence_verify.py --json\n", encoding="utf-8")
    return tmp_path


def _change(root: Path, name: str, mutate) -> None:
    path = root / "specifications" / "intelligence" / name
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_intelligence_baseline_is_deterministic_ranked_and_ci_enforced() -> None:
    verifier = _load("intelligence_verify")
    root = Path(__file__).resolve().parents[3]
    first, second = verifier.verify(root), verifier.verify(root)
    assert first.conformant and first == second
    assert [item["investment_id"] for item in first.investment_ranking] == ["INV-001", "INV-002"]
    assert len(first.evidence_hash) == 64
    assert first.schema_version == "1.0"
    assert first.schema_ref == (
        "schemas/release-artifacts/intelligence-verification-report.schema.json"
    )
    schema = json.loads((root / first.schema_ref).read_text(encoding="utf-8"))
    jsonschema.validate(verifier._report_document(first), schema)


def test_intelligence_report_fails_closed_when_schema_validation_fails(monkeypatch) -> None:
    verifier = _load("intelligence_verify")
    original_schema = verifier._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(verifier, "_schema", stricter_schema)

    try:
        verifier.verify(Path(__file__).resolve().parents[3])
    except RuntimeError as exc:
        assert "intelligence-verification-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid intelligence verification report was accepted")


def test_optimizer_cannot_fund_execute_or_hide_zero_capacity(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["authority"]["automatic_funding"] = True
        document["investments"][0]["available_capacity"] = 0
        document["investments"][0]["required_capacity"] = 0

    _change(root, "objective-optimizer.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"investment", "optimizer-authority"} <= checks


def test_optimizer_rejects_dependency_cycles_and_invalid_weights(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["weights"]["expected_value"] = 0.9
        document["investments"][0]["dependencies"] = ["INV-002"]

    _change(root, "objective-optimizer.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"objective-optimizer", "investment-cycle"} <= checks


def test_dashboard_cannot_remove_metric_provenance_or_preaggregation_auth(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["views"][0]["metrics"].pop()
        document["views"][1]["metrics"][0]["evidence_id"] = "fabricated"
        document["requirements"]["authorization_before_aggregation"] = False

    _change(root, "dashboard.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"dashboard", "dashboard-governance"} <= checks


def test_reasoning_rejects_single_domain_causality_and_missing_counterevidence(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        inference = document["inferences"][0]
        inference["source_evidence"] = inference["source_evidence"][:1]
        inference["counterevidence"] = []
        inference["causality_claimed"] = True

    _change(root, "cross-domain-reasoning.v1.json", mutate)
    assert any(item.check == "cross-domain-reasoning" for item in verifier.verify(root).findings)


def test_memory_rejects_duplicate_hash_self_supersession_and_raw_reasoning(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["items"][1]["memory_hash"] = document["items"][0]["memory_hash"]
        document["items"][0]["supersedes"] = document["items"][0]["memory_id"]
        document["policy"]["raw_reasoning_forbidden"] = False

    _change(root, "strategic-memory.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"strategic-memory", "strategic-memory-policy"} <= checks


def test_cognitive_policy_cannot_lower_thresholds_or_trust_model_output(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["policy"]["minimum_evidence_sources"] = 1
        document["policy"]["prohibited_recommendation_domains"] = []
        document["policy"]["model_output_trusted"] = True

    _change(root, "cognitive-governance.v1.json", mutate)
    assert any(item.check == "cognitive-governance" for item in verifier.verify(root).findings)


def test_recommendation_cannot_skip_lifecycle_self_review_or_gain_authority(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        recommendation = document["recommendations"][0]
        recommendation["history"] = ["generated", "accepted"]
        recommendation["status"] = "accepted"
        recommendation["review"]["actor_id"] = recommendation["proposed_by"]
        recommendation["authority"] = "executing"

    _change(root, "strategic-intelligence.v1.json", mutate)
    assert any(item.check == "strategic-recommendation" for item in verifier.verify(root).findings)


def test_symlink_spec_and_commented_ci_command_fail_closed(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)
    specification = root / "specifications" / "intelligence" / "cognitive-governance.v1.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(specification.read_bytes())
    specification.unlink()
    specification.symlink_to(outside)
    workflow = root / ".github" / "workflows" / "engineering-verification.yml"
    workflow.write_text("# run: python tools/intelligence_verify.py --json\n", encoding="utf-8")
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"intelligence-specification", "continuous-intelligence"} <= checks


def test_recommended_portfolio_cannot_overcommit_shared_capacity(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)
    _change(
        root,
        "objective-optimizer.v1.json",
        lambda document: document.update(capacity_budget=6),
    )
    findings = verifier.verify(root).findings
    assert any(item.check == "strategic-recommendation" for item in findings)


def test_hidden_dependency_and_capacity_fields_are_rejected(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["investments"][0]["soft_dependencies"] = ["external-program"]
        document["investments"][0]["untracked_capacity"] = 12

    _change(root, "objective-optimizer.v1.json", mutate)
    assert any(item.check == "investment" for item in verifier.verify(root).findings)


def test_dashboard_duplicate_metric_and_suppressed_counterevidence_fail(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        metrics = document["views"][0]["metrics"]
        metrics.append(dict(metrics[0]))
        metrics[0].pop("counterevidence")

    _change(root, "dashboard.v1.json", mutate)
    assert any(item.check == "dashboard" for item in verifier.verify(root).findings)


def test_duplicate_reasoning_evidence_cannot_fake_domain_diversity(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        sources = document["inferences"][0]["source_evidence"]
        sources[1]["evidence_id"] = sources[0]["evidence_id"]

    _change(root, "cross-domain-reasoning.v1.json", mutate)
    assert any(item.check == "cross-domain-reasoning" for item in verifier.verify(root).findings)


def test_memory_content_mutation_without_rehash_is_rejected(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)
    _change(
        root,
        "strategic-memory.v1.json",
        lambda document: document["items"][0].update(statement="Rewritten rationale"),
    )
    assert any(item.check == "strategic-memory" for item in verifier.verify(root).findings)


def test_consistent_but_weakened_governance_thresholds_are_rejected(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["policy"]["confidence_minimum"] = 0.1
        document["policy"]["confidence_maximum"] = 0.99

    _change(root, "cognitive-governance.v1.json", mutate)
    assert any(item.check == "cognitive-governance" for item in verifier.verify(root).findings)


def test_advisory_recommendation_cannot_smuggle_execution_payload(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["recommendations"][0]["execution_payload"] = {"deploy": "production"}

    _change(root, "strategic-intelligence.v1.json", mutate)
    assert any(item.check == "strategic-recommendation" for item in verifier.verify(root).findings)


def test_malformed_collection_shape_fails_closed_without_exception(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)
    _change(root, "dashboard.v1.json", lambda document: document.update(views={"metrics": []}))
    report = verifier.verify(root)
    assert not report.conformant
    assert any(item.check == "intelligence-shape" for item in report.findings)


def test_malformed_nested_evidence_shape_fails_closed_without_exception(tmp_path) -> None:
    verifier, root = _load("intelligence_verify"), _root(tmp_path)

    def mutate(document):
        document["inferences"][0]["source_evidence"] = ["not-an-evidence-object"]

    _change(root, "cross-domain-reasoning.v1.json", mutate)
    report = verifier.verify(root)
    assert not report.conformant
    assert any(item.check == "intelligence-shape" for item in report.findings)
