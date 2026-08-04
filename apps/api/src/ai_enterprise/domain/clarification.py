from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.aeir import (
    AeirProjectModel,
    AeirSource,
    AeirStatus,
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
    field: Literal["name", "description"]
    proposed_value: str = Field(min_length=1, max_length=4000)


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
                correction.field: correction.proposed_value,
                "status": AeirStatus.APPROVED,
                "confidence": 1.0,
                "source": AeirSource(
                    kind="human_clarification",
                    reference=f"question:{answer.question_id}",
                    manifest_sha256=base_model.source_manifest_sha256,
                    evidence_references=evidence,
                ),
            }
            objects[current.id] = current.model_copy(update=changes)
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


def _report_hash(report: ClarificationReport) -> str:
    return specification_hash(report.model_dump(mode="json", exclude={"report_sha256"}))


def _answer_hash(batch: ClarificationAnswerBatch) -> str:
    return specification_hash(batch.model_dump(mode="json", exclude={"answer_batch_sha256"}))
