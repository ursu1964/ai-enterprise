import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ai_enterprise.domain.aeir import RelationshipType, compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.aepm_interpretation import AiOperationRecord, _operation_hash
from ai_enterprise.domain.aepm_validation import AepmValidationEngine
from ai_enterprise.domain.clarification import (
    HumanReviewWorkflowState,
    validate_human_review_transition,
)

ROOT = Path(__file__).resolve().parents[3]
AEIR_SCHEMA = ROOT / "specifications/aeir/AEIR-0.1.schema.json"
RELATIONSHIP_SCHEMA = ROOT / "specifications/aeir/RELATIONSHIP-0.1.schema.json"
VALIDATION_FINDING_SCHEMA = (
    ROOT / "specifications/validation/VALIDATION-FINDING-0.1.schema.json"
)
AI_OPERATION_SCHEMA = ROOT / "specifications/ai/AI-OPERATION-0.1.schema.json"
DETERMINISTIC_AI_BOUNDARY = (
    ROOT / "specifications/ai/DETERMINISTIC-AI-BOUNDARY-0.1.md"
)
HUMAN_REVIEW_WORKFLOW_SCHEMA = (
    ROOT / "specifications/workflow/HUMAN-REVIEW-WORKFLOW-0.1.schema.json"
)
MVP_NON_GOALS = ROOT / "specifications/MVP-NON-GOALS-0.1.md"
EXAMPLE = ROOT / "examples/sample-project/aepm-0.1.json"
INVALID_EXAMPLE = ROOT / "examples/sample-project/aepm-0.1.invalid.json"
AEP_SCHEMA = ROOT / "specifications/aepm/AEPM-0.1.schema.json"


def _schema(path: Path) -> dict[str, object]:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def _assert_valid(schema: dict[str, object], instance: dict[str, object]) -> None:
    Draft202012Validator(schema).validate(instance)


def test_aeir_schema_declares_r2_status_and_reference_fields() -> None:
    schema = _schema(AEIR_SCHEMA)
    object_schema = schema["$defs"]["object"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert {"objects", "relationships", "model_sha256"} <= set(schema["required"])
    assert {
        "lifecycle_status",
        "truth_status",
        "approval_status",
        "source_refs",
        "evidence_refs",
        "relationship_refs",
        "metadata",
    } <= set(object_schema["required"])
    assert object_schema["properties"]["truth_status"]["enum"] == [
        "asserted",
        "inferred",
        "assumed",
        "verified",
        "disputed",
    ]


def test_relationship_schema_is_first_class_and_not_embedded_only() -> None:
    schema = _schema(RELATIONSHIP_SCHEMA)

    assert schema["title"] == "AI Enterprise Relationship v0.1"
    assert schema["properties"]["type"]["const"] == "relationship"
    assert {"source_object_id", "target_object_id", "relationship_type"} <= set(
        schema["required"]
    )
    assert schema["properties"]["relationship_type"]["enum"] == [
        relationship_type.value for relationship_type in RelationshipType
    ]


def test_validation_finding_schema_declares_categories_and_blocking_flag() -> None:
    schema = _schema(VALIDATION_FINDING_SCHEMA)

    assert schema["title"] == "AI Enterprise Validation Finding v0.1"
    assert {"rule_id", "category", "blocking", "suggested_action"} <= set(
        schema["required"]
    )
    assert "recommendation" in schema["properties"]["severity"]["enum"]
    assert "traceability" in schema["properties"]["category"]["enum"]


def test_ai_operation_schema_requires_reviewable_hash_bound_provenance() -> None:
    schema = _schema(AI_OPERATION_SCHEMA)

    assert schema["title"] == "AI Enterprise AI Operation Provenance v0.1"
    assert schema["additionalProperties"] is False
    assert {"model_provider", "model_name", "prompt_version", "operation_sha256"} <= set(
        schema["required"]
    )
    assert schema["properties"]["review_required"]["const"] is True
    assert "candidate_requirement_generation" in schema["properties"]["operation_type"]["enum"]


def test_runtime_models_emit_fields_required_by_r2_contracts() -> None:
    manifest = AepmManifest.model_validate_json(EXAMPLE.read_text(encoding="utf-8"))
    model = compile_aepm(manifest).model_dump(mode="json")
    first_object = model["objects"][0]
    first_relationship = model["relationships"][0]
    invalid = json.loads(INVALID_EXAMPLE.read_text(encoding="utf-8"))
    finding = AepmValidationEngine().validate(invalid).findings[0].model_dump(mode="json")

    assert {"lifecycle_status", "truth_status", "approval_status"} <= set(first_object)
    assert "relationship_refs" in first_object
    assert "relationships" not in first_object
    assert first_relationship["type"] == "relationship"
    assert {"rule_id", "category", "blocking", "suggested_action"} <= set(finding)


def test_r2_schemas_validate_runtime_and_sample_documents() -> None:
    aepm_schema = _schema(AEP_SCHEMA)
    aeir_schema = _schema(AEIR_SCHEMA)
    relationship_schema = _schema(RELATIONSHIP_SCHEMA)
    validation_finding_schema = _schema(VALIDATION_FINDING_SCHEMA)
    ai_operation_schema = _schema(AI_OPERATION_SCHEMA)
    workflow_schema = _schema(HUMAN_REVIEW_WORKFLOW_SCHEMA)
    manifest = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    invalid_manifest = json.loads(INVALID_EXAMPLE.read_text(encoding="utf-8"))
    model = compile_aepm(AepmManifest.model_validate(manifest)).model_dump(mode="json")
    operation = AiOperationRecord.model_construct(
        model_provider="openai",
        model_name="gpt-5.1",
        operation_type="extraction",
        prompt_version="aepm-extractor-0.1.3",
        generated_at="2026-08-05T00:00:00Z",
        input_source_refs=("client-manifest:sample",),
        review_required=True,
        operation_sha256="0" * 64,
    )
    operation = AiOperationRecord.model_validate(
        {
            **operation.model_dump(mode="json"),
            "operation_sha256": _operation_hash(operation),
        }
    )
    workflow = {
        "schema_version": "human-review-workflow-0.1",
        "states": [state.value for state in HumanReviewWorkflowState],
        "transitions": [
            {"from": "extracted", "to": "validation_pending"},
            {"from": "validation_pending", "to": "clarification_required"},
            {"from": "validation_pending", "to": "client_review"},
            {"from": "clarification_required", "to": "client_review"},
            {"from": "client_review", "to": "approved"},
            {"from": "approved", "to": "ready_for_compilation"},
        ],
        "artifact_compilation_rule": {
            "approved_snapshot_required": True,
            "draft_artifacts_allowed_when_marked": True,
        },
    }
    aeir_schema["properties"]["relationships"]["items"] = relationship_schema

    _assert_valid(aepm_schema, manifest)
    assert list(Draft202012Validator(aepm_schema).iter_errors(invalid_manifest))
    _assert_valid(aeir_schema, model)
    _assert_valid(relationship_schema, model["relationships"][0])
    _assert_valid(
        validation_finding_schema,
        AepmValidationEngine().validate(invalid_manifest).findings[0].model_dump(mode="json"),
    )
    _assert_valid(ai_operation_schema, operation.model_dump(mode="json"))
    _assert_valid(workflow_schema, workflow)


def test_deterministic_ai_boundary_is_explicitly_specified() -> None:
    contract = DETERMINISTIC_AI_BOUNDARY.read_text(encoding="utf-8")

    assert "Structural authority belongs to deterministic application code" in contract
    assert "schema validation" in contract
    assert "traceability coverage" in contract
    assert "extracting candidate fields from prose" in contract
    assert "must never be the final authority" in contract
    assert "approval" in contract


def test_human_review_workflow_contract_matches_runtime_transitions() -> None:
    schema = json.loads(HUMAN_REVIEW_WORKFLOW_SCHEMA.read_text(encoding="utf-8"))
    states = [item["const"] for item in schema["properties"]["states"]["prefixItems"]]
    expected_states = [state.value for state in HumanReviewWorkflowState]
    transition_values = {
        (transition[0].value, transition[1].value)
        for transition in (
            validate_human_review_transition("extracted", "validation_pending"),
            validate_human_review_transition("validation_pending", "clarification_required"),
            validate_human_review_transition("validation_pending", "client_review"),
            validate_human_review_transition("clarification_required", "client_review"),
            validate_human_review_transition("client_review", "approved"),
            validate_human_review_transition("approved", "ready_for_compilation"),
        )
    }

    assert schema["title"] == "AI Enterprise Human Review Workflow v0.1"
    assert states == expected_states
    assert ("approved", "ready_for_compilation") in transition_values
    assert schema["properties"]["artifact_compilation_rule"]["properties"][
        "approved_snapshot_required"
    ]["const"] is True


def test_human_review_workflow_rejects_skipped_approval_transition() -> None:
    try:
        validate_human_review_transition("client_review", "ready_for_compilation")
    except ValueError as exc:
        assert "invalid human review transition" in str(exc)
    else:  # pragma: no cover - defensive assertion for explicit contract behavior
        raise AssertionError("skipped approval transition was accepted")


def test_mvp_non_goals_exclude_expansive_v01_behaviors() -> None:
    non_goals = MVP_NON_GOALS.read_text(encoding="utf-8")

    for phrase in (
        "automatic deployment",
        "production-ready code generation",
        "autonomous approval",
        "unconstrained chat-based editing",
        "real-time multi-user collaboration",
        "semantic merge conflict resolution",
        "arbitrary user-defined ontologies",
        "automatic regulatory compliance claims",
        "broad domain-pack support",
    ):
        assert phrase in non_goals
