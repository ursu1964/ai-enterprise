"""align legacy physical schema with SQLAlchemy metadata

Revision ID: 2b7e9f0a1c3d
Revises: 1f2a3b4c5d6e
"""

from collections.abc import Sequence

from alembic import op

revision: str = "2b7e9f0a1c3d"
down_revision: str | None = "1f2a3b4c5d6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DROP_INDEXES = (
    "uq_architecture_active_run_project",
    "ix_audit_events_project_occurred_id",
    "ix_execution_events_execution_occurred_id",
    "ix_execution_runs_project_created_id",
    "ix_execution_test_results_run_sequence",
    "ix_job_execution_attempts_running",
    "ix_job_execution_attempts_revision_cycle_id",
    "ix_patch_review_events_review_occurred_id",
    "ix_patch_review_findings_review_severity_blocking",
    "ix_patch_review_runs_project_created_id",
    "ix_performance_evidence_agent",
    "ix_performance_evidence_workflow",
    "uq_requirements_revision_cycles_active_run",
    "ix_requirements_revision_requests_run",
    "uq_active_rollback_approval",
    "ix_worker_instances_liveness",
    "ix_integration_eligibilities_execution_run_id",
    "ix_workflow_instances_correlation_id",
    "ix_workflow_instances_project_id",
)


DROP_CONSTRAINTS = (
    ("cognitive_decisions", "fk_cognitive_decision_exact_record"),
    ("cognitive_decisions", "fk_cognitive_decision_org"),
    ("cognitive_links", "fk_cognitive_links_source_record_id_org"),
    ("cognitive_links", "fk_cognitive_links_target_record_id_org"),
    ("cognitive_records", "fk_cognitive_parent_org"),
    ("cognitive_records", "uq_cognitive_records_org_id"),
    ("cognitive_records", "uq_cognitive_records_org_id_hash"),
    ("ecosystem_gateway_invocations", "fk_ecosystem_invocations_connector_asset_id_org"),
    ("ecosystem_gateway_invocations", "fk_ecosystem_invocations_contract_asset_id_org"),
    ("ecosystem_approvals", "fk_ecosystem_approvals_asset_org"),
    ("ecosystem_assets", "fk_ecosystem_assets_entity_org"),
    ("ecosystem_edges", "fk_ecosystem_edges_source_entity_id_org"),
    ("ecosystem_edges", "fk_ecosystem_edges_target_entity_id_org"),
    ("ecosystem_assets", "uq_ecosystem_assets_org_id"),
    ("ecosystem_entities", "uq_ecosystem_entities_org_id"),
    ("integration_eligibilities", "integration_eligibilities_execution_run_id_key"),
    ("job_execution_attempts", "job_execution_attempts_job_id_fkey"),
    ("recovery_test_runs", "recovery_test_runs_stderr_artifact_id_fkey"),
    ("recovery_test_runs", "recovery_test_runs_stdout_artifact_id_fkey"),
    ("work_package_decomposition_runs", "fk_decomposition_run_parent_artifact"),
    ("workflow_instances", "workflow_instances_correlation_id_key"),
    ("workflow_instances", "workflow_instances_project_id_key"),
)


def upgrade() -> None:
    for index in DROP_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index}")
    for table, constraint in DROP_CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint}")

    op.execute(
        """
        ALTER TABLE ecosystem_approvals
            ADD CONSTRAINT uq_ecosystem_approvals_asset_hash_decision
            UNIQUE (asset_id, asset_hash, decision)
        """
    )
    op.execute(
        """
        ALTER TABLE engineering_drift_decisions
            ADD CONSTRAINT uq_engineering_drift_decisions_finding_hash_decision
            UNIQUE (finding_id, finding_hash, decision)
        """
    )
    op.execute(
        """
        ALTER TABLE engineering_specification_approvals
            ADD CONSTRAINT uq_engineering_specification_approvals_hash_decision
            UNIQUE (specification_id, specification_hash, decision)
        """
    )
    op.execute(
        """
        ALTER TABLE specification_generation_runs
            ADD CONSTRAINT uq_specification_generation_runs_input_hash
            UNIQUE (input_hash)
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_integration_eligibilities_execution_run_id
            ON integration_eligibilities (execution_run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_integration_attempt_runs_integration_attempt_id
            ON integration_attempt_runs (integration_attempt_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_integration_stage_executions_run_id
            ON integration_stage_executions (run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_job_execution_attempts_revision_cycle_id
            ON job_execution_attempts (revision_cycle_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_assessments_incident_id
            ON recovery_assessments (incident_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_attempt_runs_recovery_attempt_id
            ON recovery_attempt_runs (recovery_attempt_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_attempts_status
            ON recovery_attempts (status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_incidents_integration_attempt_id
            ON recovery_incidents (integration_attempt_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_stage_executions_run_id
            ON recovery_stage_executions (run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_recovery_test_runs_recovery_attempt_id
            ON recovery_test_runs (recovery_attempt_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requirements_artifact_lineage_revision_cycle_id
            ON requirements_artifact_lineage (revision_cycle_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requirements_revision_cycles_requirements_run_id
            ON requirements_revision_cycles (requirements_run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requirements_revision_cycles_status
            ON requirements_revision_cycles (status)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requirements_revision_requests_requirements_run_id
            ON requirements_revision_requests (requirements_run_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rollback_approvals_recovery_assessment_id
            ON rollback_approvals (recovery_assessment_id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_workflow_instances_correlation_id
            ON workflow_instances (correlation_id)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_workflow_instances_project_id
            ON workflow_instances (project_id)
        """
    )

    op.execute(
        """
        ALTER TABLE job_execution_attempts
            ADD CONSTRAINT job_execution_attempts_job_id_fkey
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        """
    )
    op.execute(
        """
        ALTER TABLE recovery_test_runs
            ADD CONSTRAINT recovery_test_runs_stderr_artifact_id_fkey
            FOREIGN KEY (stderr_artifact_id) REFERENCES artifacts(id)
        """
    )
    op.execute(
        """
        ALTER TABLE recovery_test_runs
            ADD CONSTRAINT recovery_test_runs_stdout_artifact_id_fkey
            FOREIGN KEY (stdout_artifact_id) REFERENCES artifacts(id)
        """
    )
    op.execute(
        """
        ALTER TABLE work_package_decomposition_runs
            ADD CONSTRAINT fk_decomposition_run_parent_artifact
            FOREIGN KEY (parent_artifact_id)
            REFERENCES work_package_decomposition_artifacts(id)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE work_package_decomposition_runs "
        "DROP CONSTRAINT IF EXISTS fk_decomposition_run_parent_artifact"
    )
    op.execute(
        "ALTER TABLE recovery_test_runs "
        "DROP CONSTRAINT IF EXISTS recovery_test_runs_stdout_artifact_id_fkey"
    )
    op.execute(
        "ALTER TABLE recovery_test_runs "
        "DROP CONSTRAINT IF EXISTS recovery_test_runs_stderr_artifact_id_fkey"
    )
    op.execute(
        "ALTER TABLE job_execution_attempts "
        "DROP CONSTRAINT IF EXISTS job_execution_attempts_job_id_fkey"
    )
    op.execute("DROP INDEX IF EXISTS ix_workflow_instances_project_id")
    op.execute("DROP INDEX IF EXISTS ix_workflow_instances_correlation_id")
    op.execute("DROP INDEX IF EXISTS ix_rollback_approvals_recovery_assessment_id")
    op.execute("DROP INDEX IF EXISTS ix_requirements_revision_requests_requirements_run_id")
    op.execute("DROP INDEX IF EXISTS ix_requirements_revision_cycles_status")
    op.execute("DROP INDEX IF EXISTS ix_requirements_revision_cycles_requirements_run_id")
    op.execute("DROP INDEX IF EXISTS ix_requirements_artifact_lineage_revision_cycle_id")
    op.execute("DROP INDEX IF EXISTS ix_recovery_test_runs_recovery_attempt_id")
    op.execute("DROP INDEX IF EXISTS ix_recovery_stage_executions_run_id")
    op.execute("DROP INDEX IF EXISTS ix_recovery_incidents_integration_attempt_id")
    op.execute("DROP INDEX IF EXISTS ix_recovery_attempts_status")
    op.execute("DROP INDEX IF EXISTS ix_recovery_attempt_runs_recovery_attempt_id")
    op.execute("DROP INDEX IF EXISTS ix_recovery_assessments_incident_id")
    op.execute("DROP INDEX IF EXISTS ix_job_execution_attempts_revision_cycle_id")
    op.execute("DROP INDEX IF EXISTS ix_integration_stage_executions_run_id")
    op.execute("DROP INDEX IF EXISTS ix_integration_attempt_runs_integration_attempt_id")
    op.execute("DROP INDEX IF EXISTS ix_integration_eligibilities_execution_run_id")
    op.execute(
        "ALTER TABLE specification_generation_runs "
        "DROP CONSTRAINT IF EXISTS uq_specification_generation_runs_input_hash"
    )
    op.execute(
        "ALTER TABLE engineering_specification_approvals "
        "DROP CONSTRAINT IF EXISTS uq_engineering_specification_approvals_hash_decision"
    )
    op.execute(
        "ALTER TABLE engineering_drift_decisions "
        "DROP CONSTRAINT IF EXISTS uq_engineering_drift_decisions_finding_hash_decision"
    )
    op.execute(
        "ALTER TABLE ecosystem_approvals "
        "DROP CONSTRAINT IF EXISTS uq_ecosystem_approvals_asset_hash_decision"
    )
