import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import jsonschema


def _load(name: str):
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(name, root / "tools" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_load("production_readiness_contracts")
_load("infrastructure_choices")
production_readiness = _load("production_readiness")
production_evidence_plan = _load("production_evidence_plan")
SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "schemas"
        / "production-readiness"
        / "production-evidence-plan.schema.json"
    ).read_text(encoding="utf-8")
)


def _choices() -> dict:
    choices = {
        section: {field: f"real-{section}-{field}" for field in fields}
        for section, fields in production_readiness.infrastructure_choices.REQUIRED_SECTIONS.items()
    }
    choices["identity_proxy"]["signed_headers"] = [
        "X-Actor-ID",
        "X-Actor-Type",
        "X-Actor-Role",
        "X-Proxy-Timestamp",
        "X-Proxy-Signature",
    ]
    return choices


def _evidence() -> dict:
    proof = {}
    for name, fields in production_readiness.REQUIRED_PROOF.items():
        item = {
            "status": "passed",
            "checked_at": "2026-08-01T10:00:00Z",
            "valid_until": "2026-09-01T10:00:00Z",
            "evidence": f"artifacts/{name}.json",
        }
        for field in fields:
            item[field] = True if _boolean_field(field) else f"real-{field}"
        proof[name] = item
    return {"environment": "production", "reviewed_by": "release-owner", "proof": proof}


def test_production_evidence_plan_lists_operational_closure_items(
    tmp_path: Path,
) -> None:
    plan = production_evidence_plan.build_plan(
        tmp_path,
        Path("missing-evidence.json"),
        Path("missing-choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert plan["production_allowed"] is False
    assert plan["status"] == "blocked"
    assert len(plan["plan_hash"]) == 64
    jsonschema.validate(plan, SCHEMA)
    assert "rtk make production-readiness-contracts" in plan["validation_commands"]
    assert "rtk make production-readiness" in plan["validation_commands"]
    assert {
        "production_owners",
        "pilot_results",
        "infrastructure_credentials",
        "production_run_artifacts",
        "r16_graph_backend",
    }.issubset({item["name"] for item in plan["proof_requirements"]})
    pilot_plan = _find(plan["proof_requirements"], "name", "pilot_results")
    assert pilot_plan["owner_hint"] == "product owner and pilot stakeholders"
    assert "pilot_project" in pilot_plan["missing_fields"]
    assert pilot_plan["blocked"] is True
    graph_plan = _find(plan["proof_requirements"], "name", "r16_graph_backend")
    assert graph_plan["owner_hint"] == "data platform and knowledge graph owners"
    assert "deployment_evidence" in graph_plan["missing_fields"]
    assert graph_plan["blocked"] is True


def test_production_evidence_plan_is_ready_when_real_references_are_valid(
    tmp_path: Path,
) -> None:
    (tmp_path / "choices.json").write_text(json.dumps(_choices()), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(_evidence()), encoding="utf-8")

    plan = production_evidence_plan.build_plan(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    assert plan["production_allowed"] is True
    assert plan["status"] == "ready"
    assert plan["readiness_findings"] == []
    assert all(not item["missing_fields"] for item in plan["proof_requirements"])
    assert all(not item["validation_findings"] for item in plan["proof_requirements"])
    assert all(not item["blocked"] for item in plan["proof_requirements"])
    assert all(not item["missing_fields"] for item in plan["infrastructure_choice_requirements"])
    assert all(
        not item["validation_findings"] for item in plan["infrastructure_choice_requirements"]
    )
    assert all(not item["blocked"] for item in plan["infrastructure_choice_requirements"])


def test_production_evidence_plan_marks_present_but_invalid_template_values_blocked(
    tmp_path: Path,
) -> None:
    choices = _choices()
    choices["domain_tls"]["domain"] = "ai-enterprise.example.com"
    evidence = _evidence()
    evidence["proof"]["tls"]["status"] = "pending"
    evidence["proof"]["tls"]["checked_at"] = "YYYY-MM-DDTHH:MM:SSZ"
    evidence["proof"]["tls"]["valid_until"] = "YYYY-MM-DDTHH:MM:SSZ"
    (tmp_path / "choices.json").write_text(json.dumps(choices), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")

    plan = production_evidence_plan.build_plan(
        tmp_path,
        Path("evidence.json"),
        Path("choices.json"),
        now=datetime(2026, 8, 4, tzinfo=UTC),
    )

    tls_plan = _find(plan["proof_requirements"], "name", "tls")
    domain_plan = _find(plan["infrastructure_choice_requirements"], "section", "domain_tls")
    assert tls_plan["missing_fields"] == []
    assert tls_plan["blocked"] is True
    assert any("status must be passed" in item for item in tls_plan["validation_findings"])
    assert domain_plan["missing_fields"] == []
    assert domain_plan["blocked"] is True
    assert any("replace placeholder" in item for item in domain_plan["validation_findings"])


def test_production_evidence_plan_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    original_schema = production_evidence_plan._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(production_evidence_plan, "_schema", stricter_schema)

    try:
        production_evidence_plan.build_plan(
            tmp_path,
            Path("missing-evidence.json"),
            Path("missing-choices.json"),
            now=datetime(2026, 8, 4, tzinfo=UTC),
        )
    except RuntimeError as exc:
        assert "production-evidence-plan.schema.json" in str(exc)
        assert "generated production evidence plan does not validate" in str(exc)
    else:
        raise AssertionError("invalid production evidence plan was accepted")


def _find(items: list[dict], key: str, value: str) -> dict:
    return next(item for item in items if item[key] == value)


def _boolean_field(field: str) -> bool:
    return field.endswith(("verified", "passed", "reviewed", "absent"))
