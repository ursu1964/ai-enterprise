"""add R4 AI interpretation records

Revision ID: 8c1d4e6f9a23
Revises: 5b8e1f7c3a29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8c1d4e6f9a23"
down_revision: str | None = "5b8e1f7c3a29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r4_source_normalizations",
    "r4_source_segments",
    "r4_prompt_versions",
    "r4_ai_operations",
    "r4_ai_usage_records",
    "r4_ai_operation_failures",
    "r4_candidate_source_links",
    "r4_candidate_validation_results",
    "r4_uncertainty_records",
    "r4_clarification_questions",
    "r4_candidate_reviews",
    "r4_candidate_promotions",
    "r4_ai_provenance_links",
    "r4_evaluation_records",
)


def _immutable(table: str) -> None:
    name = f"prevent_{table}_mutation"
    op.execute(
        f"CREATE FUNCTION {name}() RETURNS trigger AS $$ BEGIN "
        f"RAISE EXCEPTION '{table} is append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        f"CREATE TRIGGER {name}_trigger BEFORE UPDATE OR DELETE ON {table} "
        f"FOR EACH ROW EXECUTE FUNCTION {name}()"
    )


def _timestamps() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "r4_source_normalizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "source_row_id", sa.Uuid(), sa.ForeignKey("aeir_source_objects.id"), nullable=False
        ),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("normalization_version", sa.String(40), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("segment_count", sa.Integer(), nullable=False),
        sa.Column("normalized_document", jsonb, nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("source_row_id", "normalization_version"),
        sa.UniqueConstraint("project_id", "checksum"),
    )
    op.create_index(
        "ix_r4_source_normalizations_project_id", "r4_source_normalizations", ["project_id"]
    )
    op.create_index(
        "ix_r4_source_normalizations_source_row_id", "r4_source_normalizations", ["source_row_id"]
    )
    op.create_index(
        "ix_r4_source_normalizations_source_id", "r4_source_normalizations", ["source_id"]
    )

    op.create_table(
        "r4_source_segments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "normalization_id",
            sa.Uuid(),
            sa.ForeignKey("r4_source_normalizations.id"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("segment_id", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("segment_type", sa.String(40), nullable=False),
        sa.Column("heading_path", jsonb, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.UniqueConstraint("normalization_id", "sequence"),
        sa.UniqueConstraint("project_id", "segment_id"),
    )
    for column in ("project_id", "normalization_id", "source_id", "segment_id", "segment_type"):
        op.create_index(f"ix_r4_source_segments_{column}", "r4_source_segments", [column])

    op.create_table(
        "r4_prompt_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("prompt_id", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("operation_type", sa.String(80), nullable=False),
        sa.Column("system_instruction_ref", sa.Text(), nullable=False),
        sa.Column("task_template_ref", sa.Text(), nullable=False),
        sa.Column("response_schema_ref", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("prompt_document", jsonb, nullable=False),
        sa.Column("approved_by", sa.String(200), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("prompt_id", "prompt_version"),
    )
    for column in ("prompt_id", "operation_type", "status"):
        op.create_index(f"ix_r4_prompt_versions_{column}", "r4_prompt_versions", [column])

    op.create_table(
        "r4_ai_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("operation_id", sa.String(80), nullable=False),
        sa.Column("operation_type", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_id", sa.String(120), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("response_schema_id", sa.String(120), nullable=False),
        sa.Column("response_schema_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source_ids", jsonb, nullable=False),
        sa.Column("segment_ids", jsonb, nullable=False),
        sa.Column("parameters", jsonb, nullable=False),
        sa.Column("operation_document", jsonb, nullable=False),
        sa.Column("operation_hash", sa.String(64), nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        _timestamps(),
        sa.UniqueConstraint("project_id", "operation_id"),
        sa.UniqueConstraint("project_id", "operation_hash"),
    )
    for column in ("project_id", "operation_id", "operation_type", "status"):
        op.create_index(f"ix_r4_ai_operations_{column}", "r4_ai_operations", [column])

    op.create_table(
        "r4_ai_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("provider", sa.String(120), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=False),
        sa.Column("execution_seconds", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("usage_document", jsonb, nullable=False),
        sa.UniqueConstraint("operation_row_id"),
    )
    op.create_index(
        "ix_r4_ai_usage_records_operation_row_id", "r4_ai_usage_records", ["operation_row_id"]
    )
    op.create_index("ix_r4_ai_usage_records_project_id", "r4_ai_usage_records", ["project_id"])

    op.create_table(
        "r4_ai_operation_failures",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id")),
        sa.Column("operation_id", sa.String(80), nullable=False),
        sa.Column("failure_type", sa.String(80), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("final_status", sa.String(40), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=False),
        sa.Column("failure_document", jsonb, nullable=False),
        sa.Column("failure_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "operation_id", "retry_count"),
    )
    for column in (
        "project_id",
        "ai_operation_row_id",
        "operation_id",
        "failure_type",
        "final_status",
    ):
        op.create_index(
            f"ix_r4_ai_operation_failures_{column}", "r4_ai_operation_failures", [column]
        )

    op.create_table(
        "r4_candidate_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("proposed_object_type", sa.String(80), nullable=False),
        sa.Column("proposed_object_id", sa.String(80), nullable=False),
        sa.Column("truth_status", sa.String(30), nullable=False),
        sa.Column("approval_status", sa.String(30), nullable=False),
        sa.Column("candidate_status", sa.String(40), nullable=False),
        sa.Column("schema_status", sa.String(40), nullable=False),
        sa.Column("deterministic_validation_status", sa.String(60), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("candidate_hash", sa.String(64), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("reviewed_by", sa.String(200)),
        _timestamps(),
        sa.UniqueConstraint("project_id", "candidate_id"),
        sa.UniqueConstraint("project_id", "candidate_hash"),
    )
    for column in (
        "project_id",
        "ai_operation_row_id",
        "candidate_id",
        "proposed_object_type",
        "proposed_object_id",
        "truth_status",
        "approval_status",
        "candidate_status",
        "schema_status",
    ):
        op.create_index(f"ix_r4_candidate_objects_{column}", "r4_candidate_objects", [column])

    op.create_table(
        "r4_candidate_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("relationship_type", sa.String(80), nullable=False),
        sa.Column("source_candidate_ref", sa.String(80), nullable=False),
        sa.Column("target_candidate_ref", sa.String(80), nullable=False),
        sa.Column("truth_status", sa.String(30), nullable=False),
        sa.Column("approval_status", sa.String(30), nullable=False),
        sa.Column("candidate_status", sa.String(40), nullable=False),
        sa.Column("schema_status", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("candidate_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("project_id", "candidate_id"),
        sa.UniqueConstraint("project_id", "candidate_hash"),
    )
    for column in (
        "project_id",
        "ai_operation_row_id",
        "candidate_id",
        "relationship_type",
        "truth_status",
        "approval_status",
        "candidate_status",
        "schema_status",
    ):
        op.create_index(
            f"ix_r4_candidate_relationships_{column}", "r4_candidate_relationships", [column]
        )

    op.create_table(
        "r4_candidate_source_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("segment_id", sa.String(80), nullable=False),
        sa.Column("support_type", sa.String(40), nullable=False),
        sa.Column("quoted_fragment", sa.Text()),
        sa.Column("link_document", jsonb, nullable=False),
        sa.UniqueConstraint("project_id", "candidate_id", "source_id", "segment_id"),
    )
    for column in ("project_id", "candidate_id", "source_id", "segment_id", "support_type"):
        op.create_index(
            f"ix_r4_candidate_source_links_{column}", "r4_candidate_source_links", [column]
        )

    op.create_table(
        "r4_candidate_validation_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("findings", jsonb, nullable=False),
        sa.Column("result_hash", sa.String(64), nullable=False, unique=True),
    )
    for column in ("project_id", "ai_operation_row_id", "candidate_id", "status"):
        op.create_index(
            f"ix_r4_candidate_validation_results_{column}",
            "r4_candidate_validation_results",
            [column],
        )

    op.create_table(
        "r4_uncertainty_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("record_id", sa.String(80), nullable=False),
        sa.Column("record_type", sa.String(60), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column("record_hash", sa.String(64), nullable=False, unique=True),
        sa.UniqueConstraint("project_id", "record_id", "record_type"),
    )
    for column in (
        "project_id",
        "ai_operation_row_id",
        "record_id",
        "record_type",
        "category",
        "severity",
        "status",
    ):
        op.create_index(f"ix_r4_uncertainty_records_{column}", "r4_uncertainty_records", [column])

    op.create_table(
        "r4_clarification_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "ai_operation_row_id", sa.Uuid(), sa.ForeignKey("r4_ai_operations.id"), nullable=False
        ),
        sa.Column("question_id", sa.String(80), nullable=False),
        sa.Column("origin_type", sa.String(60), nullable=False),
        sa.Column("origin_ref", sa.String(120), nullable=False),
        sa.Column("priority", sa.String(30), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("question_document", jsonb, nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False, unique=True),
        sa.UniqueConstraint("project_id", "question_id"),
    )
    for column in (
        "project_id",
        "ai_operation_row_id",
        "question_id",
        "origin_type",
        "origin_ref",
        "priority",
        "status",
    ):
        op.create_index(
            f"ix_r4_clarification_questions_{column}", "r4_clarification_questions", [column]
        )

    op.create_table(
        "r4_candidate_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("review_id", sa.String(80), nullable=False),
        sa.Column("reviewer_id", sa.String(200), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("review_document", jsonb, nullable=False),
        sa.Column("review_hash", sa.String(64), nullable=False, unique=True),
        _timestamps(),
        sa.UniqueConstraint("project_id", "review_id"),
    )
    for column in ("project_id", "candidate_id", "review_id", "reviewer_id", "action"):
        op.create_index(f"ix_r4_candidate_reviews_{column}", "r4_candidate_reviews", [column])

    op.create_table(
        "r4_candidate_promotions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("candidate_id", sa.String(80), nullable=False),
        sa.Column("canonical_object_id", sa.String(80)),
        sa.Column("canonical_relationship_id", sa.String(80)),
        sa.Column("promoted_by", sa.String(200), nullable=False),
        sa.Column("promotion_document", jsonb, nullable=False),
        sa.Column("promotion_hash", sa.String(64), nullable=False, unique=True),
        _timestamps(),
        sa.UniqueConstraint("project_id", "candidate_id"),
    )
    for column in (
        "project_id",
        "candidate_id",
        "canonical_object_id",
        "canonical_relationship_id",
    ):
        op.create_index(f"ix_r4_candidate_promotions_{column}", "r4_candidate_promotions", [column])

    op.create_table(
        "r4_ai_provenance_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.String(80), nullable=False),
        sa.Column("ai_operation_id", sa.String(80), nullable=False),
        sa.Column("source_segment_refs", jsonb, nullable=False),
        sa.Column("derivation_type", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance_document", jsonb, nullable=False),
        sa.UniqueConstraint("project_id", "entity_type", "entity_id", "ai_operation_id"),
    )
    for column in ("project_id", "entity_type", "entity_id", "ai_operation_id", "derivation_type"):
        op.create_index(f"ix_r4_ai_provenance_links_{column}", "r4_ai_provenance_links", [column])

    op.create_table(
        "r4_evaluation_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("case_id", sa.String(120), nullable=False),
        sa.Column("run_id", sa.String(120), nullable=False),
        sa.Column("metrics", jsonb, nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("result_document", jsonb, nullable=False),
        _timestamps(),
        sa.UniqueConstraint("case_id", "run_id"),
    )
    op.create_index("ix_r4_evaluation_records_case_id", "r4_evaluation_records", ["case_id"])
    op.create_index("ix_r4_evaluation_records_run_id", "r4_evaluation_records", ["run_id"])
    op.create_index("ix_r4_evaluation_records_passed", "r4_evaluation_records", ["passed"])

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation()")
    for table in (
        "r4_evaluation_records",
        "r4_ai_provenance_links",
        "r4_candidate_promotions",
        "r4_candidate_reviews",
        "r4_clarification_questions",
        "r4_uncertainty_records",
        "r4_candidate_validation_results",
        "r4_candidate_source_links",
        "r4_candidate_relationships",
        "r4_candidate_objects",
        "r4_ai_operation_failures",
        "r4_ai_usage_records",
        "r4_ai_operations",
        "r4_prompt_versions",
        "r4_source_segments",
        "r4_source_normalizations",
    ):
        op.drop_table(table)
