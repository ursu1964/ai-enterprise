import uuid
from datetime import UTC, datetime

import pytest

from ai_enterprise.api.routes.workflows import router
from ai_enterprise.api.workflow_schemas import WorkflowTransitionResponse
from ai_enterprise.application.workflow.service import WorkflowService, workflow_state_for_project
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName
from ai_enterprise.infrastructure.audit.event_hasher import verify_chain_records
from ai_enterprise.infrastructure.database.foundation_models import AuditChainRecordModel
from ai_enterprise.infrastructure.database.models import AuditEventModel, JobModel, ProjectModel
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowContextModel,
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


def test_workflow_relink_maps_created_project_to_startable_state() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.CREATED))

    assert state == WorkflowState.PROJECT_CREATED
    assert step is None
    assert action.startswith("Start the workflow")


def test_workflow_relink_route_is_registered() -> None:
    paths = {route.path for route in router.routes}

    assert "/projects/{project_id}/workflow/relink" in paths


def test_workflow_relink_maps_approved_work_package_to_manual_execution_review() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.WORK_PACKAGE_APPROVED))

    assert state == WorkflowState.WAITING_WORK_PACKAGE_APPROVAL
    assert step == WorkflowStepName.PLANNING
    assert "request execution" in action


def test_workflow_relink_sends_manifest_mismatch_to_manual_intervention() -> None:
    state, step, action = workflow_state_for_project(project(ProjectStatus.CREATED, "x"))

    assert state == WorkflowState.MANUAL_INTERVENTION
    assert step is None
    assert "manifest hash" in action


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
    assert audit.event_type == "workflow.started"
    assert audit.payload["audit_chain"]["record_hash"] == chain.record_hash
    assert chain.payload["event_type"] == "workflow.started"
    assert chain.payload["payload"]["workflow_id"] == str(workflow.id)
    assert job.job_type == "advance_workflow"
    assert verify_chain_records([
        {
            "stream_id": chain.stream_id,
            "sequence": chain.sequence,
            "previous_hash": chain.previous_hash,
            "record_hash": chain.record_hash,
            "payload": chain.payload,
        }
    ]) == []


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
    audit = next(item for item in session.added if isinstance(item, AuditEventModel))
    chain = next(item for item in session.added if isinstance(item, AuditChainRecordModel))
    assert audit.event_type == "workflow.relinked"
    assert chain.payload["event_type"] == "workflow.relinked"
    assert chain.payload["payload"]["state"] == WorkflowState.WAITING_REQUIREMENTS_APPROVAL
    assert verify_chain_records([
        {
            "stream_id": chain.stream_id,
            "sequence": chain.sequence,
            "previous_hash": chain.previous_hash,
            "record_hash": chain.record_hash,
            "payload": chain.payload,
        }
    ]) == []
