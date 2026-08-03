import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException

from ai_enterprise.api.dependencies import Actor
from ai_enterprise.api.routes.query_platform import (
    dashboard_manager,
    operating_picture,
    project_operating_picture,
    router,
)
from ai_enterprise.application.query.read_models import meaning_for
from ai_enterprise.domain.enums import ProjectStatus
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    CrewRunModel,
    JobModel,
    ProjectModel,
    WorkPackageModel,
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


def test_dashboard_read_model_compatibility_route_is_mounted() -> None:
    paths = {route.path for route in router.routes}
    assert "/query/dashboard-manager" in paths
    assert "/query/dashboard-read-model" in paths


def test_recoverable_statuses_use_plain_recovery_language() -> None:
    statuses = [
        "requirements_failed",
        "architecture_failed",
        "work_package_failed",
        "execution_failed",
        "validation_failed",
        "failed_validation",
        "integration_failed",
        "verification_failed",
        "patch_apply_failed",
        "tests_failed",
        "test_failed",
        "commit_failed",
        "push_failed",
        "remote_verification_failed",
    ]

    meanings = [meaning_for(status) for status in statuses]
    combined = " ".join(
        value
        for meaning in meanings
        for value in (
            meaning["label"],
            meaning["meaning"],
            meaning["operator_action"],
        )
    )

    assert meaning_for("requirements_failed")["label"] == "Requirements need recovery"
    assert meaning_for("execution_failed")["operator_action"] == (
        "Review execution proof and improve or retry through governance."
    )
    assert meaning_for("patch_apply_failed")["label"] == "Patch apply needs recovery"
    assert "needs recovery" in combined
    for forbidden in (
        "failed before",
        "Review failed",
        "execution logs",
        "Validation failed",
        "Patch apply failed",
        "Tests failed",
        "Test failed",
        "Commit failed",
        "Push failed",
        "Remote verification failed",
        "needs repair",
        "Inspect validation",
        "Inspect test",
        "Inspect workspace",
        "could not create",
        "could not be applied",
    ):
        assert forbidden not in combined


def test_attention_statuses_use_evidence_and_connection_language() -> None:
    meanings = {
        status: meaning_for(status)
        for status in (
            "unknown",
            "partial",
            "unavailable",
        )
    }
    combined = " ".join(
        value
        for meaning in meanings.values()
        for value in (
            meaning["label"],
            meaning["meaning"],
            meaning["operator_action"],
        )
    )

    assert meanings["unknown"]["label"] == "Needs evidence"
    assert meanings["partial"]["operator_action"] == (
        "Review created, reused, blocked, and review-needed launch items."
    )
    assert meanings["unavailable"]["label"] == "Source needs connection review"
    assert "source freshness proof" in meanings["unavailable"]["operator_action"]
    for forbidden in (
        "Unknown",
        "Source unavailable",
        "API logs",
        "failed launch items",
        "blocked or failed",
    ):
        assert forbidden not in combined


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


def work_package(now: datetime, project_id: uuid.UUID, run_id: uuid.UUID) -> WorkPackageModel:
    return WorkPackageModel(
        id=uuid.uuid4(),
        project_id=project_id,
        planning_run_id=run_id,
        artifact_id=None,
        status="approved",
        title="Reusable implementation package",
        objective="Preserve a proven implementation path for reuse.",
        repository_url=None,
        base_commit_sha="1" * 64,
        source_requirements_artifact_id=uuid.uuid4(),
        source_requirements_hash="2" * 64,
        source_architecture_artifact_id=uuid.uuid4(),
        source_architecture_hash="3" * 64,
        contract={"scope": "reuse-ready"},
        contract_hash="4" * 64,
        created_at=now,
        updated_at=now,
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
    assert "project(s)" not in response["headline"]["summary"]
    assert "1 project" in response["headline"]["summary"]
    assert response["recommendations"][0]["next_action"]
    assert any(node["kind"] == "project" for node in response["graph"]["nodes"])
    assert any(edge["label"] == "executes" for edge in response["graph"]["edges"])
    operator_actions = [
        node["status_meaning"]["operator_action"] for node in response["graph"]["nodes"]
    ]
    assert all("failure signals" not in action for action in operator_actions)


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
    assert response["projects"][0]["phase_detail"]["label"] == "Requirements"
    assert response["projects"][0]["phase_detail"]["confidence"] == "live workflow"
    assert response["projects"][0]["phase_detail"]["confidence_detail"] == {
        "state": "live workflow",
        "score": 85,
        "label": "Live workflow",
        "severity": "ok",
        "meaning": "A governed workflow is linked and actively explains this phase.",
        "operator_action": (
            "Use workflow events and phase proof when deciding the next action."
        ),
        "evidence_count": 3,
        "current_blocker_count": 0,
    }
    assert response["projects"][0]["phase_detail"]["proof_status"]["state"] == (
        "evidence_backed"
    )
    assert response["projects"][0]["phase_detail"]["proof_status"]["evidence_count"] == 3
    assert response["projects"][0]["phase_detail"]["owner_crew"] == "requirements"
    assert response["projects"][0]["phase_detail"]["completed_evidence"] == [
        "linked workflow",
        "1 completed worker job",
        "1 crew signal",
    ]
    assert response["projects"][0]["phase_detail"]["remaining_work"] == (
        "Continue the workflow and preserve proof for this phase."
    )
    assert response["projects"][0]["phase_detail"]["next_action"] == (
        "Watch the requirements artifact and approve when ready."
    )
    assert response["projects"][0]["phase_detail"]["issue_summary"] == {
        "current_count": 0,
        "historical_count": 0,
        "state": "clear",
        "operator_action": "No active blockers are attached to this phase.",
    }
    assert response["projects"][0]["state_meaning"]["label"] == "Active"
    assert response["projects"][0]["status_label"] == "Ready to start"
    assert response["projects"][0]["status_meaning"]["label"] == "Ready to start"
    assert response["projects"][0]["workflow"]["status_label"] == (
        "Requirements work running"
    )
    assert response["projects"][0]["workflow"]["status_meaning"]["label"] == (
        "Requirements work running"
    )
    assert response["projects"][0]["telemetry"]["signal_meaning"]["label"] == "Healthy"
    assert response["projects"][0]["tasks"]["done"] == 1
    assert response["reuse"]["blueprint_candidates"][0]["project_id"] == str(project_id)
    assert response["reuse"]["blueprint_candidates"][0]["project_type"] == (
        "dashboards_reporting"
    )
    assert response["reuse"]["blueprint_candidates"][0]["lifecycle"] == "candidate"
    assert response["reuse"]["blueprint_candidates"][0]["readiness_level"] == (
        "needs_more_proof"
    )
    assert response["reuse"]["blueprint_candidates"][0]["evidence_count"] == 2
    assert response["reuse"]["blueprint_candidates"][0]["evidence_sources"] == {
        "succeeded_jobs": 1,
        "succeeded_crew_runs": 1,
        "work_packages": 0,
    }
    assert "collect more proof" in response["reuse"]["blueprint_candidates"][0][
        "reuse_readiness"
    ]
    assert response["reuse"]["blueprint_candidates"][0]["promotion_blockers"] == [
        "at least two succeeded jobs",
        "at least one work package",
    ]
    assert response["reuse"]["blueprint_candidates"][0]["criteria_status"] == [
        {
            "criterion": "at least two succeeded jobs",
            "actual": 1,
            "required": 2,
            "passed": False,
        },
        {
            "criterion": "at least one succeeded crew run",
            "actual": 1,
            "required": 1,
            "passed": True,
        },
        {
            "criterion": "at least one work package",
            "actual": 0,
            "required": 1,
            "passed": False,
        },
    ]
    assert response["reuse"]["blueprint_candidates"][0]["readiness_detail"]["label"] == (
        "Needs more proof"
    )
    assert "promotion would be premature" in response["reuse"]["blueprint_candidates"][0][
        "readiness_detail"
    ]["meaning"]
    assert response["reuse"]["readiness"]["catalog_review_ready"] == 0
    assert response["reuse"]["readiness"]["needs_more_proof"] == 1
    assert "proof review" in response["reuse"]["operator_action"]
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
async def test_dashboard_manager_marks_reuse_candidate_ready_for_catalog_review() -> None:
    now = datetime.now(UTC)
    project_id = uuid.uuid4()
    row = project(now, project_id)
    run_id = uuid.uuid4()
    crew_run = CrewRunModel(
        id=run_id,
        project_id=project_id,
        crew_name="planning",
        status="succeeded",
        input_payload={},
        output_payload={},
        error_message=None,
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    first_job = job(now, project_id, "succeeded")
    second_job = job(now, project_id, "succeeded")
    package = work_package(now, project_id, run_id)
    rows = [
        [row],
        [workflow(now, project_id)],
        [first_job, second_job],
        [crew_run],
        [package],
        [],
        [],
        [],
    ]

    response = await dashboard_manager(QuerySession(rows), actor())  # type: ignore[arg-type]

    candidate = response["reuse"]["blueprint_candidates"][0]
    assert candidate["lifecycle"] == "reviewed"
    assert candidate["readiness_level"] == "catalog_review_ready"
    assert candidate["promotion_blockers"] == []
    assert candidate["evidence_count"] == 4
    assert candidate["readiness_detail"]["label"] == "Ready for catalog review"
    assert "enough operational proof" in candidate["readiness_detail"]["meaning"]
    assert response["reuse"]["readiness"]["catalog_review_ready"] == 1
    assert response["reuse"]["readiness"]["needs_more_proof"] == 0
    assert response["reuse"]["next_catalog_review"]["project_id"] == str(project_id)
    assert response["reuse"]["next_catalog_review"]["project_name"] == row.name
    assert response["reuse"]["next_catalog_review"]["evidence_count"] == 4
    assert response["reuse"]["next_catalog_review"]["evidence_bundle"]["sources"] == {
        "succeeded_jobs": 2,
        "succeeded_crew_runs": 1,
        "work_packages": 1,
    }
    assert response["reuse"]["next_catalog_review"]["evidence_bundle"][
        "promotion_blockers"
    ] == []
    assert response["reuse"]["next_catalog_review"]["evidence_bundle"][
        "review_criteria"
    ] == [
        "at least two succeeded jobs",
        "at least one succeeded crew run",
        "at least one work package",
    ]
    assert response["reuse"]["next_catalog_review"]["evidence_bundle"][
        "criteria_status"
    ] == [
        {
            "criterion": "at least two succeeded jobs",
            "actual": 2,
            "required": 2,
            "passed": True,
        },
        {
            "criterion": "at least one succeeded crew run",
            "actual": 1,
            "required": 1,
            "passed": True,
        },
        {
            "criterion": "at least one work package",
            "actual": 1,
            "required": 1,
            "passed": True,
        },
    ]


@pytest.mark.asyncio
async def test_dashboard_manager_splits_current_and_historical_project_issues() -> None:
    now = datetime.now(UTC)
    row = project(now)
    active_failure = job(now, row.id, "dead_letter")
    active_failure.last_error = "result.json missing"
    acknowledged = job(now, row.id, "dead_letter")
    acknowledged.payload = {
        "operator_resolution": {
            "state": "acknowledged",
            "acknowledged_by": "operator",
            "acknowledged_at": now.isoformat(),
            "reason": "Reviewed during recovery.",
            "action_taken": "Preserved as training evidence.",
        }
    }
    rows = [
        [row],
        [workflow(now, row.id)],
        [active_failure, acknowledged],
        [],
        [],
        [],
        [],
        [],
    ]

    response = await dashboard_manager(QuerySession(rows), actor())  # type: ignore[arg-type]

    phase_detail = response["projects"][0]["phase_detail"]
    assert response["projects"][0]["tasks"]["problems"] == 1
    assert phase_detail["confidence"] == "needs review"
    assert phase_detail["confidence_detail"]["label"] == "Needs review"
    assert phase_detail["confidence_detail"]["score"] == 35
    assert phase_detail["confidence_detail"]["current_blocker_count"] == 1
    assert phase_detail["remaining_work"] == (
        "Resolve current issues before scaling this project."
    )
    assert phase_detail["issue_summary"]["current_count"] == 1
    assert phase_detail["issue_summary"]["historical_count"] == 1
    assert phase_detail["issue_summary"]["state"] == "needs_action"
    assert phase_detail["current_issues"][0]["label"] == "Recovery review needed"
    assert phase_detail["historical_issues"][0]["label"] == "Reviewed history"
    assert phase_detail["historical_issues"][0]["resolution"]["state"] == "acknowledged"


@pytest.mark.asyncio
async def test_dashboard_manager_proposes_guardrails_for_repeated_failure_classes() -> None:
    now = datetime.now(UTC)
    row = project(now)
    first = job(now, row.id, "dead_letter")
    second = job(now, row.id, "failed")
    first.last_failure_class = "runtime"
    second.last_failure_class = "runtime"
    rows = [
        [row],
        [workflow(now, row.id)],
        [first, second],
        [],
        [],
        [],
        [],
        [],
    ]

    response = await dashboard_manager(QuerySession(rows), actor())  # type: ignore[arg-type]

    proposal = response["recovery"]["improvement_proposals"][0]
    assert proposal["title"] == "Guardrail proposal: runtime"
    assert proposal["failure_class"] == "runtime"
    assert proposal["current_failure_count"] == 2
    assert len(proposal["source_jobs"]) == 2
    assert proposal["source_jobs"][0]["job_type"] == "run_requirements_crew"
    assert proposal["source_jobs"][0]["attempt_count"] == 0
    assert proposal["status"] == "proposed"
    assert proposal["evolution_endpoint"] == "/api/v1/enterprise-evolution/improvements"
    assert proposal["evidence_status"]["state"] == "evidence_required"
    assert proposal["evidence_status"]["ready_to_submit"] is False
    assert "operator_job_attempts" in proposal["evidence_status"]["required_sources"]
    assert "immutable evidence reference" in proposal["evidence_status"]["missing"][0]
    assert proposal["evidence_status"]["submission_endpoint"] == (
        "/api/v1/enterprise-evolution/improvements"
    )
    assert "bind immutable evidence" in proposal["evidence_status"]["operator_action"]
    assert proposal["improvement_draft"]["improvement_key"] == (
        "operations.failure.runtime_guardrail"
    )
    assert proposal["improvement_draft"]["category"] == "operations"
    assert proposal["improvement_draft"]["evidence_required"] is True
    assert proposal["improvement_draft"]["evidence_collection"][0]["type"] == (
        "operator_job_attempts"
    )
    assert "/api/v1/operator/jobs/by-id/" in (
        proposal["improvement_draft"]["evidence_collection"][0]["endpoint"]
    )
    assert proposal["improvement_draft"]["risk_document"]["requires_human_review"] is True
    assert proposal["improvement_draft"]["title"] == "Reduce repeated runtime problems"
    assert "runtime problems" in proposal["improvement_draft"]["expected_benefit"]
    assert "runtime failures" not in proposal["improvement_draft"]["expected_benefit"]
    assert "recovery checklist" in proposal["recommendation"]
    assert "recurring problem class" in proposal["recommendation"]
    assert "inspect attempts" in proposal["operator_action"]
    assert "problem class" in proposal["operator_action"]
    assert "failure class" not in proposal["operator_action"]
    guardrail = response["reuse"]["guardrail_candidates"][0]
    assert guardrail["proposal_key"] == "operations.failure.runtime_guardrail"
    assert guardrail["failure_class"] == "runtime"
    assert guardrail["current_failure_count"] == 2
    assert guardrail["evidence_status"]["ready_to_submit"] is False
    assert guardrail["readiness_level"] == "evidence_required"
    assert "immutable evidence reference" in guardrail["promotion_blockers"][0]
    assert response["reuse"]["readiness"]["guardrails_evidence_required"] == 1
    assert "1 guardrail candidate" in response["reuse"]["summary"]
    assert "recurring problems into guarded templates" in response["reuse"]["operator_action"]
    assert "repeated failures" not in response["reuse"]["operator_action"]


@pytest.mark.asyncio
async def test_dashboard_manager_explains_empty_source_sections() -> None:
    response = await dashboard_manager(
        QuerySession([[], [], [], [], [], [], [], []]), actor()
    )  # type: ignore[arg-type]

    assert response["headline"]["state"] == "waiting_for_manifesto"
    assert response["sections"]["projects"]["state"] == "empty"
    assert response["sections"]["projects"]["empty_reason"] == (
        "Waiting for the first manifesto project to be created or ingested."
    )
    assert response["sections"]["workflows"]["empty_reason"] == (
        "Waiting for durable workflow records to be linked to visible projects."
    )
    assert response["sections"]["jobs"]["empty_reason"] == (
        "Waiting for the first worker job to be queued or executed for these projects."
    )
    assert response["sections"]["workers"]["empty_reason"] == (
        "Waiting for the first worker heartbeat."
    )
    assert response["sections"]["telemetry"]["empty_reason"] == (
        "Waiting for governed metrics or audit events for this view."
    )
    assert response["sections"]["graph"]["empty_reason"] == (
        "Waiting for project nodes after the first visible project record."
    )
    assert response["sections"]["graph"]["meaning"]["label"] == "Waiting for first records"
    assert response["sections"]["graph"]["operator_action"] == (
        "Waiting for first governed records. Create or link records when this section "
        "should begin showing live evidence."
    )
    assert response["sections"]["workers"]["operator_action"] == (
        "Start worker services before scaling parallel work."
    )


@pytest.mark.asyncio
async def test_dashboard_manager_marks_stale_source_sections() -> None:
    now = datetime.now(UTC)
    row = project(now)
    stale_worker = worker(now)
    stale_worker.last_heartbeat_at = now - timedelta(minutes=10)
    rows = [
        [row],
        [],
        [],
        [],
        [],
        [stale_worker],
        [],
        [],
    ]

    response = await dashboard_manager(QuerySession(rows), actor())  # type: ignore[arg-type]

    assert response["sections"]["workers"]["state"] == "stale"
    assert response["sections"]["workers"]["freshness"] == "stale"
    assert response["sections"]["workers"]["meaning"]["label"] == "Stale"
    assert response["sections"]["workers"]["stale_after_seconds"] == 300
    assert response["sections"]["workers"]["freshness_age_seconds"] >= 600


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
    assert job_node["status_label"] == "Recovery review needed"
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
    assert all("status_label" in node for node in response["graph"]["nodes"])
    assert all("status_meaning" in node for node in response["graph"]["nodes"])
    job_node = next(node for node in response["graph"]["nodes"] if node["kind"] == "job")
    assert job_node["status"] == "queued"
    assert job_node["status_label"] == "Waiting for worker capacity"
    assert "queued" not in job_node["human_summary"].lower()


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
