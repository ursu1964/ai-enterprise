"""add AEIR source and evidence links

Revision ID: 5b8e1f7c3a29
Revises: 2a6d8f1e0c42
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5b8e1f7c3a29"
down_revision: str | None = "2a6d8f1e0c42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "aeir_evidence",
    "aeir_object_source_links",
    "aeir_relationship_source_links",
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
        "aeir_evidence",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("object_row_id", sa.Uuid(), sa.ForeignKey("aeir_objects.id")),
        sa.Column(
            "relationship_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_relationships.id"),
        ),
        sa.Column("evidence_id", sa.String(120), nullable=False),
        sa.Column("evidence_type", sa.String(60), nullable=False),
        sa.Column("source_ref", sa.String(120)),
        sa.Column("evidence_document", jsonb, nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "evidence_hash"),
        sa.CheckConstraint(
            "object_row_id IS NOT NULL OR relationship_row_id IS NOT NULL",
            name="ck_aeir_evidence_target_present",
        ),
    )
    op.create_index("ix_aeir_evidence_project_id", "aeir_evidence", ["project_id"])
    op.create_index("ix_aeir_evidence_model_version_id", "aeir_evidence", ["model_version_id"])
    op.create_index("ix_aeir_evidence_object_row_id", "aeir_evidence", ["object_row_id"])
    op.create_index(
        "ix_aeir_evidence_relationship_row_id", "aeir_evidence", ["relationship_row_id"]
    )
    op.create_index("ix_aeir_evidence_evidence_id", "aeir_evidence", ["evidence_id"])
    op.create_index("ix_aeir_evidence_evidence_type", "aeir_evidence", ["evidence_type"])
    op.create_index("ix_aeir_evidence_source_ref", "aeir_evidence", ["source_ref"])

    op.create_table(
        "aeir_object_source_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("object_row_id", sa.Uuid(), sa.ForeignKey("aeir_objects.id"), nullable=False),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("source_ref", sa.String(120), nullable=False),
        sa.Column("link_type", sa.String(60), nullable=False),
        sa.Column("link_document", jsonb, nullable=False),
        sa.Column("link_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "link_hash"),
        sa.UniqueConstraint("object_row_id", "source_ref", "link_type"),
    )
    op.create_index(
        "ix_aeir_object_source_links_project_id",
        "aeir_object_source_links",
        ["project_id"],
    )
    op.create_index(
        "ix_aeir_object_source_links_model_version_id",
        "aeir_object_source_links",
        ["model_version_id"],
    )
    op.create_index(
        "ix_aeir_object_source_links_object_row_id",
        "aeir_object_source_links",
        ["object_row_id"],
    )
    op.create_index(
        "ix_aeir_object_source_links_object_id",
        "aeir_object_source_links",
        ["object_id"],
    )
    op.create_index(
        "ix_aeir_object_source_links_source_ref",
        "aeir_object_source_links",
        ["source_ref"],
    )
    op.create_index(
        "ix_aeir_object_source_links_link_type",
        "aeir_object_source_links",
        ["link_type"],
    )

    op.create_table(
        "aeir_relationship_source_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "relationship_row_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_relationships.id"),
            nullable=False,
        ),
        sa.Column("relationship_id", sa.String(64), nullable=False),
        sa.Column("source_ref", sa.String(120), nullable=False),
        sa.Column("link_type", sa.String(60), nullable=False),
        sa.Column("link_document", jsonb, nullable=False),
        sa.Column("link_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "link_hash"),
        sa.UniqueConstraint("relationship_row_id", "source_ref", "link_type"),
    )
    op.create_index(
        "ix_aeir_relationship_source_links_project_id",
        "aeir_relationship_source_links",
        ["project_id"],
    )
    op.create_index(
        "ix_aeir_relationship_source_links_model_version_id",
        "aeir_relationship_source_links",
        ["model_version_id"],
    )
    op.create_index(
        "ix_aeir_relationship_source_links_relationship_row_id",
        "aeir_relationship_source_links",
        ["relationship_row_id"],
    )
    op.create_index(
        "ix_aeir_relationship_source_links_relationship_id",
        "aeir_relationship_source_links",
        ["relationship_id"],
    )
    op.create_index(
        "ix_aeir_relationship_source_links_source_ref",
        "aeir_relationship_source_links",
        ["source_ref"],
    )
    op.create_index(
        "ix_aeir_relationship_source_links_link_type",
        "aeir_relationship_source_links",
        ["link_type"],
    )

    for table in TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        trigger = f"prevent_{table}_mutation_trigger"
        function = f"prevent_{table}_mutation"
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS {function}()")
    op.drop_table("aeir_relationship_source_links")
    op.drop_table("aeir_object_source_links")
    op.drop_table("aeir_evidence")
