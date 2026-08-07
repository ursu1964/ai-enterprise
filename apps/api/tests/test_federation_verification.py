import importlib.util
import json
import shutil
import sys
from pathlib import Path

import jsonschema


def _load(name: str):
    if name == "federation_verify":
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
    target = tmp_path / "specifications" / "federation"
    target.parent.mkdir(parents=True)
    shutil.copytree(source / "specifications" / "federation", target)
    return tmp_path


def _change(root: Path, name: str, mutate) -> None:
    path = root / "specifications" / "federation" / name
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_federation_baseline_is_deterministic_and_ci_enforced() -> None:
    verifier = _load("federation_verify")
    root = Path(__file__).resolve().parents[3]
    first, second = verifier.verify(root), verifier.verify(root)
    assert first.conformant and first == second
    assert len(first.evidence_hash) == 64
    assert first.schema_version == "1.0"
    assert first.schema_ref == (
        "schemas/release-artifacts/federation-verification-report.schema.json"
    )
    schema = json.loads((root / first.schema_ref).read_text(encoding="utf-8"))
    jsonschema.validate(verifier._report_document(first), schema)


def test_federation_report_fails_closed_when_schema_validation_fails(monkeypatch) -> None:
    verifier = _load("federation_verify")
    original_schema = verifier._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(verifier, "_schema", stricter_schema)

    try:
        verifier.verify(Path(__file__).resolve().parents[3])
    except RuntimeError as exc:
        assert "federation-verification-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid federation verification report was accepted")


def test_applicable_regulation_cannot_be_omitted(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)
    _change(
        root,
        "regulatory.v1.json",
        lambda document: document["deployments"][0].update(inherited_modules=[]),
    )
    assert any(item.check == "regulatory-inheritance" for item in verifier.verify(root).findings)


def test_cloud_failover_cannot_cross_jurisdiction_or_activate_itself(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["providers"][1]["jurisdictions"] = ["US"]
        document["workloads"][0]["automatic_failover"] = True

    _change(root, "multi-cloud.v1.json", mutate)
    assert any(item.check == "multi-cloud" for item in verifier.verify(root).findings)


def test_external_event_cannot_skip_signature_policy_or_mutate_state(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["gateway_pipeline"].remove("verify-signature")
        document["direct_internal_state_mutation"] = True

    _change(root, "external-events.v1.json", mutate)
    assert any(item.check == "external-events" for item in verifier.verify(root).findings)


def test_graph_rejects_dangling_unevidenced_and_implicitly_trusted_claims(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["edges"][0]["target"] = "unknown"
        document["edges"][0]["evidence_id"] = "fabricated"
        document["external_claims_trusted_by_default"] = True

    _change(root, "ecosystem-graph.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"graph-edge", "graph-trust"} <= checks


def test_dashboard_cannot_remove_provenance_or_authorization(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["views"][0]["metrics"][0]["evidence_id"] = "missing"
        document["requirements"]["authorization_before_aggregation"] = False

    _change(root, "dashboard.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"dashboard-metric", "dashboard-security"} <= checks


def test_federation_trust_cannot_grant_inherited_authority(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["trust"]["substitutes_for_validation"] = True
        document["trust"]["inherited_authority"] = True
        document["sovereignty"]["remote_state_mutation"] = True

    _change(root, "protocol.v1.json", mutate)
    assert any(item.check == "federation-protocol" for item in verifier.verify(root).findings)


def test_symlink_spec_and_commented_ci_command_fail_closed(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)
    spec = root / "specifications" / "federation" / "protocol.v1.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(spec.read_bytes())
    spec.unlink()
    spec.symlink_to(outside)
    workflow = root / ".github" / "workflows" / "engineering-verification.yml"
    workflow.parent.mkdir(parents=True)
    workflow.write_text("# run: python tools/federation_verify.py --json\n", encoding="utf-8")
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"federation-specification", "continuous-federation"} <= checks


def test_regulatory_jurisdiction_laundering_is_rejected(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        deployment = document["deployments"][0]
        deployment["location"] = "UNCLASSIFIED"
        deployment["customer_class"] = "unknown"
        deployment["inherited_modules"] = []

    _change(root, "regulatory.v1.json", mutate)
    assert any(item.check == "regulatory-inheritance" for item in verifier.verify(root).findings)


def test_provider_residency_requires_attestation_and_regulatory_link(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["providers"][0]["jurisdiction_evidence_id"] = "provider-health-eu"
        document["workloads"][0]["regulatory_deployment_id"] = "enterprise-ca"

    _change(root, "multi-cloud.v1.json", mutate)
    assert any(item.check == "multi-cloud" for item in verifier.verify(root).findings)


def test_event_signature_ambiguity_duplicate_fields_and_non_atomic_replay_fail(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["required_envelope"].append("nonce")
        document["signature_canonicalization"] = "provider-default"
        document["replay_policy"]["atomic_insert_required"] = False

    _change(root, "external-events.v1.json", mutate)
    assert any(item.check == "external-events" for item in verifier.verify(root).findings)


def test_graph_duplicate_nodes_cross_scope_and_classification_downgrade_fail(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["nodes"].append(dict(document["nodes"][0]))
        document["nodes"][1]["visibility_scope"] = "partner-private"
        document["edges"][0]["classification"] = "public"

    _change(root, "ecosystem-graph.v1.json", mutate)
    assert any(item.check == "graph-node" for item in verifier.verify(root).findings)
    assert any(item.check == "graph-edge" for item in verifier.verify(root).findings)


def test_dashboard_view_name_cannot_hide_removed_metrics_or_scope_filters(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["views"][0]["metrics"].pop()
        document["requirements"]["relational_scope_filtering"] = False

    _change(root, "dashboard.v1.json", mutate)
    checks = {item.check for item in verifier.verify(root).findings}
    assert {"dashboard", "dashboard-security"} <= checks


def test_delegation_cannot_amplify_capabilities_or_redelegate(tmp_path) -> None:
    verifier, root = _load("federation_verify"), _root(tmp_path)

    def mutate(document):
        document["delegation"]["capability_subset_required"] = False
        document["delegation"]["redelegation"] = True
        document["delegation"]["maximum_hops"] = 8

    _change(root, "protocol.v1.json", mutate)
    assert any(item.check == "federation-protocol" for item in verifier.verify(root).findings)
