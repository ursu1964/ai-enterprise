import json

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aepm_interpretation import (
    InterpretationBatch,
    InterpretationReviewDecision,
    finalize_interpretation,
    interpretation_output_validator,
)


def model_output() -> dict[str, object]:
    return {
        "schema_version": "aepm-interpretation-output-0.1",
        "items": [
            {
                "id": "AI-002",
                "task": "probable_contradiction",
                "content": "Retention expectations may conflict.",
                "rationale": "The two source statements specify opposing retention behavior.",
                "status": "inferred",
                "confidence": 0.81,
                "source_references": ["client-prose/paragraph-2", "client-prose/paragraph-7"],
                "target_object_ids": ["RULE-001", "RULE-002"],
            },
            {
                "id": "AI-001",
                "task": "classification",
                "content": "The service is expected to support 500 concurrent users.",
                "rationale": "The prose describes an expectation without approved evidence.",
                "status": "unverified",
                "confidence": 0.74,
                "source_references": ["client-prose/paragraph-3"],
                "classification": "assumption",
            },
        ],
    }


def test_structured_output_is_validated_and_finalized_deterministically() -> None:
    raw = json.dumps(model_output())
    validation = interpretation_output_validator().validate(raw)

    assert validation.valid is True
    assert validation.normalized_output is not None
    assert validation.output_hash is not None
    first = finalize_interpretation(
        source="Client prose",
        normalized_output=validation.normalized_output,
        model_output_sha256=validation.output_hash,
    )
    second = finalize_interpretation(
        source="Client prose",
        normalized_output=validation.normalized_output,
        model_output_sha256=validation.output_hash,
    )

    assert [item.id for item in first.items] == ["AI-001", "AI-002"]
    assert first == second


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_model_cannot_self_approve_or_reject(status: str) -> None:
    output = model_output()
    output["items"][0]["status"] = status  # type: ignore[index]

    validation = interpretation_output_validator().validate(json.dumps(output))

    assert validation.valid is False
    assert validation.findings[0]["code"] == "OUT-002"


def test_task_specific_evidence_rules_fail_closed() -> None:
    output = model_output()
    output["items"][0]["source_references"] = ["client-prose/paragraph-2"]  # type: ignore[index]

    validation = interpretation_output_validator().validate(json.dumps(output))

    assert validation.valid is False


def test_human_review_decision_is_separate_from_model_output() -> None:
    decision = InterpretationReviewDecision(
        item_id="AI-001",
        decision="approved",
        reviewer_id="reviewer@example.test",
        rationale="Confirmed against the signed project brief.",
    )

    assert decision.decision == "approved"


def test_interpretation_batch_detects_tampering() -> None:
    validation = interpretation_output_validator().validate(json.dumps(model_output()))
    assert validation.normalized_output is not None
    assert validation.output_hash is not None
    batch = finalize_interpretation(
        source={"prose": "Client prose"},
        normalized_output=validation.normalized_output,
        model_output_sha256=validation.output_hash,
    )

    with pytest.raises(ValidationError, match="batch hash"):
        InterpretationBatch.model_validate(
            {**batch.model_dump(mode="json"), "source_sha256": "0" * 64}
        )


def test_finalization_rejects_an_unbound_model_output_hash() -> None:
    validation = interpretation_output_validator().validate(json.dumps(model_output()))
    assert validation.normalized_output is not None

    with pytest.raises(ValueError, match="model output hash"):
        finalize_interpretation(
            source="Client prose",
            normalized_output=validation.normalized_output,
            model_output_sha256="0" * 64,
        )
