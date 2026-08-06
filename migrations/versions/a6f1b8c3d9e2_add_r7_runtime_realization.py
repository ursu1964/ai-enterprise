"""add R7 runtime realization

Revision ID: a6f1b8c3d9e2
Revises: 9e4a7c2d5f6b
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6f1b8c3d9e2"
down_revision: str | None = "9e4a7c2d5f6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APPEND_ONLY_TABLES = (
    "r7_runtime_providers",
    "r7_policy_evaluations",
    "r7_event_dispatches",
    "r7_deployment_runtime_syncs",
    "r7_runtime_ai_requests",
    "r7_plugin_bindings",
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
        "r7_runtime_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("provider_id", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("capabilities", jsonb, nullable=False),
        sa.Column("endpoint_ref", sa.String(300), nullable=True),
        sa.Column("configuration_document", jsonb, nullable=False),
        sa.Column("provider_document", jsonb, nullable=False),
        sa.Column("provider_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("project_id", "kind", "name", "version"),
        sa.UniqueConstraint("project_id", "provider_hash"),
    )
    for column in ("project_id", "provider_id", "kind", "name", "version", "status"):
        op.create_index(f"ix_r7_runtime_providers_{column}", "r7_runtime_providers", [column])

    op.create_table(
        "r7_policy_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column(
            "runtime_provider_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_providers.id"),
            nullable=True,
        ),
        sa.Column("evaluation_id", sa.String(40), nullable=False),
        sa.Column("action", sa.String(160), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("matched_policies", jsonb, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context_document", jsonb, nullable=False),
        sa.Column("evaluation_document", jsonb, nullable=False),
        sa.Column("evaluation_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "evaluation_id"),
        sa.UniqueConstraint("project_id", "evaluation_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "runtime_provider_id",
        "evaluation_id",
        "action",
        "resource",
        "decision",
    ):
        op.create_index(f"ix_r7_policy_evaluations_{column}", "r7_policy_evaluations", [column])

    op.create_table(
        "r7_event_dispatches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_event_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_events.id"),
            nullable=False,
        ),
        sa.Column(
            "runtime_provider_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_providers.id"),
            nullable=False,
        ),
        sa.Column("dispatch_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("subscriber_refs", jsonb, nullable=False),
        sa.Column("dispatch_document", jsonb, nullable=False),
        sa.Column("dispatch_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_event_id", "dispatch_id"),
        sa.UniqueConstraint("project_id", "dispatch_hash"),
    )
    for column in (
        "project_id",
        "runtime_event_id",
        "runtime_provider_id",
        "dispatch_id",
        "status",
    ):
        op.create_index(f"ix_r7_event_dispatches_{column}", "r7_event_dispatches", [column])

    op.create_table(
        "r7_deployment_runtime_syncs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column(
            "runtime_provider_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_providers.id"),
            nullable=False,
        ),
        sa.Column("sync_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("runtime_document", jsonb, nullable=False),
        sa.Column("sync_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "sync_id"),
        sa.UniqueConstraint("project_id", "sync_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "runtime_provider_id",
        "sync_id",
        "status",
    ):
        op.create_index(
            f"ix_r7_deployment_runtime_syncs_{column}", "r7_deployment_runtime_syncs", [column]
        )

    op.create_table(
        "r7_runtime_ai_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column(
            "runtime_provider_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_providers.id"),
            nullable=False,
        ),
        sa.Column(
            "policy_evaluation_id",
            sa.Uuid(),
            sa.ForeignKey("r7_policy_evaluations.id"),
            nullable=False,
        ),
        sa.Column("ai_request_id", sa.String(40), nullable=False),
        sa.Column("capability", sa.String(160), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("context_document", jsonb, nullable=False),
        sa.Column("response_document", jsonb, nullable=False),
        sa.Column("request_document", jsonb, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "ai_request_id"),
        sa.UniqueConstraint("project_id", "request_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "runtime_provider_id",
        "policy_evaluation_id",
        "ai_request_id",
        "capability",
        "status",
    ):
        op.create_index(f"ix_r7_runtime_ai_requests_{column}", "r7_runtime_ai_requests", [column])

    op.create_table(
        "r7_plugin_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "runtime_deployment_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_deployments.id"),
            nullable=False,
        ),
        sa.Column(
            "runtime_provider_id",
            sa.Uuid(),
            sa.ForeignKey("r7_runtime_providers.id"),
            nullable=False,
        ),
        sa.Column("binding_id", sa.String(40), nullable=False),
        sa.Column("plugin_name", sa.String(120), nullable=False),
        sa.Column("plugin_version", sa.String(80), nullable=False),
        sa.Column("compatibility_status", sa.String(40), nullable=False),
        sa.Column("requested_capabilities", jsonb, nullable=False),
        sa.Column("findings", jsonb, nullable=False),
        sa.Column("binding_document", jsonb, nullable=False),
        sa.Column("binding_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_deployment_id", "binding_id"),
        sa.UniqueConstraint("project_id", "binding_hash"),
    )
    for column in (
        "project_id",
        "runtime_deployment_id",
        "runtime_provider_id",
        "binding_id",
        "plugin_name",
        "plugin_version",
        "compatibility_status",
    ):
        op.create_index(f"ix_r7_plugin_bindings_{column}", "r7_plugin_bindings", [column])

    for table in APPEND_ONLY_TABLES:
        _immutable(table)


def downgrade() -> None:
    for table in reversed(APPEND_ONLY_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS prevent_{table}_mutation_trigger ON {table}")
        op.execute(f"DROP FUNCTION IF EXISTS prevent_{table}_mutation")
    op.drop_table("r7_plugin_bindings")
    op.drop_table("r7_runtime_ai_requests")
    op.drop_table("r7_deployment_runtime_syncs")
    op.drop_table("r7_event_dispatches")
    op.drop_table("r7_policy_evaluations")
    op.drop_table("r7_runtime_providers")
