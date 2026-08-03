import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from ai_enterprise.api.project_formation_schemas import FormationRequest
from ai_enterprise.application import mock_factory_autonomy
from ai_enterprise.application.mock_factory_autonomy import (
    MockEnterpriseAutonomyService,
    MockFactorySpec,
)
from ai_enterprise.application.project_formation_service import ProjectFormationService
from ai_enterprise.application.project_foundry_workspace import (
    ProjectFoundryWorkspaceError,
    ProjectFoundryWorkspaceService,
)
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import ArtifactType, ProjectStatus
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    ProjectModel,
)
from ai_enterprise.main import app


class FormationSession:
    def __init__(self, project: ProjectModel | None) -> None:
        self.project = project
        self.added: list[object] = []
        self.committed = False

    async def get(self, model: type, identity: uuid.UUID) -> object | None:
        return self.project

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def commit(self) -> None:
        self.committed = True


class PreviewSession:
    def __init__(self, scalar_rows: list[object | None]) -> None:
        self.scalar_rows = scalar_rows
        self.committed = False

    async def scalar(self, statement: object) -> object | None:
        return self.scalar_rows.pop(0) if self.scalar_rows else None

    async def commit(self) -> None:
        self.committed = True


def project(project_id: uuid.UUID) -> ProjectModel:
    now = datetime.now(UTC)
    return ProjectModel(
        id=project_id,
        name="Formation Project",
        description="A project used for deterministic formation pack tests.",
        repository_path="/home/user/projects/formation-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )


def test_project_formation_exposes_mock_factory_autonomy_route() -> None:
    paths = app.openapi()["paths"]

    assert "/api/v1/project-formation/mock-factory/start" in paths
    operation = paths["/api/v1/project-formation/mock-factory/start"]["post"]
    assert operation["responses"]["202"]["description"] == "Successful Response"
    assert "/api/v1/project-formation/mock-factory/preview" in paths
    preview = paths["/api/v1/project-formation/mock-factory/preview"]["get"]
    assert preview["responses"]["200"]["description"] == "Successful Response"
    assert "/api/v1/project-formation/projects/{project_id}/foundry-workspace" in paths
    foundry = paths["/api/v1/project-formation/projects/{project_id}/foundry-workspace"]["post"]
    assert foundry["responses"]["201"]["description"] == "Successful Response"
    schemas = app.openapi()["components"]["schemas"]
    launch_summary = schemas["MockFactoryLaunchSummaryResponse"]["properties"]
    project_result = schemas["MockFactoryProjectResponse"]["properties"]
    assert "review_needed_count" in launch_summary
    assert "recommended_first_project_id" in launch_summary
    assert "recommended_first_project_url" in launch_summary
    assert "result_category" in project_result


@pytest.mark.asyncio
async def test_mock_factory_preview_reports_ready_reuse_without_writes() -> None:
    existing = project(uuid.uuid4())
    existing.name = "AI Enterprise Product Factory Demo"
    existing.repository_path = "/home/user/projects/mock-enterprise/ai-enterprise-product-factory"
    session = PreviewSession([existing, None, None, None])

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).preview_mock_factory()

    assert response.status == "ready"
    assert response.ready_count == 4
    assert response.launch_plan.mode == "preview"
    assert response.launch_plan.created_count == 3
    assert response.launch_plan.reused_count == 1
    assert response.launch_plan.blocked_count == 0
    assert response.launch_plan.failed_count == 0
    assert response.launch_plan.review_needed_count == 0
    assert response.launch_plan.recommended_first_project_id == existing.id
    assert response.launch_plan.recommended_first_project_name == (
        "AI Enterprise Product Factory Demo"
    )
    assert response.launch_plan.recommended_first_project_url == (
        f"/dashboard?project={existing.id}"
    )
    assert "Start the mock factory" in response.launch_plan.operator_action
    assert response.would_create_count == 3
    assert response.would_reuse_count == 1
    assert response.would_block_count == 0
    assert response.reused_count == 1
    assert response.blocked_count == 0
    assert len(response.would_create) == 3
    assert response.would_reuse == [response.projects[0]]
    assert response.would_block == []
    assert response.projects[0].action == "reuse"
    assert response.projects[0].dashboard_url == f"/dashboard?project={existing.id}"
    assert response.recommended_first_project == response.projects[0]
    assert session.committed is False


@pytest.mark.asyncio
async def test_mock_factory_preview_groups_blocked_launch_items_without_writes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked_spec = MockFactorySpec(
        name="No Repository Path",
        description="Create a project with invalid launch information for preview checks.",
        repository_path="relative/path",
        project_type="dashboards_reporting",
        expected_outcome="A preview item that should be blocked before launch starts.",
        target_users=["operator"],
        constraints=["preview only"],
        known_systems=["factory"],
        deadline="today",
        budget_signal="demo",
    )
    monkeypatch.setattr(mock_factory_autonomy, "MOCK_FACTORY_SPECS", (blocked_spec,))
    session = PreviewSession([None])

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).preview_mock_factory()

    assert response.status == "blocked"
    assert response.ready_count == 0
    assert response.launch_plan.mode == "preview"
    assert response.launch_plan.created_count == 0
    assert response.launch_plan.reused_count == 0
    assert response.launch_plan.blocked_count == 1
    assert response.launch_plan.review_needed_count == 1
    assert response.launch_plan.recommended_first_project_id is None
    assert response.launch_plan.recommended_first_project_name is None
    assert response.launch_plan.recommended_first_project_url is None
    assert "Fix blocked launch information" in response.launch_plan.operator_action
    assert response.would_create_count == 0
    assert response.would_reuse_count == 0
    assert response.would_block_count == 1
    assert response.blocked_count == 1
    assert response.recommended_first_project is None
    assert response.projects[0].ready is False
    assert response.would_block[0].status == "blocked"
    assert response.would_block[0].issues == ["repository path must be absolute"]
    assert session.committed is False


@pytest.mark.asyncio
async def test_mock_factory_start_reports_structured_recommendation_and_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_project = project(uuid.uuid4())
    created_project.name = "Created Demo"
    created_project.repository_path = "/home/user/projects/mock-enterprise/created-demo"
    reused_project = project(uuid.uuid4())
    reused_project.name = "Reused Demo"
    reused_project.repository_path = "/home/user/projects/mock-enterprise/reused-demo"
    specs = (
        MockFactorySpec(
            name=created_project.name,
            description="Create a new mock factory project for launch-result checks.",
            repository_path=created_project.repository_path,
            project_type="dashboards_reporting",
            expected_outcome="A created project with a started workflow and inspection path.",
            target_users=["operator"],
            constraints=["test"],
            known_systems=["factory"],
            deadline="today",
            budget_signal="demo",
        ),
        MockFactorySpec(
            name=reused_project.name,
            description="Reuse an existing mock factory project for launch-result checks.",
            repository_path=reused_project.repository_path,
            project_type="dashboards_reporting",
            expected_outcome="A reused project with an existing workflow and waiting signal.",
            target_users=["operator"],
            constraints=["test"],
            known_systems=["factory"],
            deadline="today",
            budget_signal="demo",
        ),
    )
    workflow_by_project = {
        created_project.id: SimpleNamespace(id=uuid.uuid4()),
        reused_project.id: SimpleNamespace(id=uuid.uuid4()),
    }
    existing_workflow = SimpleNamespace(id=workflow_by_project[reused_project.id].id)
    session = PreviewSession([])

    async def existing_project(
        self: MockEnterpriseAutonomyService,
        spec: MockFactorySpec,
    ) -> ProjectModel | None:
        if spec.name == reused_project.name:
            return reused_project
        return None

    async def has_formation_pack(
        self: MockEnterpriseAutonomyService,
        project_value: ProjectModel,
    ) -> bool:
        return project_value.id == reused_project.id

    async def workflow_for_project(
        self: MockEnterpriseAutonomyService,
        project_value: ProjectModel,
    ) -> object | None:
        if project_value.id == reused_project.id:
            return existing_workflow
        return None

    async def create_project(
        self: MockEnterpriseAutonomyService,
        spec: MockFactorySpec,
        *,
        actor_id: str,
    ) -> ProjectModel:
        assert actor_id == "operator"
        return created_project

    async def workflow_start(self: object, *, project_id: uuid.UUID, actor_id: str) -> object:
        assert actor_id == "operator"
        return workflow_by_project[project_id]

    async def noop(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(mock_factory_autonomy, "MOCK_FACTORY_SPECS", specs)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_existing_project", existing_project)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_has_formation_pack", has_formation_pack)
    monkeypatch.setattr(
        MockEnterpriseAutonomyService, "_workflow_for_project", workflow_for_project
    )
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_create_project", create_project)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_create_formation_pack", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_continue_autonomy", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_ensure_autonomy_policy", noop)
    monkeypatch.setattr(MockEnterpriseAutonomyService, "_recover_demo_workflow", noop)
    monkeypatch.setattr(mock_factory_autonomy.WorkflowService, "start", workflow_start)
    monkeypatch.setattr(mock_factory_autonomy.WorkflowService, "notify", noop)

    response = await MockEnterpriseAutonomyService(  # type: ignore[arg-type]
        session, object()
    ).start_mock_factory(actor_id="operator")

    assert response.status == "started"
    assert response.created_count == 1
    assert response.reused_count == 1
    assert response.blocked_count == 0
    assert response.failed_count == 0
    assert response.launch_result.review_needed_count == 0
    assert response.launch_result.workflows_started_count == 1
    assert response.launch_result.workflows_waiting_count == 1
    assert response.launch_result.recommended_first_project_id == created_project.id
    assert response.launch_result.recommended_first_project_name == created_project.name
    assert response.launch_result.recommended_first_project_url == (
        f"/dashboard?project={created_project.id}"
    )
    assert response.projects[0].result_category == "created"
    assert response.projects[1].result_category == "reused_workflow_waiting"
    assert response.created == [response.projects[0]]
    assert response.reused == [response.projects[1]]


@pytest.mark.asyncio
async def test_project_formation_pack_requests_missing_information() -> None:
    project_id = uuid.uuid4()
    session = FormationSession(project(project_id))
    request = FormationRequest(
        project_id=project_id,
        idea="Create a live enterprise dashboard that explains project progress clearly.",
    )

    response = await ProjectFormationService(session).create_formation_pack(
        request, actor_id="operator"
    )

    artifacts = [item for item in session.added if isinstance(item, ArtifactModel)]
    audits = [item for item in session.added if isinstance(item, AuditEventModel)]
    assert response.status == "draft_needs_clarification"
    assert "target users" in response.missing_information
    assert response.next_action.startswith("Ask the client")
    assert len(response.artifacts) == 5
    assert len(artifacts) == 5
    assert artifacts[0].artifact_type == ArtifactType.PROJECT_BRIEF
    assert audits[0].event_type == "project_formation.pack_created"
    assert session.committed is True


@pytest.mark.asyncio
async def test_project_formation_pack_ready_for_approval() -> None:
    project_id = uuid.uuid4()
    session = FormationSession(project(project_id))
    request = FormationRequest(
        project_id=project_id,
        idea=(
            "Create a marketing platform dashboard with API integrations, telemetry, "
            "campaign planning, and reusable project blueprints."
        ),
        expected_outcome="A working platform demo with measurable project execution proof.",
        target_users=["client owner", "operator", "developer"],
        constraints=["local development first", "human approval before execution"],
        known_systems=["Git repository", "FastAPI dashboard"],
        deadline="first demo this week",
        budget_signal="reuse existing dashboard and workflow code",
    )

    response = await ProjectFormationService(session).create_formation_pack(
        request, actor_id="operator"
    )

    artifact_types = {item.artifact_type for item in response.artifacts}
    assert response.status == "ready_for_approval"
    assert response.missing_information == []
    assert response.next_action.startswith("Review the formation approval pack")
    assert ArtifactType.SOLUTION_PROPOSAL.value in artifact_types
    assert ArtifactType.FORMATION_APPROVAL_PACK.value in artifact_types
    assert response.traceability["manifest_hash"] == "0" * 64


@pytest.mark.asyncio
async def test_project_foundry_workspace_rejects_incomplete_intake(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    source_project.repository_path = str(tmp_path / "foundry-project")
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)

    with pytest.raises(ProjectFoundryWorkspaceError) as exc:
        await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
            session, settings
        ).generate_workspace(
            project_id,
            request=_foundry_request({"project": {"target_users": ["operator"]}}),
            actor_id="operator",
        )

    assert "scope section" in exc.value.missing_information
    assert "functional_requirements section" in exc.value.missing_information
    assert "project.expected_outcomes" in exc.value.missing_information
    assert session.committed is False


@pytest.mark.asyncio
async def test_project_foundry_workspace_creates_runtime_repository(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    workspace = tmp_path / "foundry-project"
    source_project.repository_path = str(workspace)
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)

    response = await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
        session, settings
    ).generate_workspace(
        project_id,
        request=_foundry_request(_complete_intake(), github_repository_url="https://github.com/acme/demo"),
        actor_id="operator",
    )

    assert response.status == "workspace_ready"
    assert response.workspace_path == str(workspace.resolve())
    assert response.github_repository_url == "https://github.com/acme/demo"
    assert response.missing_information == []
    assert "PROJECT.yaml" in response.created_files
    assert "AGENTS.md" in response.created_files
    assert "intake/project-intake.yaml" in response.created_files
    assert "requirements/requirements.yaml" in response.created_files
    assert "governance/authority-policy.yaml" in response.created_files
    assert "planning/execution-plan.yaml" in response.created_files
    assert (workspace / "PROJECT.yaml").exists()
    assert (workspace / "AGENTS.md").exists()
    assert (workspace / "requirements" / "traceability.csv").read_text(
        encoding="utf-8"
    ).startswith("requirement_id,source,status")
    assert "intake_hash:" in (workspace / "PROJECT.yaml").read_text(encoding="utf-8")
    assert source_project.repository_url == "https://github.com/acme/demo"
    assert session.committed is True


@pytest.mark.asyncio
async def test_project_foundry_workspace_reuses_existing_files_without_overwrite(tmp_path) -> None:
    project_id = uuid.uuid4()
    source_project = project(project_id)
    workspace = tmp_path / "foundry-project"
    source_project.repository_path = str(workspace)
    session = FormationSession(source_project)
    settings = Settings(repository_allowed_root=tmp_path)
    existing = workspace / "PROJECT.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text("custom: keep\n", encoding="utf-8")

    response = await ProjectFoundryWorkspaceService(  # type: ignore[arg-type]
        session, settings
    ).generate_workspace(
        project_id,
        request=_foundry_request(_complete_intake()),
        actor_id="operator",
    )

    assert "PROJECT.yaml" in response.reused_files
    assert existing.read_text(encoding="utf-8") == "custom: keep\n"


def _foundry_request(
    intake: dict,
    *,
    github_repository_url: str | None = None,
):
    from ai_enterprise.api.project_formation_schemas import FoundryWorkspaceRequest

    return FoundryWorkspaceRequest(
        intake=intake,
        github_repository_url=github_repository_url,
    )


def _complete_intake() -> dict:
    return {
        "project": {
            "name": "Demo Foundry Workspace",
            "description": "Create a complete Project Foundry runtime workspace.",
            "business_objective": "Generate a governed project repository from intake.",
            "target_users": ["operator", "client owner"],
            "project_type": "software_factory",
            "expected_outcomes": ["workspace ready", "traceable requirements"],
        },
        "scope": {
            "included": ["workspace generation", "governance files"],
            "excluded": ["production deployment"],
            "assumptions": ["human approval before execution"],
            "dependencies": ["GitHub repository"],
        },
        "functional_requirements": [
            {
                "id": "FR-001",
                "description": "Generate a source-of-truth repository structure.",
                "priority": "critical",
                "acceptance_criteria": ["PROJECT.yaml exists", "AGENTS.md exists"],
            }
        ],
        "non_functional_requirements": {
            "performance": "fast local generation",
            "scalability": "repeatable for many projects",
            "availability": "local-first",
            "security": "path boundary enforced",
            "privacy": "no production secrets in generated files",
            "accessibility": "plain text project files",
            "maintainability": "deterministic files",
        },
        "technical_constraints": {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "operating_systems": ["Linux"],
            "cloud_or_local": "local first",
            "existing_systems": ["AI Enterprise"],
            "prohibited_technologies": ["unapproved production secrets"],
        },
        "delivery": {
            "target_environment": "local",
            "milestones": ["intake", "workspace", "review"],
            "deployment_method": "GitHub collaboration after approval",
            "documentation_required": ["README", "PROJECT.yaml"],
            "support_model": "operator supervised",
        },
        "authority": {
            "allowed_actions": ["create workspace files"],
            "approval_required": ["repository push", "production deployment"],
            "prohibited_actions": ["delete production data"],
            "secret_access_policy": "no secrets in generated workspace",
            "production_access_policy": "human approval required",
        },
    }
