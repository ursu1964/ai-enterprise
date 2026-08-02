import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.dashboard import dashboard_context, dashboard_telemetry_summary
from ai_enterprise.api.routes.projects import list_projects, project_intelligence
from ai_enterprise.config import get_settings
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.infrastructure.database.models import CrewRunModel, JobModel, ProjectModel
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowInstanceModel,
    WorkflowTransitionModel,
)
from ai_enterprise.infrastructure.organization.models import OrganizationModel
from ai_enterprise.infrastructure.performance.models import PerformanceMetricModel
from ai_enterprise.main import app


class Scalars:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class Session:
    def __init__(
        self,
        rows: list[Any],
        scalar: Any = None,
        scalar_rows: list[list[Any]] | None = None,
    ) -> None:
        self.rows = rows
        self.scalar_result = scalar
        self.scalar_rows = scalar_rows or []
        self.scalar_statement: object | None = None

    async def scalars(self, statement: object) -> Scalars:
        return Scalars(self.scalar_rows.pop(0) if self.scalar_rows else self.rows)

    async def scalar(self, statement: object) -> Any:
        self.scalar_statement = statement
        return self.scalar_result

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return self.rows[0] if self.rows else None


class DashboardSession:
    def __init__(self, scalar_rows: list[Any], scalars_rows: list[list[Any]]) -> None:
        self.scalar_rows = scalar_rows
        self.scalars_rows = scalars_rows

    async def scalar(self, statement: object) -> Any:
        return self.scalar_rows.pop(0) if self.scalar_rows else None

    async def scalars(self, statement: object) -> Scalars:
        return Scalars(self.scalars_rows.pop(0) if self.scalars_rows else [])


def project_reader(project_id: uuid.UUID) -> Actor:
    return Actor(
        "reader",
        "human",
        "operator",
        frozenset({"project.read"}),
        scopes=frozenset({f"project:{project_id}"}),
    )


def global_project_reader() -> Actor:
    return Actor(
        "reader",
        "human",
        "operator",
        frozenset({"project.read"}),
        scopes=frozenset({"global"}),
    )


def test_dashboard_page_links_operator_surfaces() -> None:
    client = TestClient(app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "AI Enterprise Command Center" in response.text
    assert "Documentation Hub" in response.text
    assert "/dashboard/documentation-hub" in response.text
    assert "Data source freshness" in response.text
    assert "Business decision board" in response.text
    assert "Guided Route" in response.text
    assert 'data-view="execution"' in response.text
    assert "Project Execution Control" in response.text
    assert "Parallel Projects" in response.text
    assert "Tasks and Crews" in response.text
    assert "Events and Telemetry" in response.text
    assert "executionGraph" in response.text
    assert "renderExecutionDashboard" in response.text
    assert "/api/v1/query/dashboard-manager" in response.text
    assert "Watch the Execution graph" in response.text
    assert "Start with a client idea or manifesto" in response.text
    assert "Open Demo" in response.text
    assert "Business State" in response.text
    assert "Recommended Next Move" in response.text
    assert "Vision Clarifier" in response.text
    assert "Download Client Manifest" in response.text
    assert "/dashboard/client-manifest-template" in response.text
    assert "Project Base Directory" in response.text
    assert "GitHub repository URL, optional" in response.text
    assert "parseClientManifestText" in response.text
    assert "fieldFromText" in response.text
    assert "source_document_type: \"client_project_manifest\"" in response.text
    assert (
        "Download the client manifest, send it to the client or requesting service"
        in response.text
    )
    assert "Practical Version" in response.text
    assert "Growth Version" in response.text
    assert "Visionary Version" in response.text
    assert "Route:" in response.text
    assert "Market:" in response.text
    assert "sourceStrip" in response.text
    assert "Living Enterprise Pulse" in response.text
    assert "Enterprise Ecosystem Modules" in response.text
    assert "Listen and Clarify" in response.text
    assert "Blueprint Marketplace" in response.text
    assert "What Needs Attention" in response.text
    assert "Start Here" in response.text
    assert "Enterprise Movement Graph" in response.text
    assert "Operating Picture Signals" in response.text
    assert "Factory Creation Graph" in response.text
    assert "Preview Mock Factory" in response.text
    assert "Launch Mock Factory Test" in response.text
    assert "Mock Autonomy" in response.text
    assert "/api/v1/project-formation/mock-factory/preview" in response.text
    assert "/api/v1/project-formation/mock-factory/start" in response.text
    assert "created, reused, blocked, and failed work" in response.text
    assert "Problem Resolution Graph" in response.text
    assert "#problemGraph.surface-graph" in response.text
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto" in response.text
    assert "overflow-wrap: anywhere" in response.text
    assert "Telemetry Pulse Graph" in response.text
    assert "Recovery and Work History" in response.text
    assert "Worker Capacity" in response.text
    assert "Current capacity" in response.text
    assert "Offline history" in response.text
    assert "Ready to accept enterprise work." in response.text
    assert "Historical worker instance. It is not part of current capacity." in response.text
    assert "Current action" in response.text
    assert "Reviewed history" in response.text
    assert "Business Telemetry" in response.text
    assert "Advanced raw metrics" in response.text
    assert "Blueprint Graph Hub" in response.text
    assert "Project Foundry Core" in response.text
    assert "/dashboard/project-foundry-core" in response.text
    assert "Authenticated Graph Context" in response.text
    assert "The dashboard will use the current organization and project" in response.text
    assert "Ready to check" in response.text
    assert "payload.nodes || payload.entities || []" in response.text
    assert "map is ready but empty" in response.text
    assert "operator headers" not in response.text
    assert "/api/v1/query/operating-picture" in response.text
    assert "/api/v1/project-formation/projects/" in response.text
    assert "Operating Picture" in response.text
    assert "unresolvedProblemJobs" in response.text
    assert "acknowledged by operator" in response.text
    assert "Needs workflow link" in response.text
    assert "Diagnostic detail" in response.text
    assert "movement-node" in response.text
    assert "surface-node" in response.text
    assert 'renderSurfaceNodes("operatingPictureSignals", important)' in response.text
    assert 'renderSurfaceNodes("movementGraph", important)' not in response.text
    assert (
        "const unresolved = state.operatingPicture.counts?.unresolved_problem_jobs"
        in response.text
    )
    assert "Economic Proof" in response.text
    assert "humanStatus" in response.text
    assert (
        "Project name, repository path, default branch, and project summary are required"
        in response.text
    )
    assert "friendlyLaunchError" in response.text
    assert "Technical detail" in response.text
    assert "reviewed history" in response.text
    assert "No current work needs action" in response.text
    assert "No current worker capacity is visible" in response.text
    assert "No projects are visible yet" in response.text
    assert "No active errors are attached to this project" in response.text
    assert "No records." not in response.text
    assert "Plan approved, execution not started" in response.text
    assert "Confidence:" in response.text
    assert "Owner:" in response.text
    assert "Completed Evidence" in response.text
    assert "Remaining Work" in response.text
    assert "Current Issues" in response.text
    assert "Historical samples" in response.text
    assert "Average phase" in response.text
    assert "lifecycle" in response.text
    assert "Source phase:" in response.text
    assert "Improvement proposals" in response.text
    assert "/api/v1/operator/jobs" in response.text
    assert "/metrics" in response.text
    assert "/dashboard/graphify" in response.text
    assert "/dashboard/demo" in response.text


def test_documentation_hub_explains_working_method_and_project_assets() -> None:
    client = TestClient(app)

    response = client.get("/dashboard/documentation-hub")

    assert response.status_code == 200
    assert "Documentation Hub" in response.text
    assert "Plan" in response.text
    assert "Execute" in response.text
    assert "Verify" in response.text
    assert "Document" in response.text
    assert "Operator Documents" in response.text
    assert "Graphs and Images" in response.text
    assert "Commands" in response.text
    assert "docs/enterprise/working-method.md" in response.text
    assert "/dashboard/graphify" in response.text


def test_project_foundry_core_downloads_aeos_foundation() -> None:
    client = TestClient(app)

    response = client.get("/dashboard/project-foundry-core")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="project-foundry-core-v0.1.md"'
    )
    assert "Project Foundry Core v0.1" in response.text
    assert "Project Intake Schema" in response.text
    assert "controlled autonomy" in response.text
    assert "Gate 6: release readiness" in response.text


def test_client_manifest_template_downloads_project_intake_document() -> None:
    client = TestClient(app)

    response = client.get("/dashboard/client-manifest-template")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == (
        'attachment; filename="ai-enterprise-client-project-manifest.md"'
    )
    assert "AI-Enterprise Client Project Manifest" in response.text
    assert "Project Base Directory:" in response.text
    assert "GitHub Repository URL:" in response.text
    assert "Default Branch: main" in response.text
    assert "Success Criteria" in response.text


def test_demo_story_page_explains_idea_to_reality() -> None:
    client = TestClient(app)

    response = client.get("/dashboard/demo")

    assert response.status_code == 200
    assert "AI Enterprise Demo Story" in response.text
    assert "Idea to Reality Map" in response.text
    assert "For Clients" in response.text
    assert "For Market Growth" in response.text
    assert "For Your Son" not in response.text
    assert "Marketing platform" in response.text
    assert "Production Route" in response.text


@pytest.mark.asyncio
async def test_list_projects_returns_current_projects() -> None:
    now = datetime.now(UTC)
    project = ProjectModel(
        id=uuid.uuid4(),
        name="Dashboard Project",
        description="A project visible from the enterprise dashboard.",
        repository_path="/home/user/projects/dashboard-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )

    response = await list_projects(
        Session([project]),  # type: ignore[arg-type]
        global_project_reader(),
    )

    assert len(response) == 1
    assert response[0].name == "Dashboard Project"


@pytest.mark.asyncio
async def test_list_projects_requires_global_project_read_scope() -> None:
    denied = project_reader(uuid.uuid4())

    with pytest.raises(HTTPException) as exc:
        await list_projects(Session([]), denied)  # type: ignore[arg-type]

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_project_intelligence_exposes_lifecycle_graph_data() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Intelligence Project",
        description="A project visible from the project intelligence graph.",
        repository_path="/home/user/projects/intelligence-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )
    workflow = WorkflowInstanceModel(
        id=workflow_id,
        project_id=project_id,
        definition_name="project_delivery",
        workflow_version="1",
        state="waiting_architecture_approval",
        current_step="architecture",
        context_version=1,
        correlation_id=uuid.uuid4(),
        optimistic_version=1,
        cancellation_requested_at=None,
        failure_code=None,
        failure_message=None,
        recommended_operator_action="Approve architecture.",
        started_at=now,
        completed_at=None,
        updated_at=now,
    )
    transition = WorkflowTransitionModel(
        id=uuid.uuid4(),
        workflow_id=workflow_id,
        sequence=1,
        previous_state="requirements_running",
        current_state="waiting_architecture_approval",
        step="architecture",
        actor_type="service",
        actor_id="workflow",
        reason="Architecture artifact is ready for review.",
        policy_evidence={},
        workflow_version="1",
        correlation_id=workflow.correlation_id,
        occurred_at=now,
    )
    run = CrewRunModel(
        id=uuid.uuid4(),
        project_id=project_id,
        crew_name="architecture",
        status="succeeded",
        input_payload={},
        output_payload={},
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    job = JobModel(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=None,
        job_type="plan_work_package",
        status="queued",
        payload={},
        priority=100,
        attempt_count=0,
        max_attempts=3,
        retry_count=0,
        available_at=now,
        lease_owner=None,
        lease_expires_at=None,
        lease_token=None,
        lease_version=0,
        last_failure_class=None,
        last_leased_at=None,
        last_error=None,
        completed_at=None,
        created_at=now,
    )

    session = Session([project], scalar=workflow, scalar_rows=[[transition], [job], [run], [], []])

    response = await project_intelligence(
        project_id,
        session,  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response["project"]["name"] == "Intelligence Project"
    assert "ORDER BY workflow_instances.updated_at DESC" in str(session.scalar_statement)
    assert response["workflow"]["state"] == "waiting_architecture_approval"
    assert response["project_phase"] == "architecture"
    assert response["project_status_phase"] == "intake"
    assert response["phases"][2]["status"] == "current"
    assert response["phases"][2]["label"] == "Architecture"
    assert response["phases"][2]["confidence"] == "live workflow"
    assert response["phases"][2]["owner_crew"] == "architecture"
    assert response["phases"][2]["next_action"] == "Approve architecture."
    assert response["phases"][2]["completed_evidence"] == ["1 workflow transition(s)"]
    assert response["phases"][2]["remaining_work"] == (
        "Finish the current gate and record the next transition."
    )
    assert response["phases"][2]["current_issues"] == []
    assert response["phases"][2]["historical_issues"] == []
    assert response["remaining_steps"]
    assert response["estimate"]["label"] == "Early estimate"
    assert response["estimate"]["confidence"] == "early"
    assert response["estimate"]["historical_sample_count"] == 0
    assert response["estimate"]["average_phase_minutes"] == 30
    assert response["crew"][0]["crew_name"] == "architecture"
    assert response["jobs"][0]["job_type"] == "plan_work_package"
    assert response["telemetry"]["always_active"] is True
    assert response["operating_state"]["degraded"] is False
    assert response["calibration"][0]["name"] == "manifest_integrity"
    assert response["improvements"]
    assert response["reuse"]["template"]["project_type"] == "dashboards_reporting"
    assert any(agent["agent_key"] == "dashboard_agent" for agent in response["specialist_agents"])
    assert response["economic_effects"]["reusable_asset_count"] == 0
    assert response["economic_effects"]["viability"] == "viable"
    assert response["blueprints"][0]["kind"] == "workflow_pattern"
    assert response["blueprints"][0]["lifecycle"] == "reviewed"
    assert response["blueprints"][0]["source_phase"] == "workflow"
    assert response["blueprints"][0]["reuse_proof"]["economic_viability"] == "viable"
    assert response["blueprints"][0]["reuse_proof"]["reuse_multiplier"] == 1.0
    assert response["blueprints"][0]["improvement_proposals"] == []
    assert response["blueprints"][1]["kind"] == "agent_team_pattern"
    assert response["blueprints"][2]["kind"] == "business_effect_pattern"


@pytest.mark.asyncio
async def test_project_intelligence_rejects_wrong_project_scope() -> None:
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Scoped Intelligence Project",
        description="A project protected by project-scoped authority.",
        repository_path="/home/user/projects/scoped-intelligence-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
    )

    with pytest.raises(HTTPException) as exc:
        await project_intelligence(
            project_id,
            Session([project]),  # type: ignore[arg-type]
            project_reader(uuid.uuid4()),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_project_intelligence_uses_observed_transition_timing_for_estimates() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    workflow_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Estimated Project",
        description="A project with transition timing for project intelligence estimates.",
        repository_path="/home/user/projects/estimated-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )
    workflow = WorkflowInstanceModel(
        id=workflow_id,
        project_id=project_id,
        definition_name="project_delivery",
        workflow_version="1",
        state="waiting_architecture_approval",
        current_step="architecture",
        context_version=1,
        correlation_id=uuid.uuid4(),
        optimistic_version=1,
        cancellation_requested_at=None,
        failure_code=None,
        failure_message=None,
        recommended_operator_action="Approve architecture.",
        started_at=now,
        completed_at=None,
        updated_at=now,
    )
    transitions = [
        WorkflowTransitionModel(
            id=uuid.uuid4(),
            workflow_id=workflow_id,
            sequence=index,
            previous_state=previous,
            current_state=current,
            step=step,
            actor_type="service",
            actor_id="workflow",
            reason=f"{current} reached.",
            policy_evidence={},
            workflow_version="1",
            correlation_id=workflow.correlation_id,
            occurred_at=occurred_at,
        )
        for index, (previous, current, step, occurred_at) in enumerate(
            [
                ("project_created", "requirements_running", "requirements", now),
                (
                    "requirements_running",
                    "waiting_requirements_approval",
                    "requirements",
                    now + timedelta(minutes=10),
                ),
                (
                    "waiting_requirements_approval",
                    "waiting_architecture_approval",
                    "architecture",
                    now + timedelta(minutes=30),
                ),
            ],
            start=1,
        )
    ]

    response = await project_intelligence(
        project_id,
        Session([project], scalar=workflow, scalar_rows=[transitions, [], [], [], []]),  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response["estimate"]["label"] == "Observed estimate"
    assert response["estimate"]["confidence"] == "observed"
    assert response["estimate"]["historical_sample_count"] == 2
    assert response["estimate"]["average_phase_minutes"] == 15
    assert response["estimate"]["estimated_minutes_remaining"] == 75


@pytest.mark.asyncio
async def test_project_intelligence_keeps_new_project_in_intake_until_workflow_starts() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Fresh Project",
        description="A project that has been created but has not started workflow execution.",
        repository_path="/home/user/projects/fresh-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "ai_software_development"},
        created_at=now,
        updated_at=now,
    )

    response = await project_intelligence(
        project_id,
        Session([project], scalar=None, scalar_rows=[[], [], [], [], []]),  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response["project_phase"] == "intake"
    assert response["project_status_phase"] == "intake"
    assert response["operating_state"]["degraded"] is True
    assert response["operating_state"]["recommended_action"].startswith("Start or relink")
    assert response["phases"][0]["name"] == "intake"
    assert response["phases"][0]["status"] == "current"
    assert response["phases"][1]["name"] == "requirements"
    assert response["phases"][1]["status"] == "remaining"
    assert "requirements" in response["remaining_steps"]


@pytest.mark.asyncio
async def test_project_intelligence_classifies_worker_errors_for_humans() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Problem Project",
        description="A project with a failed worker job that needs human explanation.",
        repository_path="/home/user/projects/problem-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "ai_software_development"},
        created_at=now,
        updated_at=now,
    )
    failed_job = JobModel(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=None,
        job_type="execute_work_package",
        status="failed",
        payload={},
        priority=100,
        attempt_count=1,
        max_attempts=3,
        retry_count=1,
        available_at=now,
        lease_owner=None,
        lease_expires_at=None,
        lease_token=None,
        lease_version=0,
        last_failure_class="git",
        last_leased_at=None,
        last_error="fatal: ambiguous argument HEAD",
        completed_at=None,
        created_at=now,
    )

    response = await project_intelligence(
        project_id,
        Session([project], scalar=None, scalar_rows=[[failed_job], [], [], []]),  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response["errors"][0]["explanation"] == (
        "The repository is not prepared for workflow execution."
    )
    assert response["errors"][0]["likely_cause"].startswith("The project path may be missing")
    assert response["errors"][0]["raw_diagnostic"] == "fatal: ambiguous argument HEAD"
    assert response["blueprints"][0]["lifecycle"] == "improved"
    assert response["blueprints"][0]["improvement_proposals"][0]["phase"] == "intake"
    assert response["blueprints"][0]["improvement_proposals"][0]["failure_class"] == "git"


@pytest.mark.asyncio
async def test_project_intelligence_treats_acknowledged_dead_letters_as_history() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Recovered Project",
        description="A project with historical dead-letter evidence already reviewed.",
        repository_path="/home/user/projects/recovered-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "ai_software_development"},
        created_at=now,
        updated_at=now,
    )
    acknowledged = JobModel(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=None,
        job_type="execute_work_package",
        status="dead_letter",
        payload={
            "operator_resolution": {
                "state": "acknowledged",
                "acknowledged_by": "operator",
                "acknowledged_at": now.isoformat(),
                "reason": "Historical failure reviewed.",
                "action_taken": "Preserved as evidence.",
            }
        },
        priority=100,
        attempt_count=3,
        max_attempts=3,
        retry_count=3,
        available_at=now,
        lease_owner=None,
        lease_expires_at=None,
        lease_token=None,
        lease_version=0,
        last_failure_class="execution",
        last_leased_at=None,
        last_error="Container produced no result.json",
        completed_at=None,
        created_at=now,
    )

    response = await project_intelligence(
        project_id,
        Session([project], scalar=None, scalar_rows=[[acknowledged], [], [], []]),  # type: ignore[arg-type]
        project_reader(project_id),
    )

    assert response["errors"] == []
    assert response["current_issues"] == []
    assert len(response["historical_issues"]) == 1
    assert response["historical_issues"][0]["explanation"] == (
        "Reviewed history. The evidence is preserved but is not current risk."
    )
    assert response["telemetry"]["problem_count"] == 0
    assert response["telemetry"]["historical_problem_count"] == 1
    assert response["telemetry"]["signal"] == "nominal"
    assert response["economic_effects"]["viability"] == "viable"
    assert response["calibration"][2]["name"] == "error_followup"
    assert response["calibration"][2]["status"] == "passed"


@pytest.mark.asyncio
async def test_dashboard_context_supplies_local_graph_authority_and_ids() -> None:
    now = datetime.now(UTC)
    organization = OrganizationModel(
        id=uuid.uuid4(),
        organization_key="ai-enterprise",
        name="AI Enterprise",
        status="active",
        policy_set_id=uuid.uuid4(),
        version=1,
    )
    project = ProjectModel(
        id=uuid.uuid4(),
        name="Context Project",
        description="A project used to populate dashboard graph context.",
        repository_path="/home/user/projects/context-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
        created_at=now,
        updated_at=now,
    )

    response = await dashboard_context(DashboardSession([organization, project], []))  # type: ignore[arg-type]

    assert response["organization_id"] == str(organization.id)
    assert response["project_id"] == str(project.id)
    assert response["actor_headers"]["X-Actor-Role"] == "platform-admin"
    assert response["authority"]["mode"] == "local-dashboard-context"


@pytest.mark.asyncio
async def test_dashboard_context_is_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            await dashboard_context(DashboardSession([], []))  # type: ignore[arg-type]
    finally:
        get_settings.cache_clear()

    assert getattr(exc.value, "status_code", None) == 403
    assert "disabled outside development" in str(getattr(exc.value, "detail", ""))


@pytest.mark.asyncio
async def test_dashboard_telemetry_summary_merges_runtime_and_governed_metrics() -> None:
    now = datetime.now(UTC)
    organization_id = uuid.uuid4()
    project = ProjectModel(
        id=uuid.uuid4(),
        name="Telemetry Project",
        description="A project used to populate dashboard telemetry summary.",
        repository_path="/home/user/projects/telemetry-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
        created_at=now,
        updated_at=now,
    )
    failed_job = JobModel(
        id=uuid.uuid4(),
        project_id=project.id,
        run_id=None,
        job_type="execute_work_package",
        status="failed",
        payload={},
        priority=100,
        attempt_count=1,
        max_attempts=3,
        retry_count=1,
        available_at=now,
        lease_owner=None,
        lease_expires_at=None,
        lease_token=None,
        lease_version=0,
        last_failure_class="runtime",
        last_leased_at=None,
        last_error="failure",
        completed_at=None,
        created_at=now,
    )
    metric = PerformanceMetricModel(
        id=uuid.uuid4(),
        organization_id=organization_id,
        scope_type="agent",
        scope_id=uuid.uuid4(),
        metric_key="delivery_quality",
        numerator=9,
        denominator=10,
        metric_value=Decimal("0.900000"),
        window_days=30,
        evidence_ids=[],
        evidence_set_hash="1" * 64,
        policy_version="performance-v1",
        calculated_at=now,
    )

    response = await dashboard_telemetry_summary(
        DashboardSession([], [[project], [failed_job], [metric]]),  # type: ignore[arg-type]
        organization_id,
    )

    assert response["runtime"]["problem_job_count"] == 1
    assert response["runtime"]["signal"] == "attention_required"
    assert response["governed_performance"]["metric_count"] == 1
    assert response["governed_performance"]["metrics"][0]["metric_name"] == "delivery_quality"
