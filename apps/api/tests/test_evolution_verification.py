import importlib.util
import json
import shutil
import sys
from pathlib import Path


def _load(name: str):
    if name == "evolution_verify":
        _load("etra_conformance")
        _load("generate_engineering_artifacts")
        _load("engineering_verify")
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _root(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[3]
    target = tmp_path / "specifications" / "evolution"
    target.parent.mkdir(parents=True)
    shutil.copytree(source / "specifications" / "evolution", target)
    return tmp_path


def _change(root: Path, name: str, mutate) -> None:
    path = root / "specifications" / "evolution" / name
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_governed_evolution_assessment_is_deterministic_and_evidence_based() -> None:
    verifier = _load("evolution_verify")
    root = Path(__file__).resolve().parents[3]
    first, second = verifier.verify(root), verifier.verify(root)
    assert first.conformant and first == second
    assert first.maturity["security"] == 5
    assert first.maturity["architecture"] == 4
    assert first.benchmark_opportunities[0]["metric_id"] == "mean-recovery-minutes"
    assert len(first.evidence_hash) == 64


def test_capability_cannot_skip_lifecycle_or_self_authorize(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        document["capabilities"][0]["history"] = ["experimental", "stable"]
        document["authority"]["self_transition_allowed"] = True

    _change(root, "capabilities.v1.json", mutate)
    report = verifier.verify(root)
    assert {item.check for item in report.findings} >= {"capability", "authority"}


def test_maturity_level_cannot_exceed_evidence(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)
    _change(
        root,
        "maturity.v1.json",
        lambda document: document["dimensions"][0].update(expected_level=5),
    )
    assert any(item.check == "maturity" for item in verifier.verify(root).findings)


def test_benchmark_cannot_become_autonomous_decision_maker(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)
    _change(
        root,
        "benchmarks.v1.json",
        lambda document: document["authority"].update(automatic_investment_decisions=True),
    )
    assert any(item.check == "authority" for item in verifier.verify(root).findings)


def test_roadmap_cycles_and_unmeasured_outcomes_are_rejected(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        document["proposals"][0]["dependencies"] = ["EV-002"]
        document["proposals"][0]["success_measures"] = ["invented-score"]

    _change(root, "roadmap.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"roadmap", "roadmap-cycle"} <= checks


def test_refactoring_requires_independent_human_approval_and_rollback(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        transformation = document["transformations"][0]
        transformation["approver"] = transformation["proposer"]
        transformation["rollback"] = {}

    _change(root, "refactoring.v1.json", mutate)
    assert any(item.check == "refactoring" for item in verifier.verify(root).findings)


def test_self_reflection_cannot_approve_or_implement_recommendations(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        document["constraints"]["autonomous_implementation"] = True
        document["recommendations"][0]["status"] = "implemented"

    _change(root, "reflection.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"reflection-authority", "reflection"} <= checks


def test_evolution_specification_symlink_is_rejected(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)
    path = root / "specifications" / "evolution" / "reflection.v1.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    report = verifier.verify(root)
    assert any(item.check == "evolution-specification" for item in report.findings)


def test_duplicate_maturity_evidence_cannot_inflate_score(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        evidence = document["dimensions"][0]["evidence"]
        evidence[1]["evidence_id"] = evidence[0]["evidence_id"]
        evidence[1]["score"] = 5
        document["dimensions"][0]["expected_level"] = 5

    _change(root, "maturity.v1.json", mutate)
    assert any(item.check == "maturity" for item in verifier.verify(root).findings)


def test_benchmark_requires_distinct_historical_current_and_objective_evidence(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        metric = document["metrics"][0]
        metric["historical_evidence_id"] = metric["current_evidence_id"]

    _change(root, "benchmarks.v1.json", mutate)
    assert any(item.check == "benchmark" for item in verifier.verify(root).findings)


def test_hidden_roadmap_dependencies_require_attestation(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)
    _change(
        root,
        "roadmap.v1.json",
        lambda document: document["proposals"][0].update(dependency_attestation=False),
    )
    assert any(item.check == "roadmap-governance" for item in verifier.verify(root).findings)


def test_rollback_label_without_hash_steps_and_test_evidence_is_unsafe(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)

    def mutate(document):
        document["transformations"][0]["rollback"] = {"artifact": "unknown"}

    _change(root, "refactoring.v1.json", mutate)
    assert any(item.check == "refactoring" for item in verifier.verify(root).findings)


def test_ci_command_in_comment_does_not_satisfy_enforcement(tmp_path) -> None:
    verifier, root = _load("evolution_verify"), _root(tmp_path)
    workflow = root / ".github" / "workflows" / "engineering-verification.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text(
        "# run: python tools/evolution_verify.py --json\nname: bypass\n", encoding="utf-8"
    )
    assert any(item.check == "continuous-evolution" for item in verifier.verify(root).findings)
