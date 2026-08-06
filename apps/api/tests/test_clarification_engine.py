import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_enterprise.domain.aeir import compile_aepm
from ai_enterprise.domain.aepm import AepmManifest
from ai_enterprise.domain.aepm_interpretation import (
    ModelInterpretationOutput,
    finalize_interpretation,
)
from ai_enterprise.domain.aepm_validation import AepmValidationEngine
from ai_enterprise.domain.agent_runtime.output import StructuredOutputValidator
from ai_enterprise.domain.clarification import (
    CanonicalCorrection,
    ClarificationAnswer,
    ClarificationReport,
    HumanReviewDecision,
    apply_answer_batch,
    apply_human_review_decisions,
    build_answer_batch,
    generate_clarification_report,
)

ROOT = Path(__file__).resolve().parents[3]


def sample() -> dict[str, object]:
    return json.loads(
        (ROOT / "examples/sample-project/aepm-0.1.json").read_text(encoding="utf-8")
    )


def interpretation():
    raw = json.dumps(
        {
            "schema_version": "aepm-interpretation-output-0.1",
            "items": [
                {
                    "id": "AI-001",
                    "task": "ambiguity",
                    "content": "Which retention period applies?",
                    "rationale": "Two periods are plausible.",
                    "status": "inferred",
                    "confidence": 0.7,
                    "source_references": ["client-prose/2"],
                    "target_object_ids": ["RULE-001"],
                },
                {
                    "id": "AI-002",
                    "task": "classification",
                    "content": "Hosting is assumed to be regional.",
                    "rationale": "No hosting decision is approved.",
                    "status": "unverified",
                    "confidence": 0.6,
                    "source_references": ["client-prose/4"],
                    "classification": "assumption",
                },
            ],
        }
    )
    validation = StructuredOutputValidator(ModelInterpretationOutput).validate(raw)
    assert validation.normalized_output is not None
    assert validation.output_hash is not None
    return finalize_interpretation(
        source="client prose",
        normalized_output=validation.normalized_output,
        model_output_sha256=validation.output_hash,
    )


def test_clean_input_has_all_five_empty_sections_and_stable_hash() -> None:
    validation = AepmValidationEngine().validate(sample())
    first = generate_clarification_report(validation)
    second = generate_clarification_report(validation)

    assert all(not questions for _section, questions in first.sections())
    assert first == second


def test_findings_and_interpretations_are_classified_with_provenance() -> None:
    document = sample()
    document["business_outcomes"][0]["indicators"] = []  # type: ignore[index]
    document["constraints"][0]["description"] = "TBD hosting"  # type: ignore[index]
    report = generate_clarification_report(
        AepmValidationEngine().validate(document), interpretation()
    )

    assert report.critical_blockers
    assert report.important_ambiguities
    assert report.unverified_assumptions
    assert report.optional_enhancements == ()
    assert all(question.source_references for question in report.questions())


def test_answer_batch_updates_only_scoped_object_and_preserves_old_model() -> None:
    manifest = AepmManifest.model_validate(sample())
    model = compile_aepm(manifest)
    report = generate_clarification_report(
        AepmValidationEngine().validate(sample()), interpretation()
    )
    question = report.important_ambiguities[0]
    original = next(item for item in model.objects if item.id == "RULE-001")
    answer = ClarificationAnswer(
        question_id=question.id,
        response="Retain records for seven years.",
        resolution="answered",
        rationale="Confirmed by the records owner.",
        corrections=(
            CanonicalCorrection(
                target_object_id="RULE-001",
                field="description",
                proposed_value="Retain audit records for seven years.",
            ),
        ),
    )
    batch = build_answer_batch(
        report=report, base_model=model, respondent_id="records-owner", answers=(answer,)
    )
    updated = apply_answer_batch(report=report, base_model=model, batch=batch)
    changed = next(item for item in updated.objects if item.id == "RULE-001")

    assert original.description != changed.description
    assert next(item for item in model.objects if item.id == "RULE-001") == original
    assert changed.status == "approved"
    assert changed.source.kind == "human_clarification"
    assert updated.model_sha256 != model.model_sha256


def test_answer_batch_can_patch_structured_attributes() -> None:
    document = sample()
    document["business_outcomes"][0]["description"] = "TBD retention savings"  # type: ignore[index]
    model = compile_aepm(AepmManifest.model_validate(document))
    report = generate_clarification_report(AepmValidationEngine().validate(document))
    question = next(
        item
        for item in report.unverified_assumptions
        if "OUT-001" in item.target_object_ids
    )
    answer = ClarificationAnswer(
        question_id=question.id,
        response="Savings will be measured by cycle-time reduction and avoided rework.",
        resolution="answered",
        rationale="Confirmed with the operations sponsor.",
        corrections=(
            CanonicalCorrection(
                target_object_id="OUT-001",
                field="attributes",
                attribute_key="indicators",
                proposed_value=["Cycle-time reduction", "Avoided rework"],
            ),
        ),
    )

    batch = build_answer_batch(
        report=report, base_model=model, respondent_id="operations-sponsor", answers=(answer,)
    )
    updated = apply_answer_batch(report=report, base_model=model, batch=batch)
    changed = next(item for item in updated.objects if item.id == "OUT-001")

    assert changed.attributes["indicators"] == ["Cycle-time reduction", "Avoided rework"]
    assert changed.status == "approved"
    assert updated.model_sha256 != model.model_sha256


def test_human_review_decisions_approve_correct_and_reject_canonical_objects() -> None:
    model = compile_aepm(AepmManifest.model_validate(sample()))

    reviewed = apply_human_review_decisions(
        base_model=model,
        reviewer_id="client-reviewer",
        decisions=(
            HumanReviewDecision(
                object_id="CAP-001",
                decision="approved",
                rationale="Confirmed by the capability owner.",
            ),
            HumanReviewDecision(
                object_id="RULE-001",
                decision="corrected",
                rationale="Policy wording was clarified.",
                description="Only authenticated customers may view their own request details.",
            ),
            HumanReviewDecision(
                object_id="DEC-001",
                decision="rejected",
                rationale="Frontend technology choice is not approved yet.",
            ),
        ),
    )

    approved = next(item for item in reviewed.objects if item.id == "CAP-001")
    corrected = next(item for item in reviewed.objects if item.id == "RULE-001")
    rejected = next(item for item in reviewed.objects if item.id == "DEC-001")

    assert approved.status == "approved"
    assert corrected.status == "approved"
    assert corrected.description == (
        "Only authenticated customers may view their own request details."
    )
    assert rejected.status == "rejected"
    assert corrected.source.kind == "human_clarification"
    assert "reviewer:client-reviewer" in corrected.source.evidence_references
    assert reviewed.model_sha256 != model.model_sha256


def test_unknown_stale_and_out_of_scope_answers_fail_closed() -> None:
    model = compile_aepm(AepmManifest.model_validate(sample()))
    report = generate_clarification_report(
        AepmValidationEngine().validate(sample()), interpretation()
    )
    question = report.important_ambiguities[0]
    out_of_scope = ClarificationAnswer(
        question_id=question.id,
        response="Change a different object.",
        resolution="answered",
        rationale="Invalid scope test.",
        corrections=(
            CanonicalCorrection(
                target_object_id="PROJ-001", field="name", proposed_value="Changed"
            ),
        ),
    )
    batch = build_answer_batch(
        report=report, base_model=model, respondent_id="reviewer", answers=(out_of_scope,)
    )

    with pytest.raises(ValueError, match="exceeds"):
        apply_answer_batch(report=report, base_model=model, batch=batch)
    with pytest.raises(ValueError, match="unknown"):
        build_answer_batch(
            report=report,
            base_model=model,
            respondent_id="reviewer",
            answers=(out_of_scope.model_copy(update={"question_id": "QUE-000000000000"}),),
        )
    stale = batch.model_copy(update={"base_model_sha256": "0" * 64})
    with pytest.raises(ValueError, match="stale"):
        apply_answer_batch(report=report, base_model=model, batch=stale)


def test_report_hash_tampering_is_rejected() -> None:
    report = generate_clarification_report(AepmValidationEngine().validate(sample()))

    with pytest.raises(ValidationError, match="report hash"):
        ClarificationReport.model_validate(
            {
                **copy.deepcopy(report.model_dump(mode="json")),
                "validation_report_sha256": "0" * 64,
            }
        )
