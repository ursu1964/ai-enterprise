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
    items: tuple[InterpretationItem, ...]
    batch_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_identity(self) -> InterpretationBatch:
        if self.batch_sha256 != _batch_hash(
            self.source_sha256, self.model_output_sha256, self.items
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
    *, source: dict[str, Any] | str, normalized_output: dict[str, Any], model_output_sha256: str
) -> InterpretationBatch:
    output = ModelInterpretationOutput.model_validate(normalized_output)
    if model_output_sha256 != hash_json(normalized_output):
        raise ValueError("model output hash does not match normalized output")
    source_sha256 = hash_text(source) if isinstance(source, str) else specification_hash(source)
    items = tuple(sorted(output.items, key=lambda item: item.id))
    return InterpretationBatch(
        source_sha256=source_sha256,
        model_output_sha256=model_output_sha256,
        items=items,
        batch_sha256=_batch_hash(source_sha256, model_output_sha256, items),
    )


def _batch_hash(
    source_sha256: str, model_output_sha256: str, items: tuple[InterpretationItem, ...]
) -> str:
    return specification_hash(
        {
            "schema_version": "aepm-interpretation-0.1",
            "source_sha256": source_sha256,
            "model_output_sha256": model_output_sha256,
            "items": [item.model_dump(mode="json") for item in items],
        }
    )
