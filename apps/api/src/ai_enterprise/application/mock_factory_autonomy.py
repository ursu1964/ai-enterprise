from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.api.project_formation_schemas import (
    FormationRequest,
    MockFactoryLaunchIssueResponse,
    MockFactoryPreviewProjectResponse,
    MockFactoryPreviewResponse,
    MockFactoryProjectResponse,
    MockFactoryStartResponse,
)
from ai_enterprise.application.project_formation_service import ProjectFormationService
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.application.workflow.service import WorkflowService, workflow_state_for_project
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import ApprovalDecision, ArtifactType, ProjectStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    AuditEventModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.database.workflow_models import WorkflowInstanceModel


@dataclass(frozen=True, slots=True)
class MockFactorySpec:
    name: str
    description: str
    repository_path: str
    project_type: str
    expected_outcome: str
    target_users: list[str]
    constraints: list[str]
    known_systems: list[str]
    deadline: str
    budget_signal: str


MOCK_FACTORY_SPECS: tuple[MockFactorySpec, ...] = (
    MockFactorySpec(
        name="AI Enterprise Product Factory Demo",
        description=(
            "Create the central manager that turns a manifesto into parallel governed "
            "projects, execution graphs, telemetry, reusable blueprints, and client proof."
        ),
        repository_path="/home/user/projects/mock-enterprise/ai-enterprise-product-factory",
        project_type="dashboards_reporting",
        expected_outcome=(
            "A visible factory demo that shows manifesto intake becoming live project work."
        ),
        target_users=["client owner", "operator", "developer", "executive sponsor"],
        constraints=["local development first", "human approval before irreversible execution"],
        known_systems=["FastAPI dashboard", "PostgreSQL", "worker queues", "Graphify"],
        deadline="first governed demo today",
        budget_signal="reuse current dashboard, workflow, telemetry, and documentation assets",
    ),
    MockFactorySpec(
        name="ISO Certification Consulting Module Demo",
        description=(
            "Create a consulting module that converts an enterprise request into ISO-style "
            "gap analysis, evidence collection, corrective actions, and client reporting."
        ),
        repository_path="/home/user/projects/mock-enterprise/iso-certification-consulting-module",
        project_type="security_compliance",
        expected_outcome=(
            "A reusable compliance delivery blueprint with traceable evidence and gaps."
        ),
        target_users=["consultant", "auditor", "client compliance lead"],
        constraints=["audit evidence must be traceable", "recommendations must be explainable"],
        known_systems=["document hub", "audit timeline", "evidence graph"],
        deadline="demo-ready after first workflow pass",
        budget_signal="package repeatable certification discovery as a productized service",
    ),
    MockFactorySpec(
        name="Application Verification Debug Module Demo",
        description=(
            "Create a verification module that analyses an application, finds failures, "
            "proposes fixes, validates changes, and converts lessons into reusable "
            "quality patterns."
        ),
        repository_path=(
            "/home/user/projects/mock-enterprise/application-verification-debug-module"
        ),
        project_type="automated_testing",
        expected_outcome=(
            "A live quality workflow that turns errors into fixes, tests, and reusable guardrails."
        ),
        target_users=["developer", "QA lead", "technical operator"],
        constraints=[
            "changes need test proof",
            "errors must include human-readable recovery guidance",
        ],
        known_systems=["operator jobs", "execution events", "performance metrics"],
        deadline="continuous improvement after first demo",
        budget_signal="reduce repeated debugging time through reusable verification patterns",
    ),
    MockFactorySpec(
        name="Enterprise Blueprint Catalog Demo",
        description=(
            "Create a reusable blueprint catalog that captures successful workflows, crew "
            "specializations, project patterns, economic proof, and future project templates."
        ),
        repository_path="/home/user/projects/mock-enterprise/enterprise-blueprint-catalog",
        project_type="architecture_design",
        expected_outcome=(
            "A catalog that makes every successful delivery reusable for future clients."
        ),
        target_users=["platform owner", "solution architect", "business operator"],
        constraints=[
            "templates must preserve source evidence",
            "reuse decisions must stay explainable",
        ],
        known_systems=["documentation hub", "project intelligence", "ecosystem graph"],
        deadline="after mock portfolio execution creates first evidence",
        budget_signal="compound value by turning delivery knowledge into reusable assets",
    ),
)


class MockEnterpriseAutonomyService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def preview_mock_factory(self) -> MockFactoryPreviewResponse:
        projects: list[MockFactoryPreviewProjectResponse] = []
        reused_count = 0
        blocked_count = 0

        for spec in MOCK_FACTORY_SPECS:
            existing_project = await self._existing_project(spec)
            missing_information = self._validation_issues(spec)
            ready = not missing_information
            if existing_project is not None:
                reused_count += 1
            if not ready:
                blocked_count += 1
            projects.append(
                MockFactoryPreviewProjectResponse(
                    name=spec.name,
                    project_type=spec.project_type,
                    repository_path=spec.repository_path,
                    default_branch="main",
                    action="reuse" if existing_project is not None else "create",
                    ready=ready,
                    missing_information=missing_information,
                    operator_action=(
                        "Start mock factory to reuse this project and nudge its workflow."
                        if existing_project is not None and ready
                        else (
                            "Start mock factory to create the project, formation pack, "
                            "and workflow."
                        )
                        if ready
                        else "Fix the missing launch information before starting this project."
                    ),
                    existing_project_id=(
                        existing_project.id if existing_project is not None else None
                    ),
                    dashboard_url=(
                        f"/dashboard?project={existing_project.id}"
                        if existing_project is not None
                        else None
                    ),
                )
            )

        recommended = next((item for item in projects if item.ready), None)
        return MockFactoryPreviewResponse(
            status="ready" if blocked_count == 0 else "blocked",
            human_summary=(
                "Mock factory preview is ready: every portfolio project has the "
                "minimum launch information."
                if blocked_count == 0
                else "Mock factory preview found projects that need launch information."
            ),
            ready_count=len(projects) - blocked_count,
            reused_count=reused_count,
            blocked_count=blocked_count,
            recommended_first_project=recommended,
            projects=projects,
        )

    async def start_mock_factory(self, *, actor_id: str) -> MockFactoryStartResponse:
        results: list[MockFactoryProjectResponse] = []
        created: list[MockFactoryProjectResponse] = []
        reused: list[MockFactoryProjectResponse] = []
        blocked: list[MockFactoryLaunchIssueResponse] = []
        failed: list[MockFactoryLaunchIssueResponse] = []
        workflows_started: list[uuid.UUID] = []
        workflows_waiting: list[uuid.UUID] = []
        reused_count = 0
        formation_pack_count = 0
        workflow_count = 0

        for spec in MOCK_FACTORY_SPECS:
            validation_issues = self._validation_issues(spec)
            if validation_issues:
                blocked.append(self._launch_issue(spec, "blocked", validation_issues))
                continue
            try:
                project = await self._existing_project(spec)
                project_record = "created"
                if project is None:
                    project = await self._create_project(spec, actor_id=actor_id)
                else:
                    project_record = "reused"
                    reused_count += 1
                    await self._ensure_autonomy_policy(project)

                formation_pack = "already prepared"
                if not await self._has_formation_pack(project):
                    await self._create_formation_pack(project, spec, actor_id=actor_id)
                    formation_pack = "created"
                    formation_pack_count += 1

                existing_workflow = await self._workflow_for_project(project)
                if existing_workflow is not None:
                    await self._recover_demo_workflow(project, existing_workflow, actor_id=actor_id)
                workflow = await WorkflowService(self._session).start(
                    project_id=project.id,
                    actor_id=actor_id,
                )
                workflow_state = "started"
                if existing_workflow is None:
                    workflow_count += 1
                    workflows_started.append(workflow.id)
                else:
                    workflow_state = "reused and nudged"
                    workflows_waiting.append(workflow.id)
                    await WorkflowService(self._session).notify(project.id)
                await self._continue_autonomy(project, actor_id=actor_id)

                project_response = MockFactoryProjectResponse(
                    project_id=project.id,
                    workflow_id=workflow.id,
                    name=project.name,
                    project_type=spec.project_type,
                    repository_path=project.repository_path,
                    project_record=project_record,
                    formation_pack=formation_pack,
                    workflow=workflow_state,
                    next_action=(
                        "Open Execution and watch phase, task, crew, event, and telemetry movement."
                    ),
                    dashboard_url=f"/dashboard?project={project.id}",
                )
                results.append(project_response)
                if project_record == "created":
                    created.append(project_response)
                else:
                    reused.append(project_response)
            except Exception as exc:
                if hasattr(self._session, "rollback"):
                    await self._session.rollback()
                failed.append(self._launch_issue(spec, "failed", [str(exc)]))

        return MockFactoryStartResponse(
            status="started" if results and not failed and not blocked else "partial",
            human_summary=(
                "Mock autonomy started every ready portfolio project."
                if not failed and not blocked
                else "Mock autonomy started ready projects and reported blocked or failed work."
            ),
            started_count=len(results),
            reused_count=reused_count,
            formation_pack_count=formation_pack_count,
            workflow_count=workflow_count,
            created_count=len(created),
            blocked_count=len(blocked),
            failed_count=len(failed),
            workflows_started=workflows_started,
            workflows_waiting=workflows_waiting,
            created=created,
            reused=reused,
            blocked=blocked,
            failed=failed,
            recommended_first_project=results[0] if results else None,
            next_action=(
                "Open the recommended project dashboard and verify the graph begins to move."
                if results
                else "Fix blocked or failed launch items, then start the mock factory again."
            ),
            projects=results,
        )

    def _validation_issues(self, spec: MockFactorySpec) -> list[str]:
        issues: list[str] = []
        if len(spec.name.strip()) < 3:
            issues.append("project name is required")
        if not spec.repository_path.startswith("/"):
            issues.append("repository path must be absolute")
        if len(spec.description.strip()) < 20:
            issues.append("project manifesto summary is required")
        if not spec.project_type.strip():
            issues.append("project type is required")
        if len(spec.expected_outcome.strip()) < 20:
            issues.append("expected outcome is required")
        return issues

    def _launch_issue(
        self, spec: MockFactorySpec, status: str, issues: list[str]
    ) -> MockFactoryLaunchIssueResponse:
        return MockFactoryLaunchIssueResponse(
            name=spec.name,
            project_type=spec.project_type,
            repository_path=spec.repository_path,
            status=status,
            issues=issues,
            operator_action=(
                "Fix the launch information and run preview again."
                if status == "blocked"
                else "Review the failure, correct the underlying record or service, and retry."
            ),
        )

    async def _existing_project(self, spec: MockFactorySpec) -> ProjectModel | None:
        return await self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.name == spec.name,
                ProjectModel.repository_path == spec.repository_path,
            )
        )

    async def _create_project(self, spec: MockFactorySpec, *, actor_id: str) -> ProjectModel:
        manifest: dict[str, Any] = {
            "source": "mock_enterprise_autonomy",
            "project_type": spec.project_type,
            "factory_type": spec.project_type,
            "autonomous_execution": {
                "enabled": True,
                "authority": "manifest_ingestion",
                "mode": "controlled_demo",
                "auto_approve_requirements": True,
                "auto_approve_architecture": True,
                "auto_approve_work_package": True,
                "stop_before_integration": True,
            },
            "autonomy_scope": "controlled_demo",
            "operating_loop": [
                "manifesto",
                "project",
                "formation_pack",
                "workflow",
                "tasks_crews",
                "telemetry",
                "dashboard",
                "documentation",
                "blueprint",
            ],
        }
        return await ProjectWorkflowService(
            session=self._session,
            settings=self._settings,
        ).create_project(
            name=spec.name,
            description=spec.description,
            repository_path=spec.repository_path,
            repository_url=None,
            default_branch="main",
            actor_id=actor_id,
            manifest=manifest,
            project_type=spec.project_type,
        )

    async def _ensure_autonomy_policy(self, project: ProjectModel) -> None:
        manifest = dict(project.manifest or {})
        changed = False
        if not isinstance(manifest.get("autonomous_execution"), dict):
            manifest["autonomous_execution"] = {
                "enabled": True,
                "authority": "manifest_ingestion",
                "mode": "controlled_demo",
                "auto_approve_requirements": True,
                "auto_approve_architecture": True,
                "auto_approve_work_package": True,
                "stop_before_integration": True,
            }
            changed = True
        next_hash = hash_json(manifest)
        if not changed and project.manifest_hash == next_hash:
            return
        project.manifest = manifest
        project.manifest_hash = next_hash
        await self._session.commit()
        await self._session.refresh(project)

    async def _continue_autonomy(self, project: ProjectModel, *, actor_id: str) -> None:
        workflow = WorkflowService(self._session)
        project_workflow = ProjectWorkflowService(
            session=self._session,
            settings=self._settings,
        )
        if project.status == ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL:
            artifact = await self._latest_artifact(project, ArtifactType.REQUIREMENTS_SPECIFICATION)
            if artifact is not None:
                await project_workflow.approve_requirements(
                    project_id=project.id,
                    artifact_id=artifact.id,
                    decision=ApprovalDecision.APPROVED,
                    reviewer="manifest-autonomy-policy",
                    comment=f"Approved automatically after manifesto ingestion by {actor_id}.",
                )
                await workflow.notify(project.id)
                return
        if project.status == ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL:
            artifact = await self._latest_artifact(project, ArtifactType.ARCHITECTURE_SPECIFICATION)
            if artifact is not None:
                await project_workflow.approve_architecture(
                    project_id=project.id,
                    artifact_id=artifact.id,
                    decision=ApprovalDecision.APPROVED,
                    reviewer="manifest-autonomy-policy",
                    comment=f"Approved automatically after manifesto ingestion by {actor_id}.",
                )
                await workflow.notify(project.id)
                return
        if project.status == ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL:
            work_package = await self._latest_work_package(project)
            if work_package is not None:
                await project_workflow.approve_work_package(
                    project_id=project.id,
                    work_package_id=work_package.id,
                    decision=ApprovalDecision.APPROVED,
                    reviewer="manifest-autonomy-policy",
                    comment=f"Approved automatically after manifesto ingestion by {actor_id}.",
                )
                await workflow.notify(project.id)

    async def _latest_artifact(
        self, project: ProjectModel, artifact_type: ArtifactType
    ) -> ArtifactModel | None:
        return await self._session.scalar(
            select(ArtifactModel)
            .where(
                ArtifactModel.project_id == project.id,
                ArtifactModel.artifact_type == artifact_type.value,
            )
            .order_by(ArtifactModel.created_at.desc())
        )

    async def _latest_work_package(self, project: ProjectModel) -> WorkPackageModel | None:
        return await self._session.scalar(
            select(WorkPackageModel)
            .where(WorkPackageModel.project_id == project.id)
            .order_by(WorkPackageModel.created_at.desc())
        )

    async def _has_formation_pack(self, project: ProjectModel) -> bool:
        artifact = await self._session.scalar(
            select(ArtifactModel).where(
                ArtifactModel.project_id == project.id,
                ArtifactModel.artifact_type == ArtifactType.FORMATION_APPROVAL_PACK.value,
            )
        )
        return artifact is not None

    async def _create_formation_pack(
        self, project: ProjectModel, spec: MockFactorySpec, *, actor_id: str
    ) -> None:
        await ProjectFormationService(self._session).create_formation_pack(
            FormationRequest(
                project_id=project.id,
                idea=spec.description,
                expected_outcome=spec.expected_outcome,
                target_users=spec.target_users,
                constraints=spec.constraints,
                known_systems=spec.known_systems,
                deadline=spec.deadline,
                budget_signal=spec.budget_signal,
            ),
            actor_id=actor_id,
        )

    async def _workflow_for_project(self, project: ProjectModel) -> WorkflowInstanceModel | None:
        return await self._session.scalar(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.project_id == project.id)
        )

    async def _recover_demo_workflow(
        self,
        project: ProjectModel,
        workflow: WorkflowInstanceModel,
        *,
        actor_id: str,
    ) -> None:
        policy = project.manifest.get("autonomous_execution")
        if not isinstance(policy, dict) or policy.get("mode") != "controlled_demo":
            return
        if workflow.state not in {"failed", "manual_intervention"}:
            return
        state, step, action = workflow_state_for_project(project)
        workflow.state = state
        workflow.current_step = step
        workflow.failure_code = None
        workflow.failure_message = None
        workflow.recommended_operator_action = action
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project.id,
                event_type="workflow.autonomy_recovered",
                actor_type="system",
                actor_id=actor_id,
                payload={
                    "workflow_id": str(workflow.id),
                    "state": state,
                    "reason": "Recovered controlled demo workflow after obsolete transition bug.",
                },
            )
        )
        await self._session.commit()
        await self._session.refresh(workflow)
