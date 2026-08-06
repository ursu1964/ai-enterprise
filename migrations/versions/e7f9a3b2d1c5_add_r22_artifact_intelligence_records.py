"""add r22 artifact intelligence records

Revision ID: e7f9a3b2d1c5
Revises: d6e8f2a1c9b4
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7f9a3b2d1c5"
down_revision: str | None = "d6e8f2a1c9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _registries()
    _artifacts()
    _artifact_versions()
    _provenance()
    _trace_relationships()
    _evidence()
    _validations()
    _findings()
    _events()
    for table_name in (
        "r22_artifact_registries",
        "r22_artifacts",
        "r22_artifact_versions",
        "r22_provenance_records",
        "r22_trace_relationships",
        "r22_evidence_records",
        "r22_validation_results",
        "r22_findings",
        "r22_artifact_events",
    ):
        _immutable(table_name)


def downgrade() -> None:
    for table_name in (
        "r22_artifact_events",
        "r22_findings",
        "r22_validation_results",
        "r22_evidence_records",
        "r22_trace_relationships",
        "r22_provenance_records",
        "r22_artifact_versions",
        "r22_artifacts",
        "r22_artifact_registries",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table_name}_mutation_trigger ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation")
        op.drop_table(table_name)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_key", sa.String(length=160), nullable=False),
        sa.Column("tenant_key", sa.String(length=160), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _registries() -> None:
    op.create_table(
        "r22_artifact_registries",
        *_base_columns(),
        sa.Column("registry_id", sa.String(length=200), nullable=False),
        sa.Column("registry_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "tenant_key", "registry_hash"),
    )
    _indexes("r22_artifact_registries", "project_key", "tenant_key")


def _artifacts() -> None:
    op.create_table(
        "r22_artifacts",
        *_base_columns(),
        sa.Column("artifact_id", sa.String(length=220), nullable=False),
        sa.Column("artifact_type", sa.String(length=160), nullable=False),
        sa.Column("artifact_class", sa.String(length=80), nullable=False),
        sa.Column("current_version_id", sa.String(length=220), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "artifact_id", "artifact_hash"),
    )
    _indexes("r22_artifacts", "project_key", "artifact_id", "artifact_class")


def _artifact_versions() -> None:
    op.create_table(
        "r22_artifact_versions",
        *_base_columns(),
        sa.Column("artifact_id", sa.String(length=220), nullable=False),
        sa.Column("artifact_version_id", sa.String(length=220), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=80), nullable=False),
        sa.Column("validation_state", sa.String(length=80), nullable=False),
        sa.Column("freshness_state", sa.String(length=80), nullable=False),
        sa.Column("integrity_state", sa.String(length=80), nullable=False),
        sa.Column("governance_state", sa.String(length=80), nullable=False),
        sa.Column("checksum", sa.String(length=96), nullable=False),
        sa.Column("content_address", sa.String(length=220), nullable=False),
        sa.Column("classification", sa.String(length=80), nullable=False),
        sa.Column("version_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "artifact_version_id", "version_hash"),
    )
    _indexes(
        "r22_artifact_versions",
        "project_key",
        "artifact_id",
        "lifecycle_state",
        "checksum",
        "classification",
    )


def _provenance() -> None:
    op.create_table(
        "r22_provenance_records",
        *_base_columns(),
        sa.Column("provenance_id", sa.String(length=220), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=220), nullable=False),
        sa.Column("provenance_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "provenance_id", "provenance_hash"),
    )
    _indexes("r22_provenance_records", "project_key", "subject_id")


def _trace_relationships() -> None:
    op.create_table(
        "r22_trace_relationships",
        *_base_columns(),
        sa.Column("relationship_id", sa.String(length=220), nullable=False),
        sa.Column("source_id", sa.String(length=220), nullable=False),
        sa.Column("target_id", sa.String(length=220), nullable=False),
        sa.Column("relationship_type", sa.String(length=80), nullable=False),
        sa.Column("relationship_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "relationship_id", "relationship_hash"),
    )
    _indexes(
        "r22_trace_relationships", "project_key", "source_id", "target_id", "relationship_type"
    )


def _evidence() -> None:
    op.create_table(
        "r22_evidence_records",
        *_base_columns(),
        sa.Column("evidence_id", sa.String(length=220), nullable=False),
        sa.Column("claim_id", sa.String(length=220), nullable=True),
        sa.Column("subject_id", sa.String(length=220), nullable=False),
        sa.Column("evidence_type", sa.String(length=120), nullable=False),
        sa.Column("evidence_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "evidence_id", "evidence_hash"),
    )
    _indexes("r22_evidence_records", "project_key", "subject_id", "claim_id")


def _validations() -> None:
    op.create_table(
        "r22_validation_results",
        *_base_columns(),
        sa.Column("validation_id", sa.String(length=220), nullable=False),
        sa.Column("artifact_version_id", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("validation_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "validation_id", "validation_hash"),
    )
    _indexes("r22_validation_results", "project_key", "artifact_version_id", "status")


def _findings() -> None:
    op.create_table(
        "r22_findings",
        *_base_columns(),
        sa.Column("finding_id", sa.String(length=220), nullable=False),
        sa.Column("artifact_version_id", sa.String(length=220), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=80), nullable=False),
        sa.Column("finding_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "finding_id", "finding_hash"),
    )
    _indexes("r22_findings", "project_key", "artifact_version_id", "state", "severity")


def _events() -> None:
    op.create_table(
        "r22_artifact_events",
        *_base_columns(),
        sa.Column("event_id", sa.String(length=220), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("checksum", sa.String(length=96), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_key", "event_id"),
    )
    _indexes("r22_artifact_events", "project_key", "event_type")


def _indexes(table_name: str, *columns: str) -> None:
    for column in columns:
        op.create_index(f"ix_{table_name}_{column}", table_name, [column])


def _immutable(table_name: str) -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION prevent_{table_name}_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '{table_name} is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER prevent_{table_name}_mutation_trigger
        BEFORE UPDATE OR DELETE ON {table_name}
        FOR EACH ROW EXECUTE FUNCTION prevent_{table_name}_mutation();
        """
    )
