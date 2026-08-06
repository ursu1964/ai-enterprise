"""add AEIR knowledge storage

Revision ID: f3a7c1d9e204
Revises: f2c6a9e1b407
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f3a7c1d9e204"
down_revision: str | None = "f2c6a9e1b407"
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


def upgrade() -> None:
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "aeir_model_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("source_manifest_sha256", sa.String(64), nullable=False),
        sa.Column("model_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("model_document", jsonb, nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "version_number"),
        sa.CheckConstraint("version_number > 0", name="ck_aeir_model_version_positive"),
    )
    op.create_index("ix_aeir_model_versions_project_id", "aeir_model_versions", ["project_id"])
    op.create_table(
        "aeir_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("object_id", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(40), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.String(30), nullable=False),
        sa.Column("truth_status", sa.String(30), nullable=False),
        sa.Column("approval_status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("object_version", sa.String(40), nullable=False),
        sa.Column("source_document", jsonb, nullable=False),
        sa.Column("source_refs", jsonb, nullable=False),
        sa.Column("evidence_refs", jsonb, nullable=False),
        sa.Column("relationship_refs", jsonb, nullable=False),
        sa.Column("attributes", jsonb, nullable=False),
        sa.Column("metadata", jsonb, nullable=False),
        sa.UniqueConstraint("model_version_id", "object_id"),
        sa.UniqueConstraint("model_version_id", "id"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_aeir_object_confidence"),
    )
    op.create_index("ix_aeir_objects_model_version_id", "aeir_objects", ["model_version_id"])
    op.create_index("ix_aeir_objects_object_type", "aeir_objects", ["object_type"])
    op.create_index("ix_aeir_objects_lifecycle_status", "aeir_objects", ["lifecycle_status"])
    op.create_index("ix_aeir_objects_truth_status", "aeir_objects", ["truth_status"])
    op.create_index("ix_aeir_objects_approval_status", "aeir_objects", ["approval_status"])
    op.create_table(
        "aeir_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "model_version_id",
            sa.Uuid(),
            sa.ForeignKey("aeir_model_versions.id"),
            nullable=False,
        ),
        sa.Column("relationship_id", sa.String(64), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("source_object_id", sa.Uuid(), nullable=False),
        sa.Column("target_object_id", sa.Uuid(), nullable=False),
        sa.Column("lifecycle_status", sa.String(30), nullable=False),
        sa.Column("truth_status", sa.String(30), nullable=False),
        sa.Column("approval_status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("valid_from", sa.String(10), nullable=False),
        sa.Column("valid_to", sa.String(10)),
        sa.Column("relationship_document", jsonb, nullable=False),
        sa.UniqueConstraint("model_version_id", "relationship_id"),
        sa.ForeignKeyConstraint(
            ("model_version_id", "source_object_id"),
            ("aeir_objects.model_version_id", "aeir_objects.id"),
        ),
        sa.ForeignKeyConstraint(
            ("model_version_id", "target_object_id"),
            ("aeir_objects.model_version_id", "aeir_objects.id"),
        ),
        sa.CheckConstraint(
            "source_object_id <> target_object_id", name="ck_aeir_relationship_distinct"
        ),
    )
    op.create_index(
        "ix_aeir_relationships_model_version_id", "aeir_relationships", ["model_version_id"]
    )
    op.create_index(
        "ix_aeir_relationships_relationship_type", "aeir_relationships", ["relationship_type"]
    )
    op.create_index(
        "ix_aeir_relationships_lifecycle_status",
        "aeir_relationships",
        ["lifecycle_status"],
    )
    op.create_index("ix_aeir_relationships_truth_status", "aeir_relationships", ["truth_status"])
    op.create_index(
        "ix_aeir_relationships_approval_status",
        "aeir_relationships",
        ["approval_status"],
    )
    op.create_table(
        "aeir_source_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("storage_provider", sa.String(80), nullable=False),
        sa.Column("bucket", sa.String(200), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("source_metadata", jsonb, nullable=False),
        sa.Column("uploaded_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("storage_provider", "bucket", "object_key"),
        sa.CheckConstraint("size_bytes >= 0", name="ck_aeir_source_size_nonnegative"),
    )
    op.create_index("ix_aeir_source_objects_project_id", "aeir_source_objects", ["project_id"])
    op.create_table(
        "aeir_change_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("model_version_id", sa.Uuid(), sa.ForeignKey("aeir_model_versions.id")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id", sa.String(200), nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", jsonb, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("project_id", "sequence"),
    )
    op.create_index("ix_aeir_change_events_project_id", "aeir_change_events", ["project_id"])
    op.create_index(
        "ix_aeir_change_events_model_version_id", "aeir_change_events", ["model_version_id"]
    )
    op.create_index("ix_aeir_change_events_event_type", "aeir_change_events", ["event_type"])
    for table in (
        "aeir_model_versions",
        "aeir_objects",
        "aeir_relationships",
        "aeir_source_objects",
        "aeir_change_events",
    ):
        _immutable(table)


def downgrade() -> None:
    for table in (
        "aeir_change_events",
        "aeir_source_objects",
        "aeir_relationships",
        "aeir_objects",
        "aeir_model_versions",
    ):
        op.execute(f"DROP TRIGGER prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION prevent_{table}_mutation()")
    op.drop_table("aeir_change_events")
    op.drop_table("aeir_source_objects")
    op.drop_table("aeir_relationships")
    op.drop_table("aeir_objects")
    op.drop_table("aeir_model_versions")
