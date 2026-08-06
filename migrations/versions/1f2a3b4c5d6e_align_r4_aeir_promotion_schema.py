"""align AEIR promotion tables for R4 canonical writes

Revision ID: 1f2a3b4c5d6e
Revises: 8c1d4e6f9a23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "1f2a3b4c5d6e"
down_revision: str | None = "8c1d4e6f9a23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE aeir_objects
            ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'draft',
            ADD COLUMN IF NOT EXISTS truth_status VARCHAR(30) NOT NULL DEFAULT 'asserted',
            ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS source_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS evidence_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS relationship_refs JSONB NOT NULL DEFAULT '[]'::jsonb,
            ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_aeir_objects_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_relationships_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_model_versions_model_sha256")
    op.execute("DROP INDEX IF EXISTS aeir_model_versions_model_sha256_key")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS status")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_objects_lifecycle_status
            ON aeir_objects (lifecycle_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_objects_truth_status
            ON aeir_objects (truth_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_objects_approval_status
            ON aeir_objects (approval_status)
        """
    )
    op.execute(
        """
        ALTER TABLE aeir_relationships
            ADD COLUMN IF NOT EXISTS lifecycle_status VARCHAR(30) NOT NULL DEFAULT 'draft',
            ADD COLUMN IF NOT EXISTS truth_status VARCHAR(30) NOT NULL DEFAULT 'asserted',
            ADD COLUMN IF NOT EXISTS approval_status VARCHAR(30) NOT NULL DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            ADD COLUMN IF NOT EXISTS valid_from VARCHAR(10) NOT NULL DEFAULT '2026-08-05',
            ADD COLUMN IF NOT EXISTS valid_to VARCHAR(10)
        """
    )
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS status")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_relationships_lifecycle_status
            ON aeir_relationships (lifecycle_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_relationships_truth_status
            ON aeir_relationships (truth_status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_aeir_relationships_approval_status
            ON aeir_relationships (approval_status)
        """
    )
    op.execute(
        """
        ALTER TABLE aeir_model_versions
            DROP CONSTRAINT IF EXISTS aeir_model_versions_model_sha256_key
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_aeir_model_versions_project_model_sha256'
            ) THEN
                ALTER TABLE aeir_model_versions
                    ADD CONSTRAINT uq_aeir_model_versions_project_model_sha256
                    UNIQUE (project_id, model_sha256);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE aeir_model_versions
            DROP CONSTRAINT IF EXISTS uq_aeir_model_versions_project_model_sha256
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_aeir_relationships_approval_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_relationships_truth_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_relationships_lifecycle_status")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS valid_to")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS valid_from")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS confidence")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS approval_status")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS truth_status")
    op.execute("ALTER TABLE aeir_relationships DROP COLUMN IF EXISTS lifecycle_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_objects_approval_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_objects_truth_status")
    op.execute("DROP INDEX IF EXISTS ix_aeir_objects_lifecycle_status")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS metadata")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS relationship_refs")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS evidence_refs")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS source_refs")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS approval_status")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS truth_status")
    op.execute("ALTER TABLE aeir_objects DROP COLUMN IF EXISTS lifecycle_status")
