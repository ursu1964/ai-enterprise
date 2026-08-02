import uuid
from datetime import UTC, datetime

from ai_enterprise.api.routes.workflows import router
from ai_enterprise.api.workflow_schemas import WorkflowTransitionResponse
from ai_enterprise.application.workflow.service import workflow_state_for_project
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName
from ai_enterprise.infrastructure.database.models import ProjectModel
from ai_enterprise.infrastructure.database.workflow_models import WorkflowTransitionModel


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
