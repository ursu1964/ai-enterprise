from datetime import UTC, datetime, timedelta

from ai_enterprise.application.query.read_models import (
    meaning_for,
    source_contract,
    status_read_model,
)
from ai_enterprise.domain.agent_runtime.enums import (
    BindingStatus,
    RegistryStatus,
    ToolInvocationStatus,
)
from ai_enterprise.domain.architecture.enums import (
    ArchitectureArtifactStatus,
    ArchitectureReviewStatus,
    ArchitectureRevisionStatus,
    ArchitectureRunStatus,
)
from ai_enterprise.domain.enterprise_kernel.enums import (
    EnterpriseModuleState,
    EnterpriseResourceState,
    EnterpriseScheduleState,
    OrganizationalThreadState,
)
from ai_enterprise.domain.enums import (
    JobStatus,
    ProjectStatus,
    RunStatus,
    WorkPackageStatus,
)
from ai_enterprise.domain.evolution.enums import (
    ControlEffectiveness,
    LifecycleStatus,
    RolloutStatus,
)
from ai_enterprise.domain.execution.enums import ExecutionStatus
from ai_enterprise.domain.execution.enums import TestStatus as ExecutionTestStatus
from ai_enterprise.domain.integration.enums import (
    IntegrationApprovalDecision,
    IntegrationAttemptStatus,
    PatchStatus,
)
from ai_enterprise.domain.knowledge.enums import (
    CandidateStatus,
    ContradictionStatus,
    TemporalStatus,
)
from ai_enterprise.domain.recovery.enums import (
    RecoveryAssessmentStatus,
    RecoveryAttemptStatus,
    RollbackApprovalStatus,
)
from ai_enterprise.domain.resilience.enums import (
    BackupStatus,
    DisasterRecoveryStatus,
    RestoreStatus,
)
from ai_enterprise.domain.workflow.enums import WorkflowState


def test_every_workflow_state_has_specialized_operator_meaning() -> None:
    for state in WorkflowState:
        meaning = meaning_for(state)

        assert "no specialized explanation" not in meaning["meaning"]
        assert meaning["operator_action"]


def test_runtime_statuses_have_friendly_read_models() -> None:
    assert status_read_model("running")["status_label"] == "Work is running"
    assert status_read_model("draft")["status_label"] == "Draft"
    assert status_read_model("registered")["status_label"] == "Registered"
    assert status_read_model("validation_failed")["status_label"] == "Validation failed"


def test_core_read_model_states_have_specialized_operator_meaning() -> None:
    enum_groups = (
        ProjectStatus,
        RunStatus,
        JobStatus,
        WorkPackageStatus,
        RegistryStatus,
        BindingStatus,
        ToolInvocationStatus,
        EnterpriseResourceState,
        EnterpriseScheduleState,
        EnterpriseModuleState,
        OrganizationalThreadState,
    )

    for enum_group in enum_groups:
        for state in enum_group:
            meaning = meaning_for(state)

            assert "no specialized explanation" not in meaning["meaning"]
            assert meaning["operator_action"]


def test_delivery_recovery_and_learning_states_have_specialized_operator_meaning() -> None:
    enum_groups = (
        ArchitectureRunStatus,
        ArchitectureArtifactStatus,
        ArchitectureReviewStatus,
        ArchitectureRevisionStatus,
        ExecutionStatus,
        ExecutionTestStatus,
        PatchStatus,
        IntegrationApprovalDecision,
        IntegrationAttemptStatus,
        RecoveryAssessmentStatus,
        RollbackApprovalStatus,
        RecoveryAttemptStatus,
        BackupStatus,
        RestoreStatus,
        DisasterRecoveryStatus,
        CandidateStatus,
        TemporalStatus,
        ContradictionStatus,
        LifecycleStatus,
        RolloutStatus,
        ControlEffectiveness,
    )

    for enum_group in enum_groups:
        for state in enum_group:
            meaning = meaning_for(state)

            assert "no specialized explanation" not in meaning["meaning"]
            assert meaning["operator_action"]
            assert meaning["label"] != str(state)


def test_source_contract_reports_fresh_stale_empty_and_unavailable_states() -> None:
    now = datetime.now(UTC)

    fresh = source_contract(
        name="Jobs",
        endpoint="/api/v1/operator/jobs",
        record_count=2,
        latest_at=now - timedelta(seconds=30),
        stale_after=timedelta(minutes=5),
    )
    stale = source_contract(
        name="Workers",
        endpoint="/api/v1/operator/jobs/worker-instances",
        record_count=1,
        latest_at=now - timedelta(minutes=10),
        stale_after=timedelta(minutes=5),
    )
    empty = source_contract(
        name="Projects",
        endpoint="/api/v1/projects",
        record_count=0,
        empty_reason="No projects exist yet.",
    )
    unavailable = source_contract(
        name="Telemetry",
        endpoint="/dashboard/telemetry-summary",
        record_count=0,
        available=False,
    )

    assert fresh["state"] == "available"
    assert fresh["freshness"] == "fresh"
    assert fresh["meaning"]["label"] == "Available"
    assert fresh["freshness_age_seconds"] is not None
    assert fresh["stale_after_seconds"] == 300
    assert stale["state"] == "stale"
    assert stale["freshness"] == "stale"
    assert stale["meaning"]["label"] == "Stale"
    assert stale["operator_action"] == (
        "Refresh this source before making delivery decisions."
    )
    assert empty["state"] == "empty"
    assert empty["empty_reason"] == "No projects exist yet."
    assert unavailable["state"] == "unavailable"
    assert unavailable["freshness"] == "unavailable"
    assert unavailable["empty_reason"] is None


def test_factory_recovery_knowledge_and_evolution_states_have_friendly_meaning() -> None:
    states = {
        "intake",
        "ready",
        "blocked",
        "partial",
        "ready_for_approval",
        "draft_needs_clarification",
        "proposed",
        "promoted",
        "rejected",
        "pending_human_review",
        "revertible",
        "consumed",
        "expired",
        "timed_out",
        "passed",
        "tested",
        "closed",
        "denied",
        "analyzed",
        "simulated",
        "reviewed",
        "superseded",
        "stale",
        "disputed",
        "verified",
        "unsupported",
        "live workflow",
        "evidence backed",
        "early estimate",
        "needs review",
        "planned",
        "inferred",
        "early",
        "observed",
        "calibrated",
    }

    for state in states:
        meaning = meaning_for(state)

        assert meaning["label"] != state
        assert "no specialized explanation" not in meaning["meaning"]
        assert meaning["operator_action"]
