from __future__ import annotations

from pathlib import Path

from ai_enterprise.infrastructure.knowledge.models import (
    R4AiOperationFailureModel,
    R4AiOperationModel,
    R4AiProvenanceLinkModel,
    R4AiUsageRecordModel,
    R4CandidateObjectModel,
    R4CandidatePromotionModel,
    R4CandidateRelationshipModel,
    R4CandidateReviewModel,
    R4CandidateSourceLinkModel,
    R4CandidateValidationResultModel,
    R4ClarificationQuestionModel,
    R4EvaluationRecordModel,
    R4PromptVersionModel,
    R4SourceNormalizationModel,
    R4SourceSegmentModel,
    R4UncertaintyRecordModel,
)

ROOT = Path(__file__).resolve().parents[3]


def _has_unique_constraint(model: type, *columns: str) -> bool:
    expected = set(columns)
    return any(
        getattr(constraint, "columns", None) is not None
        and {column.name for column in constraint.columns} == expected
        for constraint in model.__table__.constraints
    )


def test_r4_storage_models_cover_interpretation_lifecycle_tables() -> None:
    assert R4SourceNormalizationModel.__table__.c.normalized_document.type.__class__.__name__ == (
        "JSONB"
    )
    assert R4SourceNormalizationModel.__table__.c.source_row_id.foreign_keys
    assert _has_unique_constraint(R4SourceSegmentModel, "project_id", "segment_id")
    assert _has_unique_constraint(R4PromptVersionModel, "prompt_id", "prompt_version")
    assert _has_unique_constraint(R4AiOperationModel, "project_id", "operation_id")
    assert _has_unique_constraint(R4AiUsageRecordModel, "operation_row_id")
    assert _has_unique_constraint(
        R4AiOperationFailureModel,
        "project_id",
        "operation_id",
        "retry_count",
    )
    assert _has_unique_constraint(R4CandidateObjectModel, "project_id", "candidate_id")
    assert _has_unique_constraint(
        R4CandidateRelationshipModel,
        "project_id",
        "candidate_id",
    )
    assert R4CandidateObjectModel.__table__.c.payload.type.__class__.__name__ == "JSONB"
    assert _has_unique_constraint(
        R4CandidateSourceLinkModel,
        "project_id",
        "candidate_id",
        "source_id",
        "segment_id",
    )
    assert R4CandidateValidationResultModel.__table__.c.result_hash.unique
    assert _has_unique_constraint(
        R4UncertaintyRecordModel,
        "project_id",
        "record_id",
        "record_type",
    )
    assert _has_unique_constraint(R4ClarificationQuestionModel, "project_id", "question_id")
    assert _has_unique_constraint(R4CandidateReviewModel, "project_id", "review_id")
    assert _has_unique_constraint(R4CandidatePromotionModel, "project_id", "candidate_id")
    assert _has_unique_constraint(
        R4AiProvenanceLinkModel,
        "project_id",
        "entity_type",
        "entity_id",
        "ai_operation_id",
    )
    assert _has_unique_constraint(R4EvaluationRecordModel, "case_id", "run_id")


def test_r4_migration_is_linear_and_declares_append_only_ai_records() -> None:
    migration = (
        ROOT / "migrations/versions/8c1d4e6f9a23_add_r4_ai_interpretation_records.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "5b8e1f7c3a29"' in migration
    for table in (
        "r4_source_normalizations",
        "r4_source_segments",
        "r4_prompt_versions",
        "r4_ai_operations",
        "r4_ai_usage_records",
        "r4_ai_operation_failures",
        "r4_candidate_objects",
        "r4_candidate_relationships",
        "r4_candidate_source_links",
        "r4_candidate_validation_results",
        "r4_uncertainty_records",
        "r4_clarification_questions",
        "r4_candidate_reviews",
        "r4_candidate_promotions",
        "r4_ai_provenance_links",
        "r4_evaluation_records",
    ):
        assert f'"{table}"' in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "postgresql.JSONB" in migration


def test_r4_aeir_alignment_migration_is_linear_and_idempotent() -> None:
    migration = (
        ROOT / "migrations/versions/1f2a3b4c5d6e_align_r4_aeir_promotion_schema.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: str | None = "8c1d4e6f9a23"' in migration
    assert "ADD COLUMN IF NOT EXISTS lifecycle_status" in migration
    assert "ADD COLUMN IF NOT EXISTS valid_from" in migration
    assert "DROP COLUMN IF EXISTS status" in migration
    assert "uq_aeir_model_versions_project_model_sha256" in migration
