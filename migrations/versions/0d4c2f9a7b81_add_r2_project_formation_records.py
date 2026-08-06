"""add R2 project formation records

Revision ID: 0d4c2f9a7b81
Revises: f3a7c1d9e204
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0d4c2f9a7b81"
down_revision: str | None = "f3a7c1d9e204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "aeir_project_snapshots",
    "aeir_object_versions",
    "aeir_relationship_versions",
    "aeir_validation_rules",
    "aeir_validation_findings",
    "aeir_clarification_questions",
    "aeir_clarification_answers",
    "aeir_decisions",
    "aeir_ai_operations",
    "aeir_artifact_versions",
    "aeir_artifact_trace_links",
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


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "aeir_project_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.String(40), nullable=False),
        sa.Column("aepm_version", sa.String(20), nullable=False),
        sa.Column("aeir_version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("object_versions", jsonb, nullable=False),
        sa.Column("snapshot_document", jsonb, nullable=False),
        sa.Column("snapshot_sha256", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "snapshot_id"),
        sa.UniqueConstraint("snapshot_sha256"),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'archived')",
            name="ck_aeir_project_snapshot_status",
        ),
    )
    op.create_index(
        "ix_aeir_project_snapshots_project_id", "aeir_project_snapshots", ["project_id"]
    )
    op.create_index(
        "ix_aeir_project_snapshots_model_version_id",
        "aeir_project_snapshots",
        ["model_version_id"],
    )
    op.create_index("ix_aeir_project_snapshots_status", "aeir_project_snapshots", ["status"])
    op.create_table(
        "aeir_object_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("object_row_id", sa.Uuid(), sa.ForeignKey("aeir_objects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_document", jsonb, nullable=False),
        sa.Column("object_version_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("object_row_id", "version_number"),
        sa.UniqueConstraint("object_version_hash"),
        sa.CheckConstraint("version_number > 0", name="ck_aeir_object_version_positive"),
    )
    op.create_index(
        "ix_aeir_object_versions_object_row_id", "aeir_object_versions", ["object_row_id"]
    )
    op.create_index(
        "ix_aeir_object_versions_model_version_id", "aeir_object_versions", ["model_version_id"]
    )
    op.create_index("ix_aeir_object_versions_object_id", "aeir_object_versions", ["object_id"])
    op.create_table(
        "aeir_relationship_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "relationship_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_relationships.id"),
            nullable=False,
        ),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("relationship_id", sa.String(64), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("version_document", jsonb, nullable=False),
        sa.Column("relationship_version_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("relationship_row_id", "version_number"),
        sa.UniqueConstraint("relationship_version_hash"),
        sa.CheckConstraint("version_number > 0", name="ck_aeir_relationship_version_positive"),
    )
    op.create_index(
        "ix_aeir_relationship_versions_relationship_row_id",
        "aeir_relationship_versions",
        ["relationship_row_id"],
    )
    op.create_index(
        "ix_aeir_relationship_versions_model_version_id",
        "aeir_relationship_versions",
        ["model_version_id"],
    )
    op.create_index(
        "ix_aeir_relationship_versions_relationship_id",
        "aeir_relationship_versions",
        ["relationship_id"],
    )
    op.create_table(
        "aeir_validation_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("rule_version", sa.String(40), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("rule_document", jsonb, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("rule_id", "rule_version"),
    )
    op.create_index("ix_aeir_validation_rules_category", "aeir_validation_rules", ["category"])
    op.create_table(
        "aeir_validation_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("snapshot_row_id", sa.Uuid(), sa.ForeignKey("aeir_project_snapshots.id")),
        sa.Column("model_version_id", sa.Uuid(), sa.ForeignKey("aeir_model_versions.id")),
        sa.Column("rule_row_id", sa.Uuid(), sa.ForeignKey("aeir_validation_rules.id")),
        sa.Column("finding_id", sa.String(80), nullable=False),
        sa.Column("rule_id", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("blocking", sa.Boolean(), nullable=False),
        sa.Column("object_refs", jsonb, nullable=False),
        sa.Column("finding_document", jsonb, nullable=False),
        sa.Column("finding_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("snapshot_row_id", "finding_id"),
        sa.UniqueConstraint("finding_hash"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_aeir_validation_findings_project_id", "aeir_validation_findings", ["project_id"]
    )
    op.create_index(
        "ix_aeir_validation_findings_snapshot_row_id",
        "aeir_validation_findings",
        ["snapshot_row_id"],
    )
    op.create_index(
        "ix_aeir_validation_findings_model_version_id",
        "aeir_validation_findings",
        ["model_version_id"],
    )
    op.create_index("ix_aeir_validation_findings_rule_id", "aeir_validation_findings", ["rule_id"])
    op.create_index(
        "ix_aeir_validation_findings_severity", "aeir_validation_findings", ["severity"]
    )
    op.create_index(
        "ix_aeir_validation_findings_category", "aeir_validation_findings", ["category"]
    )
    op.create_table(
        "aeir_clarification_questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("snapshot_row_id", sa.Uuid(), sa.ForeignKey("aeir_project_snapshots.id")),
        sa.Column("question_id", sa.String(80), nullable=False),
        sa.Column("section", sa.String(80), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("target_object_ids", jsonb, nullable=False),
        sa.Column("question_document", jsonb, nullable=False),
        sa.Column("question_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("snapshot_row_id", "question_id"),
        sa.UniqueConstraint("question_hash"),
    )
    op.create_index(
        "ix_aeir_clarification_questions_project_id",
        "aeir_clarification_questions",
        ["project_id"],
    )
    op.create_index(
        "ix_aeir_clarification_questions_snapshot_row_id",
        "aeir_clarification_questions",
        ["snapshot_row_id"],
    )
    op.create_index(
        "ix_aeir_clarification_questions_section", "aeir_clarification_questions", ["section"]
    )
    op.create_table(
        "aeir_clarification_answers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "question_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_clarification_questions.id"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("respondent_id", sa.String(200), nullable=False),
        sa.Column("resolution", sa.String(30), nullable=False),
        sa.Column("answer_document", jsonb, nullable=False),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("question_row_id", "answer_hash"),
        sa.UniqueConstraint("answer_hash"),
    )
    op.create_index(
        "ix_aeir_clarification_answers_question_row_id",
        "aeir_clarification_answers",
        ["question_row_id"],
    )
    op.create_index(
        "ix_aeir_clarification_answers_project_id", "aeir_clarification_answers", ["project_id"]
    )
    op.create_index(
        "ix_aeir_clarification_answers_resolution", "aeir_clarification_answers", ["resolution"]
    )
    op.create_table(
        "aeir_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("snapshot_row_id", sa.Uuid(), sa.ForeignKey("aeir_project_snapshots.id")),
        sa.Column("object_id", sa.String(64)),
        sa.Column("decision_type", sa.String(60), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reviewer_id", sa.String(200), nullable=False),
        sa.Column("decision_document", jsonb, nullable=False),
        sa.Column("decision_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("decision_hash"),
    )
    op.create_index("ix_aeir_decisions_project_id", "aeir_decisions", ["project_id"])
    op.create_index("ix_aeir_decisions_snapshot_row_id", "aeir_decisions", ["snapshot_row_id"])
    op.create_index("ix_aeir_decisions_object_id", "aeir_decisions", ["object_id"])
    op.create_index("ix_aeir_decisions_decision_type", "aeir_decisions", ["decision_type"])
    op.create_index("ix_aeir_decisions_decision", "aeir_decisions", ["decision"])
    op.create_table(
        "aeir_ai_operations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), sa.ForeignKey("aeir_model_versions.id")),
        sa.Column("model_provider", sa.String(200), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("operation_type", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("input_source_refs", jsonb, nullable=False),
        sa.Column("review_required", sa.Boolean(), nullable=False),
        sa.Column("operation_document", jsonb, nullable=False),
        sa.Column("operation_sha256", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.String(40), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("operation_sha256"),
    )
    op.create_index("ix_aeir_ai_operations_project_id", "aeir_ai_operations", ["project_id"])
    op.create_index(
        "ix_aeir_ai_operations_model_version_id", "aeir_ai_operations", ["model_version_id"]
    )
    op.create_index(
        "ix_aeir_ai_operations_operation_type", "aeir_ai_operations", ["operation_type"]
    )
    op.create_table(
        "aeir_artifact_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "snapshot_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_project_snapshots.id"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("compiler_id", sa.String(120), nullable=False),
        sa.Column("compiler_version", sa.String(40), nullable=False),
        sa.Column("contract_hash", sa.String(64), nullable=False),
        sa.Column("compilation_status", sa.String(30), nullable=False),
        sa.Column("output_format", sa.String(30), nullable=False),
        sa.Column("artifact_document", jsonb, nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "artifact_type", "version_number"),
        sa.UniqueConstraint("artifact_hash"),
        sa.CheckConstraint("version_number > 0", name="ck_aeir_artifact_version_positive"),
    )
    op.create_index(
        "ix_aeir_artifact_versions_project_id", "aeir_artifact_versions", ["project_id"]
    )
    op.create_index(
        "ix_aeir_artifact_versions_snapshot_row_id",
        "aeir_artifact_versions",
        ["snapshot_row_id"],
    )
    op.create_index(
        "ix_aeir_artifact_versions_artifact_type", "aeir_artifact_versions", ["artifact_type"]
    )
    op.create_index(
        "ix_aeir_artifact_versions_compilation_status",
        "aeir_artifact_versions",
        ["compilation_status"],
    )
    op.create_table(
        "aeir_artifact_trace_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "artifact_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_artifact_versions.id"),
            nullable=False,
        ),
        sa.Column("artifact_section_id", sa.String(160), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("relationship_id", sa.String(64)),
        sa.Column("trace_type", sa.String(60), nullable=False),
        sa.Column("trace_document", jsonb, nullable=False),
        sa.Column("trace_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("artifact_version_id", "artifact_section_id", "object_id"),
    )
    op.create_index(
        "ix_aeir_artifact_trace_links_artifact_version_id",
        "aeir_artifact_trace_links",
        ["artifact_version_id"],
    )
    op.create_index(
        "ix_aeir_artifact_trace_links_object_id", "aeir_artifact_trace_links", ["object_id"]
    )
    op.create_index(
        "ix_aeir_artifact_trace_links_relationship_id",
        "aeir_artifact_trace_links",
        ["relationship_id"],
    )
    op.create_index(
        "ix_aeir_artifact_trace_links_trace_type", "aeir_artifact_trace_links", ["trace_type"]
    )
    for table in TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TRIGGER prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION prevent_{table}_mutation()")
    for table in reversed(TABLES):
        op.drop_table(table)
