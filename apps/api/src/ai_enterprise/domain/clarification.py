from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import (
    AeirProjectModel,
    AeirSource,
    AeirStatus,
    ApprovalStatus,
    TruthStatus,
    rebuild_aeir,
)
from ai_enterprise.domain.aepm_interpretation import (
    InterpretationBatch,
    InterpretationTask,
    StatementClassification,
)
from ai_enterprise.domain.aepm_validation import AepmValidationReport
from ai_enterprise.domain.specification.kernel import specification_hash


class ClarificationValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ClarificationSection(StrEnum):
    CRITICAL_BLOCKERS = "critical_blockers"
    IMPORTANT_AMBIGUITIES = "important_ambiguities"
    UNVERIFIED_ASSUMPTIONS = "unverified_assumptions"
    RECOMMENDED_IMPROVEMENTS = "recommended_improvements"
    OPTIONAL_ENHANCEMENTS = "optional_enhancements"


AuthorityStatus = Literal["deterministic", "proposed", "inferred", "unverified"]


class HumanReviewWorkflowState(StrEnum):
    EXTRACTED = "extracted"
    VALIDATION_PENDING = "validation_pending"
    CLARIFICATION_REQUIRED = "clarification_required"
    CLIENT_REVIEW = "client_review"
    APPROVED = "approved"
    READY_FOR_COMPILATION = "ready_for_compilation"


ALLOWED_HUMAN_REVIEW_TRANSITIONS: frozenset[
    tuple[HumanReviewWorkflowState, HumanReviewWorkflowState]
] = frozenset(
    {
        (
            HumanReviewWorkflowState.EXTRACTED,
            HumanReviewWorkflowState.VALIDATION_PENDING,
        ),
        (
            HumanReviewWorkflowState.VALIDATION_PENDING,
            HumanReviewWorkflowState.CLARIFICATION_REQUIRED,
        ),
        (
            HumanReviewWorkflowState.VALIDATION_PENDING,
            HumanReviewWorkflowState.CLIENT_REVIEW,
        ),
        (
            HumanReviewWorkflowState.CLARIFICATION_REQUIRED,
            HumanReviewWorkflowState.CLIENT_REVIEW,
        ),
        (
            HumanReviewWorkflowState.CLIENT_REVIEW,
            HumanReviewWorkflowState.APPROVED,
        ),
        (
            HumanReviewWorkflowState.APPROVED,
            HumanReviewWorkflowState.READY_FOR_COMPILATION,
        ),
    }
)


def validate_human_review_transition(
    current: HumanReviewWorkflowState | str, next_state: HumanReviewWorkflowState | str
) -> tuple[HumanReviewWorkflowState, HumanReviewWorkflowState]:
    current_state = HumanReviewWorkflowState(current)
    target_state = HumanReviewWorkflowState(next_state)
    if (current_state, target_state) not in ALLOWED_HUMAN_REVIEW_TRANSITIONS:
        raise ValueError(
            f"invalid human review transition: {current_state.value} -> {target_state.value}"
        )
    return current_state, target_state


class ClarificationQuestion(ClarificationValue):
    id: str = Field(pattern=r"^QUE-[0-9A-F]{12}$")
    section: ClarificationSection
    prompt: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)
    required: bool
    authority_status: AuthorityStatus
    source_references: tuple[str, ...] = Field(min_length=1)
    target_object_ids: tuple[str, ...] = ()
    confidence: float | None = Field(default=None, ge=0, le=1)


class ClarificationReport(ClarificationValue):
    schema_version: Literal["clarification-report-0.1"] = "clarification-report-0.1"
    classifier_version: Literal["clarification-classifier-0.1"] = "clarification-classifier-0.1"
    validation_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    interpretation_batch_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    critical_blockers: tuple[ClarificationQuestion, ...] = ()
    important_ambiguities: tuple[ClarificationQuestion, ...] = ()
    unverified_assumptions: tuple[ClarificationQuestion, ...] = ()
    recommended_improvements: tuple[ClarificationQuestion, ...] = ()
    optional_enhancements: tuple[ClarificationQuestion, ...] = ()
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_report(self) -> ClarificationReport:
        identifiers: list[str] = []
        for section, questions in self.sections():
            if tuple(sorted(questions, key=lambda item: item.id)) != questions:
                raise ValueError("clarification questions must be canonically ordered")
            if any(item.section is not section for item in questions):
                raise ValueError("clarification question is stored in the wrong section")
            identifiers.extend(item.id for item in questions)
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("clarification question identifiers must be unique")
        if self.report_sha256 != _report_hash(self):
            raise ValueError("clarification report hash does not match canonical content")
        return self

    def sections(
        self,
    ) -> tuple[tuple[ClarificationSection, tuple[ClarificationQuestion, ...]], ...]:
        return (
            (ClarificationSection.CRITICAL_BLOCKERS, self.critical_blockers),
            (ClarificationSection.IMPORTANT_AMBIGUITIES, self.important_ambiguities),
            (ClarificationSection.UNVERIFIED_ASSUMPTIONS, self.unverified_assumptions),
            (ClarificationSection.RECOMMENDED_IMPROVEMENTS, self.recommended_improvements),
            (ClarificationSection.OPTIONAL_ENHANCEMENTS, self.optional_enhancements),
        )

    def questions(self) -> tuple[ClarificationQuestion, ...]:
        return tuple(question for _section, questions in self.sections() for question in questions)


class CanonicalCorrection(ClarificationValue):
    target_object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    field: Literal["name", "description", "attributes"]
    proposed_value: Any = Field()
    attribute_key: str | None = Field(
        default=None, pattern=r"^[a-z][a-z0-9_]{1,79}$"
    )

    @model_validator(mode="after")
    def validate_correction(self) -> CanonicalCorrection:
        if self.field == "attributes":
            if self.attribute_key is None:
                raise ValueError("attribute corrections require an attribute_key")
        elif self.attribute_key is not None:
            raise ValueError("attribute_key is only valid for attribute corrections")
        if self.field in {"name", "description"} and not isinstance(self.proposed_value, str):
            raise ValueError("name and description corrections require string values")
        return self


class ClarificationAnswer(ClarificationValue):
    question_id: str = Field(pattern=r"^QUE-[0-9A-F]{12}$")
    response: str = Field(min_length=1, max_length=4000)
    resolution: Literal["answered", "waived"]
    rationale: str = Field(min_length=1, max_length=2000)
    corrections: tuple[CanonicalCorrection, ...] = ()

    @model_validator(mode="after")
    def validate_resolution(self) -> ClarificationAnswer:
        if self.resolution == "waived" and self.corrections:
            raise ValueError("waived questions cannot carry canonical corrections")
        return self


class ClarificationAnswerBatch(ClarificationValue):
    schema_version: Literal["clarification-answers-0.1"] = "clarification-answers-0.1"
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_model_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    respondent_id: str = Field(min_length=1, max_length=200)
    answers: tuple[ClarificationAnswer, ...]
    answer_batch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_batch(self) -> ClarificationAnswerBatch:
        identifiers = [item.question_id for item in self.answers]
        if identifiers != sorted(identifiers) or len(identifiers) != len(set(identifiers)):
            raise ValueError("clarification answers must be unique and canonically ordered")
        if self.answer_batch_sha256 != _answer_hash(self):
            raise ValueError("clarification answer hash does not match canonical content")
        return self


class HumanReviewDecision(ClarificationValue):
    object_id: str = Field(pattern=r"^[A-Z][A-Z0-9-]{2,63}$")
    decision: Literal["approved", "rejected", "corrected"]
    rationale: str = Field(min_length=1, max_length=2000)
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1, max_length=4000)

    @model_validator(mode="after")
    def validate_decision(self) -> HumanReviewDecision:
        if self.decision == "corrected" and self.name is None and self.description is None:
            raise ValueError("corrected review decisions must include a name or description")
        if self.decision == "rejected" and (self.name is not None or self.description is not None):
            raise ValueError("rejected review decisions cannot carry corrected fields")
        return self


_VALIDATION_CLASSIFICATION: dict[str, ClarificationSection] = {
    "AEPM-VAL-000": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-001": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-002": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-003": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-004": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-005": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-006": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-007": ClarificationSection.CRITICAL_BLOCKERS,
    "AEPM-VAL-008": ClarificationSection.IMPORTANT_AMBIGUITIES,
    "AEPM-VAL-009": ClarificationSection.UNVERIFIED_ASSUMPTIONS,
    "AEPM-VAL-010": ClarificationSection.RECOMMENDED_IMPROVEMENTS,
    "AEPM-VAL-011": ClarificationSection.CRITICAL_BLOCKERS,
}


def generate_clarification_report(
    validation: AepmValidationReport, interpretation: InterpretationBatch | None = None
) -> ClarificationReport:
    grouped: dict[ClarificationSection, list[ClarificationQuestion]] = {
        section: [] for section in ClarificationSection
    }
    for finding in validation.findings:
        section = _VALIDATION_CLASSIFICATION[finding.code]
        source = f"validation:{finding.code}:{finding.path}"
        grouped[section].append(
            ClarificationQuestion(
                id=_question_id(source),
                section=section,
                prompt=(
                    f"Please resolve {finding.message.rstrip('.').casefold()} "
                    f"at {finding.path}."
                ),
                rationale=finding.message,
                required=section is ClarificationSection.CRITICAL_BLOCKERS,
                authority_status="deterministic",
                source_references=(source,),
                target_object_ids=finding.object_ids,
            )
        )
    if interpretation is not None:
        for item in interpretation.items:
            ai_section = _interpretation_section(item.task, item.classification)
            if ai_section is None:
                continue
            source = f"interpretation:{interpretation.batch_sha256}:{item.id}"
            prompt = (
                item.content
                if item.task is InterpretationTask.CLARIFICATION_QUESTION
                else f"Please confirm or correct: {item.content}"
            )
            grouped[ai_section].append(
                ClarificationQuestion(
                    id=_question_id(source),
                    section=ai_section,
                    prompt=prompt,
                    rationale=item.rationale,
                    required=False,
                    authority_status=cast(AuthorityStatus, item.status.value),
                    source_references=(source, *item.source_references),
                    target_object_ids=item.target_object_ids,
                    confidence=item.confidence,
                )
            )
    values = {
        section.value: tuple(sorted(questions, key=lambda item: item.id))
        for section, questions in grouped.items()
    }
    data: dict[str, Any] = {
        "validation_report_sha256": validation.report_sha256,
        "interpretation_batch_sha256": interpretation.batch_sha256 if interpretation else None,
        **values,
    }
    provisional = ClarificationReport.model_construct(**data, report_sha256="0" * 64)
    return ClarificationReport(**data, report_sha256=_report_hash(provisional))


def build_answer_batch(
    *,
    report: ClarificationReport,
    base_model: AeirProjectModel,
    respondent_id: str,
    answers: tuple[ClarificationAnswer, ...],
) -> ClarificationAnswerBatch:
    known = {item.id: item for item in report.questions()}
    if any(answer.question_id not in known for answer in answers):
        raise ValueError("clarification answer references an unknown question")
    ordered = tuple(sorted(answers, key=lambda item: item.question_id))
    provisional = ClarificationAnswerBatch.model_construct(
        report_sha256=report.report_sha256,
        base_model_sha256=base_model.model_sha256,
        respondent_id=respondent_id,
        answers=ordered,
        answer_batch_sha256="0" * 64,
    )
    return ClarificationAnswerBatch(
        report_sha256=report.report_sha256,
        base_model_sha256=base_model.model_sha256,
        respondent_id=respondent_id,
        answers=ordered,
        answer_batch_sha256=_answer_hash(provisional),
    )


def apply_answer_batch(
    *, report: ClarificationReport, base_model: AeirProjectModel, batch: ClarificationAnswerBatch
) -> AeirProjectModel:
    if batch.report_sha256 != report.report_sha256:
        raise ValueError("clarification answer batch is bound to a different report")
    if batch.base_model_sha256 != base_model.model_sha256:
        raise ValueError("clarification answer batch is stale for the canonical model")
    questions = {item.id: item for item in report.questions()}
    objects = {item.id: item for item in base_model.objects}
    for answer in batch.answers:
        question = questions.get(answer.question_id)
        if question is None:
            raise ValueError("clarification answer references an unknown question")
        for correction in answer.corrections:
            if correction.target_object_id not in question.target_object_ids:
                raise ValueError("clarification correction exceeds its question scope")
            current = objects.get(correction.target_object_id)
            if current is None:
                raise ValueError("clarification correction target is unavailable")
            evidence = (
                current.source.reference,
                f"clarification-report:{report.report_sha256}",
                f"clarification-answer:{batch.answer_batch_sha256}",
                f"respondent:{batch.respondent_id}",
            )
            changes: dict[str, Any] = {
                "status": AeirStatus.APPROVED,
                "truth_status": TruthStatus.VERIFIED,
                "approval_status": ApprovalStatus.APPROVED,
                "confidence": 1.0,
                "source": AeirSource(
                    kind="human_clarification",
                    reference=f"question:{answer.question_id}",
                    manifest_sha256=base_model.source_manifest_sha256,
                    evidence_references=evidence,
                ),
            }
            if correction.field == "attributes":
                attributes = dict(current.attributes)
                assert correction.attribute_key is not None
                attributes[correction.attribute_key] = correction.proposed_value
                changes["attributes"] = attributes
            else:
                changes[correction.field] = correction.proposed_value
            objects[current.id] = current.model_copy(update=changes)
    return rebuild_aeir(base_model, objects=tuple(objects[item.id] for item in base_model.objects))


def apply_human_review_decisions(
    *,
    base_model: AeirProjectModel,
    reviewer_id: str,
    decisions: tuple[HumanReviewDecision, ...],
) -> AeirProjectModel:
    if len({item.object_id for item in decisions}) != len(decisions):
        raise ValueError("human review decisions must target each AEIR object at most once")
    objects = {item.id: item for item in base_model.objects}
    for review in decisions:
        current = objects.get(review.object_id)
        if current is None:
            raise ValueError("human review decision target is unavailable")
        evidence = (
            current.source.reference,
            f"human-review:{review.decision}",
            f"reviewer:{reviewer_id}",
        )
        updates: dict[str, Any] = {
            "status": _review_status(review),
            "truth_status": (
                TruthStatus.DISPUTED if review.decision == "rejected" else TruthStatus.VERIFIED
            ),
            "approval_status": (
                ApprovalStatus.REJECTED
                if review.decision == "rejected"
                else ApprovalStatus.APPROVED
            ),
            "confidence": 1.0 if review.decision != "rejected" else current.confidence,
            "source": AeirSource(
                kind="human_clarification",
                reference=f"human-review:{review.object_id}",
                manifest_sha256=base_model.source_manifest_sha256,
                evidence_references=evidence,
            ),
        }
        if review.name is not None:
            updates["name"] = review.name
        if review.description is not None:
            updates["description"] = review.description
        objects[current.id] = current.model_copy(update=updates)
    return rebuild_aeir(base_model, objects=tuple(objects[item.id] for item in base_model.objects))


def _interpretation_section(
    task: InterpretationTask, classification: StatementClassification | None
) -> ClarificationSection | None:
    if task in {InterpretationTask.AMBIGUITY, InterpretationTask.CLARIFICATION_QUESTION}:
        return ClarificationSection.IMPORTANT_AMBIGUITIES
    if task is InterpretationTask.PROBABLE_CONTRADICTION:
        return ClarificationSection.IMPORTANT_AMBIGUITIES
    if (
        task is InterpretationTask.CLASSIFICATION
        and classification is StatementClassification.ASSUMPTION
    ):
        return ClarificationSection.UNVERIFIED_ASSUMPTIONS
    if task is InterpretationTask.EXTRACTED_FIELD:
        return ClarificationSection.UNVERIFIED_ASSUMPTIONS
    if task is InterpretationTask.CANDIDATE_REQUIREMENT or (
        task is InterpretationTask.CLASSIFICATION
        and classification is StatementClassification.RECOMMENDATION
    ):
        return ClarificationSection.RECOMMENDED_IMPROVEMENTS
    return None


def _question_id(source: str) -> str:
    return f"QUE-{hashlib.sha256(source.encode()).hexdigest()[:12].upper()}"


def _review_status(review: HumanReviewDecision) -> AeirStatus:
    if review.decision == "rejected":
        return AeirStatus.REJECTED
    return AeirStatus.APPROVED


def _report_hash(report: ClarificationReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_sha256"}))


def _answer_hash(batch: ClarificationAnswerBatch) -> str:
    return specification_hash(batch.model_dump(mode="json", exclude={"answer_batch_sha256"}))
