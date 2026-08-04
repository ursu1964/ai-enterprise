import copy
import json
from pathlib import Path

from ai_enterprise.domain.aepm_validation import AepmValidationEngine

ROOT = Path(__file__).resolve().parents[3]


def sample() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )


def codes(document: dict[str, object]) -> set[str]:
    return {item.code for item in AepmValidationEngine().validate(document).findings}


def test_complete_manifest_has_deterministic_valid_report() -> None:
    first = AepmValidationEngine().validate(sample())
    second = AepmValidationEngine().validate(copy.deepcopy(sample()))

    assert first.valid is True
    assert first.findings == ()
    assert first.report_sha256 == second.report_sha256


def test_required_semantic_checks_are_classified() -> None:
    document = sample()
    document.pop("project_intent")
    document["business_outcomes"][0]["indicators"] = []  # type: ignore[index]
    document["capabilities"][0]["owner_stakeholder_id"] = "STK-999"  # type: ignore[index]
    document["core_processes"][0]["trigger"] = ""  # type: ignore[index]
    document["core_processes"][0]["outputs"] = []  # type: ignore[index]
    document["quality_requirements"][0]["acceptance_criteria"] = []  # type: ignore[index]
    document["data_entities"][0]["owner_stakeholder_id"] = ""  # type: ignore[index]
    document["integrations"][0]["security_rules"] = []  # type: ignore[index]

    assert {
        "AEPM-VAL-001",
        "AEPM-VAL-002",
        "AEPM-VAL-003",
        "AEPM-VAL-004",
        "AEPM-VAL-005",
        "AEPM-VAL-006",
        "AEPM-VAL-007",
        "AEPM-VAL-011",
    } <= codes(document)


def test_contradictions_assumptions_and_duplicates_are_deterministic() -> None:
    document = sample()
    document["business_rules"] = [  # type: ignore[assignment]
        {"id": "RULE-001", "description": "Must retain audit records"},
        {"id": "RULE-002", "description": "Must not retain audit records"},
    ]
    document["constraints"] = [  # type: ignore[assignment]
        {"id": "CON-001", "category": "technical", "description": "TBD hosting"},
        {"id": "CON-002", "category": "technical", "description": "TBD hosting"},
    ]

    report = AepmValidationEngine().validate(document)

    assert {"AEPM-VAL-008", "AEPM-VAL-009", "AEPM-VAL-010"} <= {
        item.code for item in report.findings
    }
    assert list(report.findings) == sorted(
        report.findings,
        key=lambda item: (
            0 if item.severity == "error" else 1,
            item.code,
            item.path,
            item.object_ids,
        ),
    )


def test_unknown_fields_and_bad_identifiers_get_schema_findings() -> None:
    document = sample()
    document["universal_ontology"] = True
    document["business_rules"][0]["id"] = "bad"  # type: ignore[index]

    report = AepmValidationEngine().validate(document)

    assert report.valid is False
    assert "AEPM-VAL-000" in {item.code for item in report.findings}
