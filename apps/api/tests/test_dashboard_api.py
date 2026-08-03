import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from ai_enterprise.api.dependencies import Actor, get_actor
from ai_enterprise.api.routes import dashboard as dashboard_routes
from ai_enterprise.api.routes.dashboard import (
    dashboard_context,
    dashboard_deployment_blueprint,
    dashboard_graph_demo_setup,
    dashboard_infrastructure_choices,
    dashboard_server_readiness,
    dashboard_telemetry_summary,
)
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
        self.added: list[Any] = []
        self.commit_count = 0

    async def scalar(self, statement: object) -> Any:
        return self.scalar_rows.pop(0) if self.scalar_rows else None

    async def scalars(self, statement: object) -> Scalars:
        return Scalars(self.scalars_rows.pop(0) if self.scalars_rows else [])

    async def get(self, model: type, identity: uuid.UUID) -> Any:
        return None

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def commit(self) -> None:
        self.commit_count += 1


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


def service_project_reader(scope: str) -> Actor:
    return Actor(
        "project-service",
        "service",
        "operator",
        frozenset({"project.read"}),
        scopes=frozenset({scope}),
    )


def test_dashboard_page_links_operator_surfaces() -> None:
    client = TestClient(app)

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "AI Enterprise Command Center" in response.text
    assert "Documentation Hub" in response.text
    assert "/dashboard/documentation-hub" in response.text
    assert "Data source freshness" in response.text
    assert "managerSectionSource" in response.text
    assert "dashboardManagerSources" in response.text
    assert "source-meaning" in response.text
    assert "source-next" in response.text
    assert "source-proof" in response.text
    assert "data is available for operator decisions" in response.text
    assert "Proof:" in response.text
    assert "connection needs attention" in response.text
    assert "waiting for signal" in response.text
    assert "refresh recommended" in response.text
    assert "verify API readiness before making delivery decisions" in response.text
    assert "Waiting for the first source timestamp" in response.text
    assert "check API logs" not in response.text
    assert "data source(s) need attention" not in response.text
    assert 'countSentence(staleSources, "data source")' in response.text
    assert "freshness_age_seconds" in response.text
    assert "stale_after_seconds" in response.text
    assert "refresh window" in response.text
    assert "stale after" not in response.text
    assert "Data is incomplete" not in response.text
    assert "Source refresh needed" in response.text
    assert "Service Pulse" in response.text
    assert "HTTP Flow" not in response.text
    assert "Business decision board" in response.text
    assert "state.dashboardManager?.business_board" in response.text
    assert "Guided Route" in response.text
    assert 'data-view="execution"' in response.text
    assert "Project Execution Control" in response.text
    assert "Parallel Projects" in response.text
    assert "Tasks and Crews" in response.text
    assert "Events and Telemetry" in response.text
    assert "Waiting for the first event timestamp." in response.text
    assert "No timestamp yet" not in response.text
    assert "executionGraph" in response.text
    assert "renderExecutionDashboard" in response.text
    assert "/api/v1/query/dashboard-manager" in response.text
    assert "Watch the Execution graph" in response.text
    assert "Start with a client idea or manifesto" in response.text
    assert "window.location.hash" in response.text
    assert "hashchange" in response.text
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
    assert "Project summary is waiting for the client objective." in response.text
    assert "Project base directory is required before launch." in response.text
    assert "GitHub connection can be added now or after local project creation." in response.text
    assert "No description" not in response.text
    assert "No repository path" not in response.text
    assert "No GitHub repository URL yet" not in response.text
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
    assert "Preview Launch" in response.text
    assert "Create Foundry Workspace" in response.text
    assert "createFoundryWorkspaceFromDashboard" in response.text
    assert "/foundry-workspace" in response.text
    assert "Project Foundry created the repository blueprint" in response.text
    assert "PROJECT.yaml, AGENTS.md, governance, intake, requirements" in response.text
    assert "No records were created. This project is ready for supervised launch." in response.text
    assert (
        "Client-side preflight only. No database record, workflow, job, or artifact was created."
        in response.text
    )
    assert "Preview Mock Factory" in response.text
    assert "would create" in response.text
    assert "would reuse" in response.text
    assert "launchContractFromFactoryResult" in response.text
    assert "launch_plan" in response.text
    assert "launch_result" in response.text
    assert "review_needed_count" in response.text
    assert "workflows_started_count" in response.text
    assert "workflows_waiting_count" in response.text
    assert "Workflows Started" in response.text
    assert "Workflows Waiting" in response.text
    assert "recommended_first_project_id" in response.text
    assert "recommended_first_project_url" in response.text
    assert "result_category" in response.text
    assert "Preview contract, launch plan summary" in response.text
    assert "Launch result summary" in response.text

    assert "Launch Mock Factory Test" in response.text
    assert "Mock Autonomy" in response.text
    assert "Launch Result" in response.text
    assert "Launch is waiting for preview or start." in response.text
    assert "Project Readiness" in response.text
    assert "No project readiness items yet" in response.text
    assert "Live evidence is waiting for the first governed record" in response.text
    assert "Evidence is waiting for the first governed record" in response.text
    assert "Status: ${esc(emptyMessage)}" in response.text
    assert "Next: follow the panel guidance, then refresh this dashboard." in response.text
    assert (
        "Result: when the factory creates governed data, it appears here automatically."
        in response.text
    )
    assert "launch-contract-list" in response.text
    assert "Open Recommended View" in response.text
    assert "Open Proof Path" in response.text
    assert "No launch has started yet" not in response.text
    assert "No live records are available" not in response.text
    assert "No evidence has been recorded" not in response.text
    assert (
        "No project readiness items yet. Press Preview Launch or start the factory "
        "to populate this list."
        in response.text
    )
    assert "Start Manifesto Batch when you want to create this project." in response.text
    assert "Will reuse existing work" in response.text
    assert "Partially started" in response.text
    assert "Started" in response.text
    assert "Blocked" in response.text
    assert "Partly started, needs review" not in response.text
    assert "Started and ready to inspect" not in response.text
    assert "Blocked until missing details are fixed" not in response.text
    assert "/api/v1/project-formation/mock-factory/preview" in response.text
    assert "/api/v1/project-formation/mock-factory/start" in response.text
    assert "created, reused, blocked, and review-needed work" in response.text
    assert "Problem Resolution Graph" in response.text
    assert "Blocked work links to worker state" in response.text
    assert "Needs review" in response.text
    assert "Dead Letter" not in response.text
    assert "Review blocked work first." in response.text
    assert "#problemGraph.surface-graph" in response.text
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto" in response.text
    assert "overflow-wrap: anywhere" in response.text
    assert "Telemetry Pulse Graph" in response.text
    assert "Guided Recovery Center" in response.text
    assert "Recovery and Work History" not in response.text
    assert "Worker Capacity" in response.text
    assert "Current capacity" in response.text
    assert "Offline history" in response.text
    assert "Ready to accept enterprise work." in response.text
    assert "Historical worker instance. It is not part of current capacity." in response.text
    assert "Work that needs a decision" in response.text
    assert "Reviewed proof history" in response.text
    assert "Needs action" in response.text
    assert "Being retried" in response.text
    assert "Healthy history" in response.text
    assert "Open Attempts" in response.text
    assert "Record Reviewed Recovery" in response.text
    assert "Acknowledge Reviewed Failure" not in response.text
    assert "Attempt Proof" in response.text
    assert "Recovery signal:" in response.text
    assert "waiting for worker" in response.text
    assert "Waiting for recovery signal" in response.text
    assert "waiting for proof" in response.text
    assert "Waiting for heartbeat" in response.text
    assert "Telemetry summary is waiting for the first governed signal." in response.text
    assert "Server readiness is waiting for verifier output." in response.text
    assert "Infrastructure choices are waiting for saved decisions." in response.text
    assert "not assigned" not in response.text
    assert "not reported" not in response.text
    assert "Not reported" not in response.text
    assert "not available yet" not in response.text
    assert "Attempt proof needs attention" in response.text
    assert "Review could not be recorded" in response.text
    assert "recommended fix" in response.text
    assert "current delivery risk" in response.text
    assert "jobRecoveryDecision" in response.text
    assert "Operator decision required" in response.text
    assert "Current delivery risk until recovery is reviewed" in response.text
    assert "Open attempt proof, identify the recovery path" in response.text
    assert "Reviewed recovery" in response.text
    assert "Healthy history. This completed record supports delivery proof." in response.text
    assert "Failed work changes the operating picture" not in response.text
    assert "Review failed or blocked work" not in response.text
    assert "quality or blocked work is slowing progress" in response.text
    assert "Prevents repeated problems later." in response.text
    assert "recurring-problem guardrail candidate" in response.text
    assert "Recurring problems should become recovery checklists" in response.text
    assert "Recurring problem classes should become a recovery checklist" in response.text
    assert "current problem(s) share this class" not in response.text
    assert 'countSentence(count, "current problem")' in response.text
    assert "Reduces repeat problems across future projects." in response.text
    assert "Reduces repeat problems before more work is queued." in response.text
    assert "known problem classes" in response.text
    assert "quality or failures are blocking progress" not in response.text
    assert "repeated-failure guardrail candidate" not in response.text
    assert "current failure(s) share this class" not in response.text
    assert "Repeated failure classes should become" not in response.text
    assert "Reduces repeat failures" not in response.text
    assert "jobActionStatus" in response.text
    assert "/api/v1/operator/jobs/by-id/" in response.text
    assert "loadJobAttempts" in response.text
    assert "acknowledgeProblemJob" in response.text
    assert "groupedJobs" in response.text
    assert "jobRecoveryGroup" in response.text
    assert "failureImprovementProposals" in response.text
    assert "dashboardRecoveryProposals" in response.text
    assert "recovery?.improvement_proposals" in response.text
    assert "evidence_status" in response.text
    assert "ready_to_submit" in response.text
    assert "Missing:" in response.text
    assert "immutable evidence reference" in response.text
    assert "improvement_draft?.evidence_required" in response.text
    assert "Draft target:" in response.text
    assert "Evidence required from job attempts." in response.text
    assert "Source jobs:" in response.text
    assert "Guardrail proposal:" in response.text
    assert "Recurring problems should become recovery checklists" in response.text
    assert "Business Telemetry" in response.text
    assert "Server Readiness" in response.text
    assert "/dashboard/server-readiness" in response.text
    assert "Real Infrastructure Choices" in response.text
    assert "/dashboard/infrastructure-choices" in response.text
    assert "infrastructureChoicesTable" in response.text
    assert "Advanced metric names" in response.text
    assert "System pulse counter or gauge used for operator proof." in response.text
    assert "system pulse signal(s)" not in response.text
    assert (
        'countSentence(Object.keys(state.metrics).length, "system pulse signal")'
        in response.text
    )
    assert "Advanced raw metrics" not in response.text
    assert "raw signal(s)" not in response.text
    assert "Blueprint Graph Hub" in response.text
    assert "Blueprint Learning Queue" in response.text
    assert "Guardrail Learning Queue" in response.text
    assert "dashboardManager?.reuse" in response.text
    assert "blueprint_candidates" in response.text
    assert "guardrail_candidates" in response.text
    assert "reuseReadiness" in response.text
    assert "next_catalog_review" in response.text
    assert "nextCatalogReview" in response.text
    assert "evidence_bundle" in response.text
    assert "nextReviewEvidenceCount" in response.text
    assert "nextReviewCriteriaPassed" in response.text
    assert "criteria_status" in response.text
    assert "catalog_review_ready" in response.text
    assert "needs_more_proof" in response.text
    assert "guardrails_evidence_required" in response.text
    assert "Review-ready:" in response.text
    assert "Next review:" in response.text
    assert "proof item(s)" not in response.text
    assert 'countSentence(nextReviewEvidenceCount, "proof item")' in response.text
    assert "passed criterion/criteria" in response.text
    assert "needs proof:" in response.text
    assert "Evidence required:" in response.text
    assert "No reusable learning candidates have been observed yet." in response.text
    assert "lifecycle_detail" in response.text
    assert "promotion_blockers" in response.text
    assert "Promotion blockers:" in response.text
    assert "trust_level" in response.text
    assert "Collect governed evidence before reuse." in response.text
    assert "proposal_type" in response.text
    assert "evidence_sources" in response.text
    assert "evidence required" in response.text
    assert "Review before reuse." in response.text
    assert "Project Foundry Core" in response.text
    assert "/dashboard/project-foundry-core" in response.text
    assert "Authenticated Graph Context" in response.text
    assert "The dashboard will use the current organization and project" in response.text
    assert "authenticatedGraphPreview" in response.text
    assert "Create Demo Graph Proof" in response.text
    assert "/dashboard/graph-demo/setup" in response.text
    assert "Demo graph proof is ready" in response.text
    assert "Ready to check" in response.text
    assert "payload.nodes || payload.entities || []" in response.text
    assert "map is ready but empty" in response.text
    assert "The graph is not broken; it is waiting for governed execution records." in response.text
    assert "Last check found" in response.text
    assert "/api/v1/ecosystem/graph" in response.text
    assert "/api/v1/specifications/evidence/graph" in response.text
    assert "operator headers" not in response.text
    assert "/api/v1/query/operating-picture" in response.text
    assert "/api/v1/project-formation/projects/" in response.text
    assert "Operating Picture" in response.text
    assert "unresolvedProblemJobs" in response.text
    assert "acknowledged by operator" in response.text
    assert "Needs workflow link" in response.text
    assert "Proof detail" in response.text
    assert "Diagnostic detail" not in response.text
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
    assert "The factory needs operator review before retry." in response.text
    assert "open Problems for the recovery path before retrying" in response.text
    assert "review-needed launches" in response.text
    assert "need review. Opening execution control" in response.text
    assert "needs review:" in response.text
    assert "Launch needs operator review." in response.text
    assert "Open Problems and retry after correction." in response.text
    assert "Recovery review needed" in response.text
    assert "Reviewed recovery needed" not in response.text
    assert "inspect API logs" not in response.text
    assert "launch failure" not in response.text
    assert "failed launches" not in response.text
    assert "Launch failed." not in response.text
    assert "Reviewed failure or recovery needed" not in response.text
    assert "Technical detail" not in response.text
    assert "Worker proof has not been attached to this record yet." in response.text
    assert "No worker diagnostic was reported" not in response.text
    assert "reviewed history" in response.text
    assert "No current work needs action" in response.text
    assert "No current worker capacity is visible" in response.text
    assert "No projects are visible yet" in response.text
    assert "Recovery Items" in response.text
    assert "No active recovery items are attached to this project" in response.text
    assert "No active errors are attached to this project" not in response.text
    assert "Worker proof has not been attached to this error yet" not in response.text
    assert "No records." not in response.text
    assert "Plan approved, execution not started" in response.text
    assert "Confidence:" in response.text
    assert "Owner:" in response.text
    assert "Phase confidence" in response.text
    assert "Owner crew" in response.text
    assert "Issue split" in response.text
    assert "Proof status" in response.text
    assert "Issue state" in response.text
    assert "Evidence:" in response.text
    assert "Remaining:" in response.text
    assert "Live workflow" in response.text
    assert "Evidence backed" in response.text
    assert "Needs review" in response.text
    assert "Completed Evidence" in response.text
    assert "Remaining Work" in response.text
    assert "Workflow is waiting for the first governed step." in response.text
    assert "Waiting for phase proof" in response.text
    assert (
        "Evidence will appear after the workflow records a phase transition or artifact."
        in response.text
    )
    assert "No phase movement recorded yet." in response.text
    assert "Waiting for execution proof" in response.text
    assert "Executed steps will appear after workflow movement is recorded." in response.text
    assert "No proof yet" not in response.text
    assert "No transition recorded" not in response.text
    assert "No active step" not in response.text
    assert "Current Issues" in response.text
    assert "Used to show active blockers for the selected phase" in response.text
    assert "This phase has no active blockers" in response.text
    assert "Used to preserve old problems after they are resolved or acknowledged" in response.text
    assert "Past problems will appear here after review" in response.text
    assert "Nothing to show yet" not in response.text
    assert "Waiting for live evidence" in response.text
    assert "Waiting for table evidence" in response.text
    assert "when the factory creates governed data, it appears here automatically" in response.text
    assert "Historical samples" in response.text
    assert "Average phase" in response.text
    assert "lifecycle" in response.text
    assert "Source phase:" in response.text
    assert "Improvement proposals" in response.text
    assert "/api/v1/operator/jobs" in response.text
    assert "/metrics" in response.text
    assert "/dashboard/graphify" in response.text
    assert "/dashboard/demo" in response.text


@pytest.mark.asyncio
async def test_local_dashboard_context_actor_can_read_query_model() -> None:
    actor = await get_actor(
        session=DashboardSession(scalar_rows=[None], scalars_rows=[]),  # type: ignore[arg-type]
        actor_id="local-dashboard-admin",
        actor_type="human",
        actor_role="platform-admin",
    )

    assert actor.capabilities == frozenset(
        {
            "ecosystem.read",
            "operator.jobs.manage",
            "query.read",
            "specification.read",
        }
    )
    assert actor.scopes == frozenset({"global"})


@pytest.mark.asyncio
async def test_dashboard_server_readiness_reports_human_actions() -> None:
    payload = await dashboard_server_readiness()

    assert payload["status"] in {"ready", "needs_setup"}
    assert payload["commands"][0] == "make server-readiness-template"
    assert any(item["name"] == "Trusted proxy" for item in payload["checks"])
    assert any(item["name"] == "Backup verification" for item in payload["checks"])
    assert any(item["name"] == "Migration gate" for item in payload["checks"])
    assert any(item["name"] == "Server secret generator" for item in payload["checks"])
    assert any(item["name"] == "Proxy signature helper" for item in payload["checks"])
    assert any(item["name"] == "Model endpoint verifier" for item in payload["checks"])
    assert any(item["name"] == "GitHub access hooks" for item in payload["checks"])
    assert any(item["name"] == "Scheduled backup templates" for item in payload["checks"])
    assert any(item["name"] == "Managed storage hooks" for item in payload["checks"])
    assert any(item["name"] == "Kubernetes rollout templates" for item in payload["checks"])
    assert any(item["name"] == "Prometheus and Grafana" for item in payload["checks"])
    assert any(item["name"] == "Production alert rules" for item in payload["checks"])
    assert any(item["name"] == "Reverse proxy and TLS" for item in payload["checks"])
    assert any(item["name"] == "Deployment blueprint" for item in payload["checks"])
    assert any(item["name"] == "Infrastructure choices gate" for item in payload["checks"])
    assert "make server-secrets" in payload["commands"]
    assert "make deployment-blueprint" in payload["commands"]
    assert "make infrastructure-choices-template" in payload["commands"]
    assert "make infrastructure-choices-verify" in payload["commands"]
    assert any("make model-verify" in command for command in payload["commands"])
    assert all("action" in item for item in payload["checks"])


@pytest.mark.asyncio
async def test_dashboard_deployment_blueprint_reports_reusable_phases() -> None:
    payload = await dashboard_deployment_blueprint()

    assert payload["status"] in {"ready", "needs_setup"}
    assert payload["name"] == "AI Enterprise Deployment Blueprint"
    assert [phase["phase"] for phase in payload["phases"]] == [1, 2, 3, 4, 5, 6]
    assert "next_action" in payload


@pytest.mark.asyncio
async def test_dashboard_infrastructure_choices_reports_decision_gate() -> None:
    payload = await dashboard_infrastructure_choices()

    assert payload["status"] == "needs_setup"
    assert payload["conformant"] is False
    assert "domain_tls" in payload["sections"]
    assert "next_action" in payload


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
    assert "Document Preview" in response.text
    assert "docPreview" in response.text
    assert "Select a document from Operator Documents to preview it here." in response.text
    assert "No document selected." not in response.text
    assert "doc-open" in response.text
    assert "Open Plain Text" in response.text
    assert "Open Raw Text" not in response.text
    assert "/dashboard/documentation/operator-startup-guide?download=true" in response.text
    assert (
        "/dashboard/documentation/real-world-infrastructure-choices?download=true"
        in response.text
    )
    assert "Graphs and Images" in response.text
    assert "Commands" in response.text
    assert "docs/enterprise/working-method.md" in response.text
    assert "/dashboard/graphify" in response.text
    assert "Document preview needs attention" in response.text
    assert "confirm the document is registered in the Documentation Hub" in response.text
    assert "preview needs attention" in response.text
    assert "is unavailable" not in response.text


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


def test_documentation_endpoint_previews_and_downloads_registered_documents() -> None:
    client = TestClient(app)

    preview = client.get("/dashboard/documentation/working-method")
    download = client.get("/dashboard/documentation/operator-startup-guide?download=true")

    assert preview.status_code == 200
    assert "Working Method" in preview.text
    assert "attachment" not in preview.headers.get("content-disposition", "")
    assert download.status_code == 200
    assert download.headers["content-disposition"] == (
        'attachment; filename="operator-startup-guide.md"'
    )
    assert "Operator Startup Guide" in download.text


def test_documentation_endpoint_rejects_unregistered_documents() -> None:
    client = TestClient(app)

    traversal = client.get("/dashboard/documentation/../../.env")
    response = client.get("/dashboard/documentation/not-registered-doc")

    assert traversal.status_code == 404
    assert response.status_code == 404
    assert response.json()["detail"] == "Operator document is not registered"


def test_documentation_endpoint_explains_missing_registered_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    client = TestClient(app)
    monkeypatch.setitem(
        dashboard_routes.OPERATOR_DOCUMENT_FILES,
        "missing-document",
        {"path": tmp_path / "missing.md", "filename": "missing.md"},
    )

    response = client.get("/dashboard/documentation/missing-document")

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "Operator document file needs setup in the Documentation Hub"
    )


def test_graphify_dashboard_explains_missing_generated_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    client = TestClient(app)
    monkeypatch.setattr(dashboard_routes, "GRAPHIFY_HTML", tmp_path / "missing.html")

    response = client.get("/dashboard/graphify")

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Code graph needs generation. Run graphify update ., then reopen this page."
    )


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
    assert "Step-by-Step Live Demo" in response.text
    assert "Demo Operator Console" in response.text
    assert "API health" in response.text
    assert "Visible projects" in response.text
    assert "Telemetry" in response.text
    assert "Refresh Live Proof" in response.text
    assert "Live proof checked" in response.text
    assert "proofHealthCard" in response.text
    assert 'id="proofHealthCard" class="proof-card" href="/dashboard"' in response.text
    assert 'id="proofProjectsCard" class="proof-card" href="/dashboard#projects"' in response.text
    assert 'id="proofTelemetryCard" class="proof-card" href="/dashboard#metrics"' in response.text
    assert 'id="proofNextCard" class="proof-card" href="/dashboard#factory"' in response.text
    assert "loadLiveProof" in response.text
    assert "card.href = href" in response.text
    assert "If the proof still needs attention" in response.text
    assert "Project proof is waiting for source confirmation" in response.text
    assert "Runtime telemetry is visible" in response.text
    assert "Runtime telemetry is waiting for the first signal" in response.text
    assert "Metric proof is waiting for source confirmation" in response.text
    assert "not reachable yet" not in response.text
    assert "stays unavailable" not in response.text
    assert "remains unavailable" not in response.text
    assert "Click to open Projects" in response.text
    assert "Click to watch live project movement." in response.text
    assert "/health/ready" in response.text
    assert "/api/v1/projects" in response.text
    assert (
        "This console explains the next action before you open another dashboard."
        in response.text
    )
    assert "Launch Result shows readiness, missing data, and Project Readiness." in response.text
    assert (
        "Phase confidence, owner crew, completed work, and remaining work are visible."
        in response.text
    )
    assert "/dashboard#factory" in response.text
    assert "/dashboard#execution" in response.text
    assert "/dashboard#projects" in response.text
    assert "/dashboard#metrics" in response.text
    assert "Open Docs" in response.text


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
async def test_list_projects_requires_human_actor() -> None:
    with pytest.raises(HTTPException) as exc:
        await list_projects(
            Session([]),  # type: ignore[arg-type]
            service_project_reader("global"),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Human project authority is required"


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
    assert response["phases"][2]["confidence_detail"] == {
        "state": "live workflow",
        "score": 75,
        "label": "Live workflow",
        "severity": "ok",
        "meaning": "A governed workflow is linked and actively explains this phase.",
        "operator_action": (
            "Use workflow events and phase proof when deciding the next action."
        ),
        "evidence_count": 1,
        "current_blocker_count": 0,
    }
    assert response["phases"][2]["proof_status"]["state"] == "evidence_backed"
    assert response["phases"][2]["proof_status"]["evidence_count"] == 1
    assert response["phases"][2]["owner_crew"] == "architecture"
    assert response["phases"][2]["next_action"] == "Approve architecture."
    assert response["phases"][2]["completed_evidence"] == ["1 workflow transition"]
    assert "workflow transition(s)" not in str(response)
    assert response["phases"][2]["remaining_work"] == (
        "Finish the current gate and record the next transition."
    )
    assert response["phases"][2]["issue_summary"] == {
        "current_count": 0,
        "historical_count": 0,
        "state": "clear",
        "operator_action": "No active blockers are attached to this phase.",
    }
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
    assert response["blueprints"][0]["lifecycle_detail"]["label"] == (
        "Reviewed candidate"
    )
    assert response["blueprints"][0]["lifecycle_detail"]["trust_level"] == "reviewed"
    assert "needs proof before reuse" in response["blueprints"][0]["lifecycle_detail"][
        "meaning"
    ]
    assert "Collect the remaining proof" in response["blueprints"][0][
        "lifecycle_detail"
    ]["next_action"]
    assert "complete all delivery phases" in response["blueprints"][0][
        "lifecycle_detail"
    ]["promotion_blockers"]
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
async def test_project_intelligence_requires_human_actor() -> None:
    project_id = uuid.uuid4()
    project = ProjectModel(
        id=project_id,
        name="Service Blocked Intelligence Project",
        description="A project protected from service actor project intelligence reads.",
        repository_path="/home/user/projects/service-blocked-intelligence-project",
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
            service_project_reader(f"project:{project_id}"),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Human project authority is required"


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
    assert response["blueprints"][0]["lifecycle_detail"]["label"] == (
        "Improvement needed"
    )
    assert response["blueprints"][0]["lifecycle_detail"]["trust_level"] == (
        "guardrail_required"
    )
    assert "guardrails before this pattern is reused" in response["blueprints"][0][
        "lifecycle_detail"
    ]["meaning"]
    assert "resolve current issues before reuse" in response["blueprints"][0][
        "lifecycle_detail"
    ]["promotion_blockers"]
    proposal = response["blueprints"][0]["improvement_proposals"][0]
    assert proposal["proposal_key"] == "blueprint.intake.git.guardrail"
    assert proposal["proposal_type"] == "guardrail_or_template_update"
    assert proposal["status"] == "proposed"
    assert proposal["evidence_required"] is True
    assert proposal["evidence_sources"][0]["type"] == "project_job_failure"
    assert proposal["evidence_sources"][0]["job_type"] == "execute_work_package"
    assert "update the reusable blueprint" in proposal["operator_action"]
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
async def test_dashboard_graph_demo_setup_creates_local_graph_records() -> None:
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
        name="Graph Demo Project",
        description="A project used to seed graph proof.",
        repository_path="/home/user/projects/graph-demo",
        repository_url=None,
        default_branch="main",
        status=ProjectStatus.CREATED,
        manifest_hash="0" * 64,
        manifest={},
        created_at=now,
        updated_at=now,
    )
    session = DashboardSession(
        [organization, project, None, None, None, None, None, None],
        [[], []],
    )

    response = await dashboard_graph_demo_setup(session)  # type: ignore[arg-type]

    assert response["status"] == "ready"
    assert response["organization_id"] == str(organization.id)
    assert response["project_id"] == str(project.id)
    assert response["ecosystem"]["entities"] == 2
    assert response["ecosystem"]["edges"] == 1
    assert response["evidence"]["nodes"] == 2
    assert response["evidence"]["edges"] == 1
    assert response["next_action"] == (
        "Open Graph, then check Ecosystem and Evidence again."
    )
    assert len(session.added) >= 6
    assert session.commit_count >= 6


@pytest.mark.asyncio
async def test_dashboard_graph_demo_setup_is_disabled_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        with pytest.raises(HTTPException) as exc:
            await dashboard_graph_demo_setup(DashboardSession([], []))  # type: ignore[arg-type]
    finally:
        get_settings.cache_clear()

    assert getattr(exc.value, "status_code", None) == 403
    assert "disabled outside development" in str(getattr(exc.value, "detail", ""))


@pytest.mark.asyncio
async def test_dashboard_graph_demo_setup_requires_existing_project() -> None:
    with pytest.raises(HTTPException) as exc:
        await dashboard_graph_demo_setup(DashboardSession([None, None], []))  # type: ignore[arg-type]

    assert getattr(exc.value, "status_code", None) == 409
    assert "Create or load a project" in str(getattr(exc.value, "detail", ""))


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
