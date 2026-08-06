"""add bk r11 evidence audit records

Revision ID: a1d5e8f2b9c4
Revises: f8a6c2d4e9b1
Create Date: 2026-08-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1d5e8f2b9c4"
down_revision: str | None = "f8a6c2d4e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _packages()
    _artifacts()
    _audit_records()
    _coverage_reports()
    _integrity_reports()
    _package_events()
    for table_name in (
        "bk_r11_evidence_packages",
        "bk_r11_evidence_artifacts",
        "bk_r11_audit_records",
        "bk_r11_coverage_reports",
        "bk_r11_integrity_reports",
        "bk_r11_package_events",
    ):
        _immutable(table_name)


def downgrade() -> None:
    for table_name in (
        "bk_r11_package_events",
        "bk_r11_integrity_reports",
        "bk_r11_coverage_reports",
        "bk_r11_audit_records",
        "bk_r11_evidence_artifacts",
        "bk_r11_evidence_packages",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table_name}_mutation_trigger ON {table_name}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table_name}_mutation")
        op.drop_table(table_name)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_key", sa.String(length=160), nullable=False),
        sa.Column("package_id", sa.String(length=220), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def _packages() -> None:
    op.create_table(
        "bk_r11_evidence_packages",
        *_base_columns(),
        sa.Column("package_version", sa.String(length=120), nullable=False),
        sa.Column("acceptance_status", sa.String(length=80), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "manifest_hash"),
    )
    _indexes("bk_r11_evidence_packages", "project_key", "package_id", "acceptance_status")
    op.create_index(
        "ix_bk_r11_evidence_packages_manifest_hash",
        "bk_r11_evidence_packages",
        ["manifest_hash"],
    )


def _artifacts() -> None:
    op.create_table(
        "bk_r11_evidence_artifacts",
        *_base_columns(),
        sa.Column("evidence_id", sa.String(length=220), nullable=False),
        sa.Column("evidence_type", sa.String(length=120), nullable=False),
        sa.Column("source_system", sa.String(length=160), nullable=False),
        sa.Column("classification", sa.String(length=80), nullable=False),
        sa.Column("artifact_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "evidence_id", "artifact_hash"),
    )
    _indexes(
        "bk_r11_evidence_artifacts",
        "project_key",
        "package_id",
        "evidence_id",
        "evidence_type",
        "classification",
    )


def _audit_records() -> None:
    op.create_table(
        "bk_r11_audit_records",
        *_base_columns(),
        sa.Column("audit_record_id", sa.String(length=260), nullable=False),
        sa.Column("stream_id", sa.String(length=220), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "audit_record_id", "record_hash"),
    )
    _indexes(
        "bk_r11_audit_records",
        "project_key",
        "package_id",
        "stream_id",
        "event_type",
    )


def _coverage_reports() -> None:
    op.create_table(
        "bk_r11_coverage_reports",
        *_base_columns(),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("coverage_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "coverage_hash"),
    )
    _indexes("bk_r11_coverage_reports", "project_key", "package_id", "status")


def _integrity_reports() -> None:
    op.create_table(
        "bk_r11_integrity_reports",
        *_base_columns(),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("integrity_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "integrity_hash"),
    )
    _indexes("bk_r11_integrity_reports", "project_key", "package_id", "status")


def _package_events() -> None:
    op.create_table(
        "bk_r11_package_events",
        *_base_columns(),
        sa.Column("event_id", sa.String(length=260), nullable=False),
        sa.Column("event_type", sa.String(length=160), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_key", "package_id", "event_id"),
    )
    _indexes("bk_r11_package_events", "project_key", "package_id", "event_type")


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
