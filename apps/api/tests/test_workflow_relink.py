import uuid
from datetime import UTC, datetime

import pytest

from ai_enterprise.api.routes.workflows import router
from ai_enterprise.api.workflow_schemas import WorkflowTransitionResponse
from ai_enterprise.application.workflow.service import (
    WorkflowService,
    workflow_relink_decision_for_project,
    workflow_state_for_project,
)
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.enums import (
    WorkflowEventName,
    WorkflowState,
    WorkflowStepName,
)
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel, JobModel, ProjectModel
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowContextModel,
    WorkflowInstanceModel,
    WorkflowTransitionModel,
)


class WorkflowWriteSession:
    def __init__(self, row: ProjectModel) -> None:
        self.row = row
        self.added: list[object] = []
        self.scalar_calls = 0
        self.committed = False

    async def scalar(self, statement: object) -> object | None:
        self.scalar_calls += 1
        if self.scalar_calls == 1:
            return None
        chain_records = [row for row in self.added if isinstance(row, AuditChainRecordModel)]
        return chain_records[-1] if chain_records else None

    async def get(self, model: type, identity: uuid.UUID) -> object | None:
        return self.row

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, row: object) -> None:
        return None


class CancelRepository:
    def __init__(self, workflow: WorkflowInstanceModel) -> None:
        self.workflow = workflow
        self.transitions: list[WorkflowState] = []

    async def get(self, workflow_id: uuid.UUID, lock: bool = False) -> WorkflowInstanceModel:
        return self.workflow

    async def context(self, workflow: WorkflowInstanceModel) -> WorkflowContext:
        return WorkflowContext(
            workflow_id=workflow.id,
            project_id=workflow.project_id,
            current_state=WorkflowState.PROJECT_CREATED,
            correlation_id=workflow.correlation_id,
            actor_id="operator",
        )

    async def append_transition(
        self,
        *,
        workflow: WorkflowInstanceModel,
        context: WorkflowContext,
        next_state: WorkflowState,
        step: object,
        actor_type: str,
        actor_id: str,
        reason: str,
        checkpoint: bool,
    ) -> WorkflowContext:
        workflow.state = next_state
        self.transitions.append(next_state)
        return context.evolved(current_state=next_state)


def project(status: str, manifest_hash: str | None = None) -> ProjectModel:
    now = datetime.now(UTC)
    manifest = {"schema_version": "1.0", "name": "Relinked Project"}
    return ProjectModel(
        id=uuid.uuid4(),
        name="Relinked Project",
        description="A project used to recover missing workflow linkage.",
        repository_path="/home/user/projects/relinked-project",
        repository_url=None,
        default_branch="main",
        status=status,
        manifest_hash=manifest_hash or hash_json(manifest),
        manifest=manifest,
        created_at=now,
        updated_at=now,
    )


def assert_single_valid_chain(
    session: WorkflowWriteSession, event_type: str
) -> AuditChainRecordModel:
    chain = next(item for item in session.added if isinstance(item, AuditChainRecordModel))
    assert chain.payload["event_type"] == event_type
    assert verify_chain_records([
        {
            "stream_id": chain.stream_id,
            "sequence": chain.sequence,
            "previous_hash": chain.previous_hash,
            "record_hash": chain.record_hash,
            "payload": chain.payload,
        }
    ]) == []
    return chain


def test_workflow_relink_maps_created_project_to_startable_state() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.CREATED))

    assert state == WorkflowState.PROJECT_CREATED
    assert step is None
    assert action.startswith("Start the workflow")


@pytest.mark.parametrize(
    ("status", "expected_state", "expected_step", "expected_action"),
    [
        (
            ProjectStatus.CREATED,
            WorkflowState.PROJECT_CREATED,
            None,
            "Start the workflow",
        ),
        (
            ProjectStatus.REQUIREMENTS_QUEUED,
            WorkflowState.REQUIREMENTS_RUNNING,
            WorkflowStepName.REQUIREMENTS,
            "requirements job",
        ),
        (
            ProjectStatus.REQUIREMENTS_RUNNING,
            WorkflowState.REQUIREMENTS_RUNNING,
            WorkflowStepName.REQUIREMENTS,
            "requirements job",
        ),
        (
            ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL,
            WorkflowState.WAITING_REQUIREMENTS_APPROVAL,
            WorkflowStepName.REQUIREMENTS,
            "approve or request changes",
        ),
        (
            ProjectStatus.REQUIREMENTS_APPROVED,
            WorkflowState.REQUIREMENTS_RUNNING,
            WorkflowStepName.REQUIREMENTS,
            "Advance the workflow to architecture",
        ),
        (
            ProjectStatus.REQUIREMENTS_REJECTED,
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.REQUIREMENTS,
            "Requirements were rejected",
        ),
        (
            ProjectStatus.REQUIREMENTS_FAILED,
            WorkflowState.FAILED,
            WorkflowStepName.REQUIREMENTS,
            "Requirements work failed",
        ),
        (
            ProjectStatus.ARCHITECTURE_QUEUED,
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowStepName.ARCHITECTURE,
            "architecture job",
        ),
        (
            ProjectStatus.ARCHITECTURE_RUNNING,
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowStepName.ARCHITECTURE,
            "architecture job",
        ),
        (
            ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL,
            WorkflowState.WAITING_ARCHITECTURE_APPROVAL,
            WorkflowStepName.ARCHITECTURE,
            "approve or request changes",
        ),
        (
            ProjectStatus.ARCHITECTURE_APPROVED,
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowStepName.ARCHITECTURE,
            "Advance the workflow to work-package planning",
        ),
        (
            ProjectStatus.ARCHITECTURE_REJECTED,
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.ARCHITECTURE,
            "Architecture was rejected",
        ),
        (
            ProjectStatus.ARCHITECTURE_FAILED,
            WorkflowState.FAILED,
            WorkflowStepName.ARCHITECTURE,
            "Architecture work failed",
        ),
        (
            ProjectStatus.WORK_PACKAGE_QUEUED,
            WorkflowState.PLANNING_RUNNING,
            WorkflowStepName.PLANNING,
            "planning jobs",
        ),
        (
            ProjectStatus.WORK_PACKAGE_PLANNING,
            WorkflowState.PLANNING_RUNNING,
            WorkflowStepName.PLANNING,
            "planning jobs",
        ),
        (
            ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL,
            WorkflowState.WAITING_WORK_PACKAGE_APPROVAL,
            WorkflowStepName.PLANNING,
            "approve or request changes",
        ),
        (
            ProjectStatus.WORK_PACKAGE_APPROVED,
            WorkflowState.PLANNING_RUNNING,
            WorkflowStepName.PLANNING,
            "Advance the workflow to execution",
        ),
        (
            ProjectStatus.WORK_PACKAGE_REJECTED,
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.PLANNING,
            "Work package was rejected",
        ),
        (
            ProjectStatus.WORK_PACKAGE_FAILED,
            WorkflowState.FAILED,
            WorkflowStepName.PLANNING,
            "Work-package planning failed",
        ),
    ],
)
def test_workflow_relink_maps_each_project_status_to_explicit_protocol_action(
    status: ProjectStatus,
    expected_state: WorkflowState,
    expected_step: WorkflowStepName | None,
    expected_action: str,
) -> None:
    state, step, action = workflow_state_for_project(project(status))

    assert state == expected_state
    assert step == expected_step
    assert expected_action in action


def test_workflow_relink_mapping_is_exhaustive_for_project_statuses() -> None:
    covered_statuses = {
        ProjectStatus.CREATED,
        ProjectStatus.REQUIREMENTS_QUEUED,
        ProjectStatus.REQUIREMENTS_RUNNING,
        ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL,
        ProjectStatus.REQUIREMENTS_APPROVED,
        ProjectStatus.REQUIREMENTS_REJECTED,
        ProjectStatus.REQUIREMENTS_FAILED,
        ProjectStatus.ARCHITECTURE_QUEUED,
        ProjectStatus.ARCHITECTURE_RUNNING,
        ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL,
        ProjectStatus.ARCHITECTURE_APPROVED,
        ProjectStatus.ARCHITECTURE_REJECTED,
        ProjectStatus.ARCHITECTURE_FAILED,
        ProjectStatus.WORK_PACKAGE_QUEUED,
        ProjectStatus.WORK_PACKAGE_PLANNING,
        ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL,
        ProjectStatus.WORK_PACKAGE_APPROVED,
        ProjectStatus.WORK_PACKAGE_REJECTED,
        ProjectStatus.WORK_PACKAGE_FAILED,
    }

    assert covered_statuses == set(ProjectStatus)


@pytest.mark.parametrize(
    "status",
    [
        ProjectStatus.REQUIREMENTS_APPROVED,
        ProjectStatus.ARCHITECTURE_APPROVED,
        ProjectStatus.WORK_PACKAGE_APPROVED,
    ],
)
def test_workflow_relink_marks_approved_statuses_ready_to_advance(
    status: ProjectStatus,
) -> None:
    decision = workflow_relink_decision_for_project(project(status))

    assert decision.advance_ready is True
    assert decision.decision_already_made is True
    assert "Advance the workflow" in decision.operator_action
    assert "approve or request changes" not in decision.operator_action


@pytest.mark.parametrize(
    "status",
    [
        ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL,
        ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL,
        ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL,
    ],
)
def test_workflow_relink_marks_awaiting_approval_statuses_as_waiting_for_decision(
    status: ProjectStatus,
) -> None:
    decision = workflow_relink_decision_for_project(project(status))

    assert decision.advance_ready is False
    assert decision.decision_already_made is False
    assert "approve or request changes" in decision.operator_action


def test_workflow_relink_route_is_registered() -> None:
    paths = {route.path for route in router.routes}

    assert "/projects/{project_id}/workflow/relink" in paths


def test_workflow_relink_maps_approved_work_package_to_advance_ready_execution() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.WORK_PACKAGE_APPROVED))

    assert state == WorkflowState.PLANNING_RUNNING
    assert step == WorkflowStepName.PLANNING
    assert "execution" in action


def test_workflow_relink_sends_manifest_mismatch_to_manual_intervention() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.CREATED, "x"))

    assert state == WorkflowState.MANUAL_INTERVENTION
    assert step is None
    assert "manifest hash" in action


def test_workflow_relink_sends_unknown_legacy_status_to_manual_intervention() -> None:
    decision = workflow_relink_decision_for_project(project("legacy_execution_review"))

    assert decision.workflow_state == WorkflowState.MANUAL_INTERVENTION
    assert decision.current_step is None
    assert decision.advance_ready is False
    assert decision.decision_already_made is False
    assert "not mapped" in decision.operator_action


def test_relinked_workflow_history_accepts_bootstrap_previous_state() -> None:
    now = datetime.now(UTC)
    transition = WorkflowTransitionModel(
        id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
        sequence=1,
        previous_state="unlinked",
        current_state=WorkflowState.PROJECT_CREATED,
        step=None,
        actor_type="human",
        actor_id="local-dashboard-admin",
        reason="Relink historical project.",
        policy_evidence={},
        workflow_version="1.0",
        correlation_id=uuid.uuid4(),
        occurred_at=now,
    )

    response = WorkflowTransitionResponse.model_validate(transition)

    assert response.previous_state == "unlinked"
    assert response.current_state == WorkflowState.PROJECT_CREATED


@pytest.mark.asyncio
async def test_workflow_start_writes_tamper_evident_audit_chain() -> None:
    row = project(ProjectStatus.CREATED)
    session = WorkflowWriteSession(row)

    workflow = await WorkflowService(session).start(project_id=row.id, actor_id="operator")  # type: ignore[arg-type]

    audit = next(item for item in session.added if isinstance(item, AuditEventModel))
    chain = next(item for item in session.added if isinstance(item, AuditChainRecordModel))
    job = next(item for item in session.added if isinstance(item, JobModel))

    assert session.committed is True
    assert workflow.project_id == row.id
    assert audit.event_type == WorkflowEventName.STARTED
    assert audit.payload["audit_chain"]["record_hash"] == chain.record_hash
    assert chain.payload["event_type"] == WorkflowEventName.STARTED
    assert chain.payload["payload"]["workflow_id"] == str(workflow.id)
    assert job.job_type == "advance_workflow"
    assert_single_valid_chain(session, WorkflowEventName.STARTED)


@pytest.mark.asyncio
async def test_workflow_relink_writes_tamper_evident_audit_chain() -> None:
    row = project(ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL)
    session = WorkflowWriteSession(row)

    workflow = await WorkflowService(session).relink_project(  # type: ignore[arg-type]
        project_id=row.id,
        actor_id="operator",
        reason="Recover missing workflow.",
    )

    assert session.committed is True
    context = next(item for item in session.added if isinstance(item, WorkflowContextModel))
    transition = next(item for item in session.added if isinstance(item, WorkflowTransitionModel))
    assert isinstance(context, WorkflowContextModel)
    assert isinstance(transition, WorkflowTransitionModel)
    assert workflow.state == WorkflowState.WAITING_REQUIREMENTS_APPROVAL
    assert context.context["metadata"]["relink"] == {
        "project_status": ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL,
        "relink_reason": "Review requirements evidence and approve or request changes.",
        "advance_ready": False,
        "decision_already_made": False,
    }
    audit = next(item for item in session.added if isinstance(item, AuditEventModel))
    chain = next(item for item in session.added if isinstance(item, AuditChainRecordModel))
    assert audit.event_type == WorkflowEventName.RELINKED
    assert chain.payload["event_type"] == WorkflowEventName.RELINKED
    assert chain.payload["payload"]["state"] == WorkflowState.WAITING_REQUIREMENTS_APPROVAL
    assert chain.payload["payload"]["advance_ready"] is False
    assert chain.payload["payload"]["decision_already_made"] is False
    assert_single_valid_chain(session, WorkflowEventName.RELINKED)


@pytest.mark.asyncio
async def test_workflow_cancel_writes_tamper_evident_audit_chain() -> None:
    row = project(ProjectStatus.CREATED)
    session = WorkflowWriteSession(row)
    workflow = WorkflowInstanceModel(
        id=uuid.uuid4(),
        project_id=row.id,
        definition_name="vertical_slice",
        workflow_version="1.0",
        state=WorkflowState.PROJECT_CREATED,
        current_step=None,
        context_version=1,
        correlation_id=uuid.uuid4(),
        optimistic_version=1,
    )
    service = WorkflowService(session)  # type: ignore[arg-type]
    repository = CancelRepository(workflow)
    service.repository = repository  # type: ignore[assignment]

    result = await service.cancel(
        workflow_id=workflow.id,
        actor_id="operator",
        reason="Operator stopped the run.",
    )

    audit = next(item for item in session.added if isinstance(item, AuditEventModel))
    chain = assert_single_valid_chain(session, WorkflowEventName.CANCELLED)
    assert session.committed is True
    assert result.state == WorkflowState.CANCELLED
    assert repository.transitions == [WorkflowState.CANCELLING, WorkflowState.CANCELLED]
    assert audit.event_type == WorkflowEventName.CANCELLED
    assert audit.payload["audit_chain"]["record_hash"] == chain.record_hash
    assert chain.payload["payload"]["reason"] == "Operator stopped the run."
