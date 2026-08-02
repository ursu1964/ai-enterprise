import uuid
from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.query_platform import (
    dashboard_manager,
    operating_picture,
    project_operating_picture,
)
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
)
from ai_enterprise.infrastructure.database.workflow_models import WorkflowInstanceModel
from ai_enterprise.infrastructure.jobs.models import WorkerInstanceModel


class Scalars:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class QuerySession:
    def __init__(
        self, scalars_rows: list[list[object]], project: ProjectModel | None = None
    ) -> None:
        self.scalars_rows = scalars_rows
        self.project = project

    async def scalars(self, statement: object) -> Scalars:
        return Scalars(self.scalars_rows.pop(0) if self.scalars_rows else [])

    async def get(self, model: type, identity: uuid.UUID) -> object | None:
        return self.project


def actor(
    role: str = "operator",
    actor_type: str = "human",
    scopes: frozenset[str] = frozenset({"global"}),
) -> Actor:
    return Actor(
        subject="local-dashboard-admin",
        actor_type=actor_type,
        role=role,
        capabilities=frozenset({"query.read"}),
        scopes=scopes,
    )


def project_query_actor(project_id: uuid.UUID) -> Actor:
    return actor(scopes=frozenset({f"project:{project_id}"}))


def project(now: datetime, project_id: uuid.UUID | None = None) -> ProjectModel:
    return ProjectModel(
        id=project_id or uuid.uuid4(),
        name="Operating Picture Project",
        description="A project shown through the query-platform read model.",
        repository_path="/home/user/projects/operating-picture-project",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={"project_type": "dashboards_reporting"},
        created_at=now,
        updated_at=now,
    )


def workflow(now: datetime, project_id: uuid.UUID) -> WorkflowInstanceModel:
    return WorkflowInstanceModel(
        id=uuid.uuid4(),
        project_id=project_id,
        definition_name="project_delivery",
        workflow_version="1",
        state="requirements_running",
        current_step="requirements",
        context_version=1,
        correlation_id=uuid.uuid4(),
        optimistic_version=1,
        cancellation_requested_at=None,
        failure_code=None,
        failure_message=None,
        recommended_operator_action="Watch the requirements artifact and approve when ready.",
        started_at=now,
        completed_at=None,
        updated_at=now,
    )


def job(now: datetime, project_id: uuid.UUID, status: str = "queued") -> JobModel:
    return JobModel(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=None,
        job_type="run_requirements_crew",
        status=status,
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


def worker(now: datetime) -> WorkerInstanceModel:
    return WorkerInstanceModel(
        id=uuid.uuid4(),
        worker_id="worker-1",
        profile="workflow",
        status="online",
        started_at=now,
        last_heartbeat_at=now,
        stopped_at=None,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_operating_picture_returns_human_readable_graph() -> None:
    now = datetime.now(UTC)
    row = project(now)
    rows = [
        [row],
        [workflow(now, row.id)],
        [job(now, row.id)],
        [worker(now)],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]

    response = await operating_picture(QuerySession(rows), actor())  # type: ignore[arg-type]

    assert response["query_policy"]["mode"] == "read_only_projection"
    assert response["headline"]["state"] == "active"
    assert "project(s)" in response["headline"]["summary"]
    assert response["recommendations"][0]["next_action"]
    assert any(node["kind"] == "project" for node in response["graph"]["nodes"])
    assert any(edge["label"] == "executes" for edge in response["graph"]["edges"])


@pytest.mark.asyncio
async def test_dashboard_manager_projects_tasks_crews_and_live_graph() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    row = project(now, project_id)
    crew_run = CrewRunModel(
        id=uuid.uuid4(),
        project_id=project_id,
        crew_name="requirements",
        status="succeeded",
        input_payload={},
        output_payload={},
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    audit = AuditEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        event_type="ManifestoIngested",
        actor_type="human",
        actor_id="local-dashboard-admin",
        payload={},
        created_at=now,
    )
    rows = [
        [row],
        [workflow(now, project_id)],
        [job(now, project_id, "queued"), job(now, project_id, "succeeded")],
        [crew_run],
        [],
        [worker(now)],
        [audit],
        [],
    ]

    response = await dashboard_manager(QuerySession(rows), actor())  # type: ignore[arg-type]

    assert response["query_policy"]["mode"] == "dashboard_manager_projection"
    assert response["headline"]["state"] == "active"
    assert response["headline"]["meaning"]["label"] == "Active"
    assert response["totals"]["projects"] == 1
    assert response["totals"]["tasks_done"] == 1
    assert response["totals"]["tasks_active"] == 1
    assert response["totals"]["online_workers"] == 1
    assert response["projects"][0]["phase"] == "requirements"
    assert response["projects"][0]["state_meaning"]["label"] == "Active"
    assert response["projects"][0]["status_label"] == "Ready to start"
    assert response["projects"][0]["status_meaning"]["label"] == "Ready to start"
    assert response["projects"][0]["tasks"]["done"] == 1
    assert response["projects"][0]["tasks"]["active"] == 1
    assert response["projects"][0]["crews"][0]["name"] == "run requirements crew"
    assert response["projects"][0]["crews"][0]["status_label"] == "Waiting for worker capacity"
    assert response["projects"][0]["recent_events"][0]["event_type"] == "ManifestoIngested"
    assert response["sections"]["projects"]["available"] is True
    assert response["sections"]["projects"]["record_count"] == 1
    assert response["sections"]["workers"]["record_count"] == 1
    assert response["sections"]["graph"]["operator_action"] == (
        "Use this section for the current operating picture."
    )
    assert any(node["kind"] == "project" for node in response["graph"]["nodes"])
    assert any(edge["label"] == "assigns" for edge in response["graph"]["edges"])
    assert all("status_label" in node for node in response["graph"]["nodes"])


@pytest.mark.asyncio
async def test_dashboard_manager_explains_empty_source_sections() -> None:
    response = await dashboard_manager(
        QuerySession([[], [], [], [], [], [], [], []]), actor()
    )  # type: ignore[arg-type]

    assert response["headline"]["state"] == "waiting_for_manifesto"
    assert response["sections"]["projects"]["state"] == "empty"
    assert response["sections"]["projects"]["empty_reason"] == (
        "No manifesto project has been created yet."
    )
    assert response["sections"]["graph"]["meaning"]["label"] == "No records yet"
    assert response["sections"]["workers"]["operator_action"] == (
        "Start worker services before scaling parallel work."
    )


@pytest.mark.asyncio
async def test_operating_picture_excludes_acknowledged_dead_letters_from_current_health() -> None:
    now = datetime.now(UTC)
    row = project(now)
    acknowledged = job(now, row.id, "dead_letter")
    acknowledged.payload = {
        "operator_resolution": {
            "state": "acknowledged",
            "acknowledged_by": "operator",
            "acknowledged_at": now.isoformat(),
            "reason": "Historical failure already reviewed.",
            "action_taken": "Preserved as evidence.",
        }
    }
    rows = [
        [row],
        [workflow(now, row.id)],
        [acknowledged],
        [worker(now)],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]

    response = await operating_picture(QuerySession(rows), actor())  # type: ignore[arg-type]

    assert response["headline"]["state"] == "active"
    assert response["counts"]["unresolved_problem_jobs"] == 0
    assert response["counts"]["acknowledged_problem_jobs"] == 1
    assert response["status_counts"]["job_resolution"] == {"acknowledged": 1}


@pytest.mark.asyncio
async def test_operating_picture_graph_exposes_friendly_status_labels() -> None:
    now = datetime.now(UTC)
    row = project(now)
    rows = [
        [row],
        [workflow(now, row.id)],
        [job(now, row.id, "dead_letter")],
        [worker(now)],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    ]

    response = await operating_picture(QuerySession(rows), actor())  # type: ignore[arg-type]

    job_node = next(node for node in response["graph"]["nodes"] if node["kind"] == "job")
    assert job_node["status"] == "dead_letter"
    assert job_node["status_label"] == "Reviewed failure or recovery needed"
    assert "dead_letter" not in job_node["human_summary"]
    assert job_node["status_meaning"]["operator_action"]


@pytest.mark.asyncio
async def test_operating_picture_blocks_non_human_actor() -> None:
    with pytest.raises(HTTPException) as exc:
        await operating_picture(
            QuerySession([]),  # type: ignore[arg-type]
            actor(role="worker", actor_type="service", scopes=frozenset()),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_operating_picture_requires_global_query_scope() -> None:
    with pytest.raises(HTTPException) as exc:
        await operating_picture(
            QuerySession([]),  # type: ignore[arg-type]
            actor(scopes=frozenset({f"project:{uuid.uuid4()}"})),
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_project_operating_picture_links_project_evidence() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    row = project(now, project_id)
    artifact = ArtifactModel(
        id=uuid.uuid4(),
        project_id=project_id,
        run_id=None,
        artifact_type="project_manifest",
        media_type="application/json",
        content="{}",
        content_hash="1" * 64,
        created_at=now,
    )
    crew_run = CrewRunModel(
        id=uuid.uuid4(),
        project_id=project_id,
        crew_name="requirements",
        status="succeeded",
        input_payload={},
        output_payload={},
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    audit = AuditEventModel(
        id=uuid.uuid4(),
        project_id=project_id,
        event_type="ProjectCreated",
        actor_type="human",
        actor_id="local-dashboard-admin",
        payload={},
        created_at=now,
    )
    rows = [[workflow(now, project_id)], [job(now, project_id)], [artifact], [crew_run], [audit]]

    response = await project_operating_picture(
        project_id, QuerySession(rows, row), project_query_actor(project_id)  # type: ignore[arg-type]
    )

    assert response["project"]["id"] == project_id
    assert response["headline"]["state"] == "active"
    assert response["status_counts"]["artifacts"]["project_manifest"] == 1
    assert response["latest_audit_events"][0]["human_summary"]
    assert any(node["kind"] == "job" for node in response["graph"]["nodes"])


@pytest.mark.asyncio
async def test_project_operating_picture_rejects_wrong_project_scope() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    row = project(now, project_id)

    with pytest.raises(HTTPException) as exc:
        await project_operating_picture(
            project_id,
            QuerySession([], row),  # type: ignore[arg-type]
            project_query_actor(uuid.uuid4()),
        )

    assert exc.value.status_code == 403
