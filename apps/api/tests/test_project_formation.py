import uuid
from datetime import UTC, datetime

import pytest

from ai_enterprise.api.project_formation_schemas import FormationRequest
from ai_enterprise.application.mock_factory_autonomy import MockEnterpriseAutonomyService
from ai_enterprise.application.project_formation_service import ProjectFormationService
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
    assert response.reused_count == 1
    assert response.blocked_count == 0
    assert response.projects[0].action == "reuse"
    assert response.projects[0].dashboard_url == f"/dashboard?project={existing.id}"
    assert response.recommended_first_project == response.projects[0]
    assert session.committed is False


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
