"""add specification engineering platform

Revision ID: c31a76d9e845
Revises: c25f91a8b724
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c31a76d9e845"
down_revision: str | None = "c25f91a8b724"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def _guard_generation_run() -> None:
    op.execute(
        """
        CREATE FUNCTION guard_specification_generation_run() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'generation runs cannot be deleted'; END IF;
          IF OLD.id IS DISTINCT FROM NEW.id
             OR OLD.specification_id IS DISTINCT FROM NEW.specification_id
             OR OLD.specification_hash IS DISTINCT FROM NEW.specification_hash
             OR OLD.generator_key IS DISTINCT FROM NEW.generator_key
             OR OLD.generator_version IS DISTINCT FROM NEW.generator_version
             OR OLD.input_hash IS DISTINCT FROM NEW.input_hash
             OR OLD.request_document IS DISTINCT FROM NEW.request_document
             OR OLD.requested_by IS DISTINCT FROM NEW.requested_by
             OR OLD.created_at IS DISTINCT FROM NEW.created_at THEN
            RAISE EXCEPTION 'generation run input is immutable';
          END IF;
          IF NOT (
            (OLD.status = 'pending' AND NEW.status = 'running')
            OR (OLD.status = 'running' AND NEW.status IN ('completed', 'failed'))
          ) THEN RAISE EXCEPTION 'invalid generation run transition'; END IF;
          IF NEW.status = 'completed' AND
             (NEW.output_manifest IS NULL OR NEW.output_manifest_hash IS NULL) THEN
            RAISE EXCEPTION 'completed generation requires immutable output manifest';
          END IF;
          RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER guard_specification_generation_run_trigger
        BEFORE UPDATE
        OR DELETE ON specification_generation_runs
        FOR EACH ROW EXECUTE FUNCTION guard_specification_generation_run();
        """
    )


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "engineering_specifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("specification_key", sa.String(240), nullable=False),
        sa.Column("specification_type", sa.String(60), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("specification_document", jsonb, nullable=False),
        sa.Column("specification_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("requirements_hash", sa.String(64), nullable=False),
        sa.Column("architecture_hash", sa.String(64), nullable=False),
        sa.Column("work_package_hash", sa.String(64), nullable=False),
        sa.Column(
            "parent_specification_id", sa.Uuid(), sa.ForeignKey("engineering_specifications.id")
        ),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "specification_key", "version"),
    )
    op.create_table(
        "engineering_specification_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_specifications.id"),
            nullable=False,
        ),
        sa.Column("specification_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("specification_id", "specification_hash", "decision"),
    )
    op.create_table(
        "specification_generation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_specifications.id"),
            nullable=False,
        ),
        sa.Column("specification_hash", sa.String(64), nullable=False),
        sa.Column("generator_key", sa.String(120), nullable=False),
        sa.Column("generator_version", sa.String(80), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("request_document", jsonb, nullable=False),
        sa.Column("output_manifest", jsonb),
        sa.Column("output_manifest_hash", sa.String(64), unique=True),
        sa.Column("failure_document", jsonb),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "generated_engineering_artifacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "generation_run_id",
            sa.Uuid(),
            sa.ForeignKey("specification_generation_runs.id"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(80), nullable=False),
        sa.Column("repository_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("specification_hash", sa.String(64), nullable=False),
        sa.Column("generator_version", sa.String(80), nullable=False),
        sa.Column("provenance_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "specification_validation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_specifications.id"),
            nullable=False,
        ),
        sa.Column("specification_hash", sa.String(64), nullable=False),
        sa.Column("validator_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("findings", jsonb, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "engineering_evidence_nodes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("node_type", sa.String(60), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=False),
        sa.Column("reference_hash", sa.String(64), nullable=False),
        sa.Column("classification", sa.String(30), nullable=False),
        sa.Column("node_document", jsonb, nullable=False),
        sa.Column("node_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("node_type", "reference_id", "reference_hash"),
    )
    op.create_table(
        "engineering_evidence_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_node_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_evidence_nodes.id"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_evidence_nodes.id"),
            nullable=False,
        ),
        sa.Column("relationship", sa.String(80), nullable=False),
        sa.Column("edge_document", jsonb, nullable=False),
        sa.Column("edge_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_node_id", "target_node_id", "relationship"),
    )
    op.create_table(
        "engineering_drift_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "specification_id",
            sa.Uuid(),
            sa.ForeignKey("engineering_specifications.id"),
            nullable=False,
        ),
        sa.Column("specification_hash", sa.String(64), nullable=False),
        sa.Column("repository_commit_hash", sa.String(64), nullable=False),
        sa.Column("runtime_deployment_hash", sa.String(64)),
        sa.Column("detector_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("comparison_manifest", jsonb, nullable=False),
        sa.Column("comparison_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "engineering_drift_findings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "drift_run_id", sa.Uuid(), sa.ForeignKey("engineering_drift_runs.id"), nullable=False
        ),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("expected_hash", sa.String(64), nullable=False),
        sa.Column("actual_hash", sa.String(64), nullable=False),
        sa.Column("evidence_document", jsonb, nullable=False),
        sa.Column("finding_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("promotion_blocking", sa.Boolean(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "engineering_drift_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "finding_id", sa.Uuid(), sa.ForeignKey("engineering_drift_findings.id"), nullable=False
        ),
        sa.Column("finding_hash", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("decided_by", sa.String(200), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("finding_id", "finding_hash", "decision"),
    )
    for table in (
        "engineering_specifications",
        "engineering_specification_approvals",
        "generated_engineering_artifacts",
        "specification_validation_runs",
        "engineering_evidence_nodes",
        "engineering_evidence_edges",
        "engineering_drift_runs",
        "engineering_drift_findings",
        "engineering_drift_decisions",
    ):
        _immutable(table)
    _guard_generation_run()


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER guard_specification_generation_run_trigger ON specification_generation_runs"
    )
    op.execute("DROP FUNCTION guard_specification_generation_run()")
    immutable = (
        "engineering_specifications",
        "engineering_specification_approvals",
        "generated_engineering_artifacts",
        "specification_validation_runs",
        "engineering_evidence_nodes",
        "engineering_evidence_edges",
        "engineering_drift_runs",
        "engineering_drift_findings",
        "engineering_drift_decisions",
    )
    for table in reversed(immutable):
        name = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER {name}_trigger ON {table}")
        op.execute(f"DROP FUNCTION {name}()")
    for table in (
        "engineering_drift_decisions",
        "engineering_drift_findings",
        "engineering_drift_runs",
        "engineering_evidence_edges",
        "engineering_evidence_nodes",
        "specification_validation_runs",
        "generated_engineering_artifacts",
        "specification_generation_runs",
        "engineering_specification_approvals",
        "engineering_specifications",
    ):
        op.drop_table(table)
