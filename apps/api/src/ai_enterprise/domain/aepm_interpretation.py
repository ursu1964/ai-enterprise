from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai_enterprise.domain.agent_runtime.output import StructuredOutputValidator
from ai_enterprise.domain.hashing import hash_json, hash_text
from ai_enterprise.domain.specification.kernel import specification_hash


class InterpretationValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InterpretationTask(StrEnum):
    EXTRACTED_FIELD = "extracted_field"
    AMBIGUITY = "ambiguity"
    CLARIFICATION_QUESTION = "clarification_question"
    CLASSIFICATION = "classification"
    PROBABLE_CONTRADICTION = "probable_contradiction"
    CANDIDATE_REQUIREMENT = "candidate_requirement"


class InterpretationStatus(StrEnum):
    PROPOSED = "proposed"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    APPROVED = "approved"
    REJECTED = "rejected"


class StatementClassification(StrEnum):
    FACT = "fact"
    ASSUMPTION = "assumption"
    RECOMMENDATION = "recommendation"


class AiOperationRecord(InterpretationValue):
    schema_version: Literal["ai-operation-0.1"] = "ai-operation-0.1"
    model_provider: str = Field(min_length=1, max_length=200)
    model_name: str = Field(min_length=1, max_length=200)
    operation_type: Literal[
        "extraction",
        "ambiguity_detection",
        "classification",
        "contradiction_detection",
        "question_drafting",
        "candidate_requirement_generation",
    ]
    prompt_version: str = Field(min_length=1, max_length=80)
    output_schema_version: Literal["aepm-interpretation-output-0.1"] = (
        "aepm-interpretation-output-0.1"
    )
    aeir_schema_version: Literal["AEIR-0.1"] = "AEIR-0.1"
    generated_at: str = Field(min_length=1, max_length=40)
    input_source_refs: tuple[str, ...] = Field(min_length=1)
    review_required: bool = True
    operation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_operation_hash(self) -> AiOperationRecord:
        if not self.review_required:
            raise ValueError("AI interpretation operations must require human review")
        if self.operation_sha256 != _operation_hash(self):
            raise ValueError("AI operation hash does not match canonical content")
        return self


class InterpretationItem(InterpretationValue):
    id: str = Field(pattern=r"^AI-[0-9]{3}$")
    task: InterpretationTask
    content: str = Field(min_length=1, max_length=4000)
    rationale: str = Field(min_length=1, max_length=2000)
    status: Literal[
        InterpretationStatus.PROPOSED,
        InterpretationStatus.INFERRED,
        InterpretationStatus.UNVERIFIED,
    ]
    confidence: float = Field(ge=0, le=1)
    source_references: tuple[str, ...] = Field(min_length=1)
    target_object_ids: tuple[str, ...] = ()
    field_name: str | None = Field(default=None, min_length=1, max_length=200)
    classification: StatementClassification | None = None

    @model_validator(mode="after")
    def validate_task_shape(self) -> InterpretationItem:
        if self.task is InterpretationTask.EXTRACTED_FIELD and self.field_name is None:
            raise ValueError("extracted fields require field_name")
        if self.task is not InterpretationTask.EXTRACTED_FIELD and self.field_name is not None:
            raise ValueError("field_name is only valid for extracted fields")
        if self.task is InterpretationTask.CLASSIFICATION and self.classification is None:
            raise ValueError("classification tasks require a classification")
        if self.task is not InterpretationTask.CLASSIFICATION and self.classification is not None:
            raise ValueError("classification is only valid for classification tasks")
        if (
            self.task is InterpretationTask.PROBABLE_CONTRADICTION
            and len(self.source_references) < 2
        ):
            raise ValueError("probable contradictions require at least two sources")
        return self


class ModelInterpretationOutput(InterpretationValue):
    schema_version: Literal["aepm-interpretation-output-0.1"]
    items: tuple[InterpretationItem, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self) -> ModelInterpretationOutput:
        identifiers = [item.id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("interpretation item identifiers must be unique")
        return self


class InterpretationBatch(InterpretationValue):
    schema_version: Literal["aepm-interpretation-0.1"] = "aepm-interpretation-0.1"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ai_operation: AiOperationRecord
    items: tuple[InterpretationItem, ...]
    batch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> InterpretationBatch:
        if self.batch_sha256 != _batch_hash(
            self.source_sha256, self.model_output_sha256, self.ai_operation, self.items
        ):
            raise ValueError("interpretation batch hash does not match canonical content")
        return self


class InterpretationReviewDecision(InterpretationValue):
    item_id: str = Field(pattern=r"^AI-[0-9]{3}$")
    decision: Literal[InterpretationStatus.APPROVED, InterpretationStatus.REJECTED]
    reviewer_id: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=2000)


def interpretation_output_validator() -> StructuredOutputValidator:
    return StructuredOutputValidator(ModelInterpretationOutput)


def finalize_interpretation(
    *,
    source: dict[str, Any] | str,
    normalized_output: dict[str, Any],
    model_output_sha256: str,
    ai_operation: AiOperationRecord | dict[str, Any] | None = None,
) -> InterpretationBatch:
    output = ModelInterpretationOutput.model_validate(normalized_output)
    if model_output_sha256 != hash_json(normalized_output):
        raise ValueError("model output hash does not match normalized output")
    source_sha256 = hash_text(source) if isinstance(source, str) else specification_hash(source)
    items = tuple(sorted(output.items, key=lambda item: item.id))
    operation = (
        _default_operation(source_sha256)
        if ai_operation is None
        else AiOperationRecord.model_validate(ai_operation)
    )
    return InterpretationBatch(
        source_sha256=source_sha256,
        model_output_sha256=model_output_sha256,
        ai_operation=operation,
        items=items,
        batch_sha256=_batch_hash(source_sha256, model_output_sha256, operation, items),
    )


def _batch_hash(
    source_sha256: str,
    model_output_sha256: str,
    ai_operation: AiOperationRecord,
    items: tuple[InterpretationItem, ...],
) -> str:
    return specification_hash(
        {
            "schema_version": "aepm-interpretation-0.1",
            "source_sha256": source_sha256,
            "model_output_sha256": model_output_sha256,
            "ai_operation": ai_operation.model_dump(mode="json"),
            "items": [item.model_dump(mode="json") for item in items],
        }
    )


def _default_operation(source_sha256: str) -> AiOperationRecord:
    provisional = AiOperationRecord.model_construct(
        model_provider="unrecorded-provider",
        model_name="unrecorded-model",
        operation_type="extraction",
        prompt_version="aepm-interpretation-0.1",
        generated_at="1970-01-01T00:00:00Z",
        input_source_refs=(f"source:{source_sha256}",),
        review_required=True,
        operation_sha256="0" * 64,
    )
    return AiOperationRecord(
        model_provider=provisional.model_provider,
        model_name=provisional.model_name,
        operation_type=provisional.operation_type,
        prompt_version=provisional.prompt_version,
        generated_at=provisional.generated_at,
        input_source_refs=provisional.input_source_refs,
        review_required=True,
        operation_sha256=_operation_hash(provisional),
    )


def _operation_hash(operation: AiOperationRecord) -> str:
    return specification_hash(operation.model_dump(mode="json", exclude={"operation_sha256"}))
