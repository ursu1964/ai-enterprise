import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.execution_workflow import ExecutionApplicationService
from ai_enterprise.application.project_workflow import ProjectWorkflowService
from ai_enterprise.application.review.service import ReviewCandidatePatchService
from ai_enterprise.application.workflow.completeness import verify_completeness
from ai_enterprise.application.workflow.repository import WorkflowNotFoundError, WorkflowRepository
from ai_enterprise.config import Settings
from ai_enterprise.domain.enums import ProjectStatus, WorkPackageStatus
from ai_enterprise.domain.execution.enums import ExecutionStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.review.enums import PatchReviewStatus
from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.enums import TERMINAL_STATES, WorkflowState, WorkflowStepName
from ai_enterprise.infrastructure.database.models import (
    ApprovalModel,
    ArtifactModel,
    ExecutionRunModel,
    IntegrationAttemptModel,
    IntegrationCommitModel,
    PatchReviewRunModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowContextModel,
    WorkflowInstanceModel,
    WorkflowStepAttemptModel,
    WorkflowTransitionModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository


class WorkflowConflictError(RuntimeError):
    pass


def workflow_state_for_project(project: ProjectModel) -> tuple[WorkflowState, str | None, str]:
    if hash_json(project.manifest) != project.manifest_hash:
        return (
            WorkflowState.MANUAL_INTERVENTION,
            None,
            (
                "Project manifest hash does not match stored content. "
                "Review legacy data before running."
            ),
        )
    status = str(project.status)
    if status == ProjectStatus.CREATED:
        return (
            WorkflowState.PROJECT_CREATED,
            None,
            "Start the workflow when the operator is ready to generate requirements.",
        )
    if status in {ProjectStatus.REQUIREMENTS_QUEUED, ProjectStatus.REQUIREMENTS_RUNNING}:
        return (
            WorkflowState.REQUIREMENTS_RUNNING,
            WorkflowStepName.REQUIREMENTS,
            "Wait for requirements generation or inspect the requirements job.",
        )
    if status == ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL:
        return (
            WorkflowState.WAITING_REQUIREMENTS_APPROVAL,
            WorkflowStepName.REQUIREMENTS,
            "Review requirements evidence and approve or request changes.",
        )
    if status == ProjectStatus.REQUIREMENTS_APPROVED:
        return (
            WorkflowState.REQUIREMENTS_RUNNING,
            WorkflowStepName.REQUIREMENTS,
            "Requirements are approved. Advance the workflow to architecture.",
        )
    if status == ProjectStatus.REQUIREMENTS_REJECTED:
        return (
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.REQUIREMENTS,
            "Requirements were rejected. Revise evidence before advancing.",
        )
    if status == ProjectStatus.REQUIREMENTS_FAILED:
        return (
            WorkflowState.FAILED,
            WorkflowStepName.REQUIREMENTS,
            "Requirements work failed. Review job evidence before retrying.",
        )
    if status in {
        ProjectStatus.ARCHITECTURE_QUEUED,
        ProjectStatus.ARCHITECTURE_RUNNING,
    }:
        return (
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowStepName.ARCHITECTURE,
            "Wait for architecture generation or inspect the architecture job.",
        )
    if status == ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL:
        return (
            WorkflowState.WAITING_ARCHITECTURE_APPROVAL,
            WorkflowStepName.ARCHITECTURE,
            "Review architecture evidence and approve or request changes.",
        )
    if status == ProjectStatus.ARCHITECTURE_APPROVED:
        return (
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowStepName.ARCHITECTURE,
            "Architecture is approved. Advance the workflow to work-package planning.",
        )
    if status == ProjectStatus.ARCHITECTURE_REJECTED:
        return (
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.ARCHITECTURE,
            "Architecture was rejected. Revise evidence before advancing.",
        )
    if status == ProjectStatus.ARCHITECTURE_FAILED:
        return (
            WorkflowState.FAILED,
            WorkflowStepName.ARCHITECTURE,
            "Architecture work failed. Review job evidence before retrying.",
        )
    if status in {
        ProjectStatus.WORK_PACKAGE_QUEUED,
        ProjectStatus.WORK_PACKAGE_PLANNING,
    }:
        return (
            WorkflowState.PLANNING_RUNNING,
            WorkflowStepName.PLANNING,
            "Wait for work-package planning or inspect planning jobs.",
        )
    if status == ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL:
        return (
            WorkflowState.WAITING_WORK_PACKAGE_APPROVAL,
            WorkflowStepName.PLANNING,
            "Review work-package evidence and approve or request changes.",
        )
    if status == ProjectStatus.WORK_PACKAGE_APPROVED:
        return (
            WorkflowState.PLANNING_RUNNING,
            WorkflowStepName.PLANNING,
            "Work package is approved. Advance the workflow to execution.",
        )
    if status == ProjectStatus.WORK_PACKAGE_REJECTED:
        return (
            WorkflowState.MANUAL_INTERVENTION,
            WorkflowStepName.PLANNING,
            "Work package was rejected. Revise evidence before execution.",
        )
    if status == ProjectStatus.WORK_PACKAGE_FAILED:
        return (
            WorkflowState.FAILED,
            WorkflowStepName.PLANNING,
            "Work-package planning failed. Review job evidence before retrying.",
        )
    return (
        WorkflowState.MANUAL_INTERVENTION,
        None,
        "Project status is not mapped to an automatic workflow step. Review before running.",
    )


class WorkflowService:
    VERSION = "1.0"

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings
        self.repository = WorkflowRepository(session)

    async def start(self, *, project_id: uuid.UUID, actor_id: str) -> WorkflowInstanceModel:
        existing = await self.session.scalar(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.project_id == project_id)
        )
        if existing is not None:
            return existing
        if await self.session.get(ProjectModel, project_id) is None:
            raise WorkflowNotFoundError(f"Project {project_id} does not exist")
        workflow_id, correlation_id = uuid.uuid4(), uuid.uuid4()
        workflow = WorkflowInstanceModel(
            id=workflow_id,
            project_id=project_id,
            definition_name="vertical_slice",
            workflow_version=self.VERSION,
            state=WorkflowState.PROJECT_CREATED,
            current_step=None,
            context_version=1,
            correlation_id=correlation_id,
            optimistic_version=1,
        )
        context = WorkflowContext(
            workflow_id=workflow_id,
            project_id=project_id,
            current_state=WorkflowState.PROJECT_CREATED,
            correlation_id=correlation_id,
            actor_id=actor_id,
        )
        self.session.add(workflow)
        await self.session.flush()
        self.session.add(
            WorkflowContextModel(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                version=1,
                state=WorkflowState.PROJECT_CREATED,
                context=context.model_dump(mode="json"),
                context_hash=context.content_hash(),
            )
        )
        await AuditWriter(self.session).append_project_event(
            project_id=project_id,
            event_type="workflow.started",
            actor_type="human",
            actor_id=actor_id,
            payload={"workflow_id": str(workflow_id), "correlation_id": str(correlation_id)},
        )
        await JobRepository(self.session).enqueue(
            project_id=project_id,
            run_id=None,
            job_type="advance_workflow",
            payload={"workflow_id": str(workflow_id), "correlation_id": str(correlation_id)},
            max_attempts=3,
        )
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def relink_project(
        self, *, project_id: uuid.UUID, actor_id: str, reason: str
    ) -> WorkflowInstanceModel:
        existing = await self.session.scalar(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.project_id == project_id)
        )
        if existing is not None:
            return existing
        project = await self.session.get(ProjectModel, project_id)
        if project is None:
            raise WorkflowNotFoundError(f"Project {project_id} does not exist")
        state, step, action = workflow_state_for_project(project)
        workflow_id, correlation_id = uuid.uuid4(), uuid.uuid4()
        workflow = WorkflowInstanceModel(
            id=workflow_id,
            project_id=project_id,
            definition_name="vertical_slice",
            workflow_version=self.VERSION,
            state=state,
            current_step=step,
            context_version=1,
            correlation_id=correlation_id,
            optimistic_version=1,
            recommended_operator_action=action,
        )
        context = WorkflowContext(
            workflow_id=workflow_id,
            project_id=project_id,
            current_state=state,
            correlation_id=correlation_id,
            actor_id=actor_id,
        )
        self.session.add(workflow)
        await self.session.flush()
        self.session.add(
            WorkflowContextModel(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                version=1,
                state=state,
                context=context.model_dump(mode="json"),
                context_hash=context.content_hash(),
            )
        )
        self.session.add(
            WorkflowTransitionModel(
                id=uuid.uuid4(),
                workflow_id=workflow_id,
                sequence=1,
                previous_state="unlinked",
                current_state=state,
                step=step,
                actor_type="human",
                actor_id=actor_id,
                reason=reason,
                workflow_version=self.VERSION,
                correlation_id=correlation_id,
            )
        )
        await AuditWriter(self.session).append_project_event(
            project_id=project_id,
            event_type="workflow.relinked",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "workflow_id": str(workflow_id),
                "state": state,
                "reason": reason,
            },
        )
        await self.session.commit()
        await self.session.refresh(workflow)
        return workflow

    async def advance(self, workflow_id: uuid.UUID) -> WorkflowInstanceModel:
        workflow = await self.repository.get(workflow_id, lock=True)
        state = WorkflowState(workflow.state)
        if state in TERMINAL_STATES or state is WorkflowState.CANCELLING:
            return workflow
        context = await self.repository.context(workflow)
        if state is WorkflowState.PROJECT_CREATED:
            if self.settings is None:
                raise RuntimeError("Workflow advancement requires application settings")
            run = await ProjectWorkflowService(
                session=self.session, settings=self.settings
            ).queue_requirements_run(project_id=workflow.project_id, actor_id="workflow-engine")
            context = context.evolved(run_ids={**context.run_ids, "requirements": run.id})
            attempt = WorkflowStepAttemptModel(
                id=uuid.uuid4(),
                workflow_id=workflow.id,
                step=WorkflowStepName.REQUIREMENTS,
                step_version="1.0",
                attempt=1,
                status="succeeded",
                policy={"max_attempts": 3, "timeout_seconds": 300},
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            self.session.add(attempt)
            await self.repository.append_transition(
                workflow=workflow,
                context=context,
                next_state=WorkflowState.REQUIREMENTS_RUNNING,
                step=WorkflowStepName.REQUIREMENTS,
                actor_type="system",
                actor_id="workflow-engine",
                reason="Workflow execution started",
                checkpoint=False,
            )
            await AuditWriter(self.session).append_project_event(
                project_id=workflow.project_id,
                event_type="workflow.transitioned",
                actor_type="system",
                actor_id="workflow-engine",
                payload={
                    "workflow_id": str(workflow.id),
                    "state": workflow.state,
                    "correlation_id": str(workflow.correlation_id),
                },
            )
        elif state is WorkflowState.REQUIREMENTS_RUNNING:
            project = await self.session.get(ProjectModel, workflow.project_id)
            if (
                project is not None
                and project.status == ProjectStatus.AWAITING_REQUIREMENTS_APPROVAL
            ):
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.WAITING_REQUIREMENTS_APPROVAL,
                    step=WorkflowStepName.REQUIREMENTS,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Requirements artifact awaits approval",
                )
            elif project is not None and project.status == ProjectStatus.REQUIREMENTS_APPROVED:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                run = await ProjectWorkflowService(
                    session=self.session, settings=self.settings
                ).queue_architecture_run(project_id=workflow.project_id, actor_id="workflow-engine")
                context = context.evolved(run_ids={**context.run_ids, "architecture": run.id})
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.ARCHITECTURE_RUNNING,
                    step=WorkflowStepName.ARCHITECTURE,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Requirements approved by autonomy policy",
                    checkpoint=False,
                )
        elif state is WorkflowState.WAITING_REQUIREMENTS_APPROVAL:
            project = await self.session.get(ProjectModel, workflow.project_id)
            if project is not None and project.status == ProjectStatus.REQUIREMENTS_APPROVED:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                run = await ProjectWorkflowService(
                    session=self.session, settings=self.settings
                ).queue_architecture_run(project_id=workflow.project_id, actor_id="workflow-engine")
                context = context.evolved(run_ids={**context.run_ids, "architecture": run.id})
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.ARCHITECTURE_RUNNING,
                    step=WorkflowStepName.ARCHITECTURE,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Requirements approved",
                    checkpoint=False,
                )
        elif state is WorkflowState.ARCHITECTURE_RUNNING:
            project = await self.session.get(ProjectModel, workflow.project_id)
            if (
                project is not None
                and project.status == ProjectStatus.AWAITING_ARCHITECTURE_APPROVAL
            ):
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.WAITING_ARCHITECTURE_APPROVAL,
                    step=WorkflowStepName.ARCHITECTURE,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Architecture artifact awaits approval",
                )
            elif project is not None and project.status == ProjectStatus.ARCHITECTURE_APPROVED:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                run = await ProjectWorkflowService(
                    session=self.session, settings=self.settings
                ).queue_work_package_planning(
                    project_id=workflow.project_id, actor_id="workflow-engine"
                )
                context = context.evolved(run_ids={**context.run_ids, "planning": run.id})
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.PLANNING_RUNNING,
                    step=WorkflowStepName.PLANNING,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Architecture approved by autonomy policy",
                    checkpoint=False,
                )
        elif state is WorkflowState.WAITING_ARCHITECTURE_APPROVAL:
            project = await self.session.get(ProjectModel, workflow.project_id)
            if project is not None and project.status == ProjectStatus.ARCHITECTURE_APPROVED:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                run = await ProjectWorkflowService(
                    session=self.session, settings=self.settings
                ).queue_work_package_planning(
                    project_id=workflow.project_id, actor_id="workflow-engine"
                )
                context = context.evolved(run_ids={**context.run_ids, "planning": run.id})
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.PLANNING_RUNNING,
                    step=WorkflowStepName.PLANNING,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Architecture approved",
                    checkpoint=False,
                )
        elif state is WorkflowState.PLANNING_RUNNING:
            project = await self.session.get(ProjectModel, workflow.project_id)
            if (
                project is not None
                and project.status == ProjectStatus.AWAITING_WORK_PACKAGE_APPROVAL
            ):
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.WAITING_WORK_PACKAGE_APPROVAL,
                    step=WorkflowStepName.PLANNING,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Work package awaits approval",
                )
            elif project is not None and project.status == ProjectStatus.WORK_PACKAGE_APPROVED:
                package = await self.session.scalar(
                    select(WorkPackageModel)
                    .where(
                        WorkPackageModel.project_id == workflow.project_id,
                        WorkPackageModel.status == WorkPackageStatus.APPROVED,
                    )
                    .order_by(WorkPackageModel.created_at.desc())
                )
                if package is not None:
                    if self.settings is None:
                        raise RuntimeError("Workflow advancement requires application settings")
                    execution = await ExecutionApplicationService(
                        session=self.session, settings=self.settings
                    ).request_execution(
                        project_id=workflow.project_id,
                        work_package_id=package.id,
                        idempotency_key=f"workflow:{workflow.id}:execution",
                        actor_id="workflow-engine",
                    )
                    context = context.evolved(execution_id=execution.id)
                    await self.repository.append_transition(
                        workflow=workflow,
                        context=context,
                        next_state=WorkflowState.EXECUTION_RUNNING,
                        step=WorkflowStepName.EXECUTION,
                        actor_type="system",
                        actor_id="workflow-engine",
                        reason="Work package approved by autonomy policy",
                        checkpoint=False,
                    )
        elif state is WorkflowState.WAITING_WORK_PACKAGE_APPROVAL:
            package = await self.session.scalar(
                select(WorkPackageModel)
                .where(
                    WorkPackageModel.project_id == workflow.project_id,
                    WorkPackageModel.status == WorkPackageStatus.APPROVED,
                )
                .order_by(WorkPackageModel.created_at.desc())
            )
            if package is not None:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                execution = await ExecutionApplicationService(
                    session=self.session, settings=self.settings
                ).request_execution(
                    project_id=workflow.project_id,
                    work_package_id=package.id,
                    idempotency_key=f"workflow:{workflow.id}:execution",
                    actor_id="workflow-engine",
                )
                context = context.evolved(execution_id=execution.id)
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.EXECUTION_RUNNING,
                    step=WorkflowStepName.EXECUTION,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Work package approved",
                    checkpoint=False,
                )
        elif state is WorkflowState.EXECUTION_RUNNING:
            successful_execution = await self.session.scalar(
                select(ExecutionRunModel).where(
                    ExecutionRunModel.id == context.execution_id,
                    ExecutionRunModel.status == ExecutionStatus.SUCCEEDED,
                )
            )
            if successful_execution is not None:
                if self.settings is None:
                    raise RuntimeError("Workflow advancement requires application settings")
                review = await ReviewCandidatePatchService(
                    session=self.session, settings=self.settings
                ).request_review(
                    project_id=workflow.project_id,
                    execution_id=successful_execution.id,
                    idempotency_key=f"workflow:{workflow.id}:review",
                    actor_id="workflow-engine",
                )
                context = context.evolved(review_id=review.id)
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.PATCH_REVIEW_RUNNING,
                    step=WorkflowStepName.REVIEW,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Execution and tests succeeded",
                    checkpoint=False,
                )
        elif state is WorkflowState.PATCH_REVIEW_RUNNING:
            loaded_review = await self.session.get(PatchReviewRunModel, context.review_id)
            if loaded_review is not None and loaded_review.status == PatchReviewStatus.ACCEPTED:
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context,
                    next_state=WorkflowState.WAITING_INTEGRATION_APPROVAL,
                    step=WorkflowStepName.REVIEW,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Independent review accepted patch",
                )
        elif state is WorkflowState.WAITING_INTEGRATION_APPROVAL:
            integration_attempt = await self.session.scalar(
                select(IntegrationAttemptModel)
                .where(IntegrationAttemptModel.execution_run_id == context.execution_id)
                .order_by(IntegrationAttemptModel.created_at.desc())
            )
            if integration_attempt is not None:
                await self.repository.append_transition(
                    workflow=workflow,
                    context=context.evolved(integration_attempt_id=integration_attempt.id),
                    next_state=WorkflowState.INTEGRATING,
                    step=WorkflowStepName.INTEGRATION,
                    actor_type="system",
                    actor_id="workflow-engine",
                    reason="Human integration approval consumed",
                    checkpoint=False,
                )
        elif state is WorkflowState.INTEGRATING and context.integration_attempt_id:
            commit = await self.session.scalar(
                select(IntegrationCommitModel).where(
                    IntegrationCommitModel.integration_attempt_id == context.integration_attempt_id,
                    IntegrationCommitModel.remote_verified.is_(True),
                )
            )
            if commit is not None:
                artifacts = list(
                    (
                        await self.session.scalars(
                            select(ArtifactModel).where(
                                ArtifactModel.project_id == workflow.project_id
                            )
                        )
                    ).all()
                )
                type_names = {
                    "project_manifest": "manifest",
                    "requirements_specification": "requirements",
                    "architecture_specification": "architecture",
                    "work_package": "work_package",
                    "candidate-patch": "patch",
                    "patch-review-report": "review",
                }
                artifact_ids = {
                    type_names[item.artifact_type]: item.id
                    for item in artifacts
                    if item.artifact_type in type_names
                }
                artifact_hashes = {
                    type_names[item.artifact_type]: item.content_hash
                    for item in artifacts
                    if item.artifact_type in type_names
                }
                approvals = list(
                    (
                        await self.session.scalars(
                            select(ApprovalModel).where(
                                ApprovalModel.project_id == workflow.project_id
                            )
                        )
                    ).all()
                )
                approval_ids = dict(context.approval_ids)
                for name in ("requirements", "architecture", "work_package"):
                    artifact_id = artifact_ids.get(name)
                    match = next(
                        (item for item in approvals if item.artifact_id == artifact_id), None
                    )
                    if match is not None:
                        approval_ids[name] = match.id
                completed_attempt = await self.session.get(
                    IntegrationAttemptModel, context.integration_attempt_id
                )
                completed_execution = (
                    await self.session.get(ExecutionRunModel, context.execution_id)
                    if context.execution_id is not None
                    else None
                )
                completed_review = (
                    await self.session.get(PatchReviewRunModel, context.review_id)
                    if context.review_id is not None
                    else None
                )
                if completed_attempt is not None:
                    approval_ids["integration"] = completed_attempt.integration_approval_id
                evidence_links = dict(context.evidence_links)
                if completed_execution is not None:
                    evidence_links.update(
                        {
                            "execution:approval_id": str(completed_execution.approval_id),
                            "execution:work_package_id": str(completed_execution.work_package_id),
                        }
                    )
                if completed_review is not None:
                    evidence_links.update(
                        {
                            "review:execution_id": str(completed_review.execution_run_id),
                            "review:patch_artifact_id": str(completed_review.patch_artifact_id),
                            "review:expected_patch_sha256": completed_review.expected_patch_sha256,
                        }
                    )
                    if completed_review.actual_patch_sha256 is not None:
                        evidence_links["review:actual_patch_sha256"] = (
                            completed_review.actual_patch_sha256
                        )
                    if completed_review.review_report_artifact_id is not None:
                        evidence_links["review:report_artifact_id"] = str(
                            completed_review.review_report_artifact_id
                        )
                if completed_attempt is not None:
                    evidence_links.update(
                        {
                            "integration:execution_id": str(completed_attempt.execution_run_id),
                            "integration:approval_id": str(
                                completed_attempt.integration_approval_id
                            ),
                            "integration:expected_patch_sha256": (
                                completed_attempt.expected_patch_sha256
                            ),
                            "integration:expected_base_commit_sha": (
                                completed_attempt.expected_base_commit_sha
                            ),
                            "integration:expected_base_tree_sha": (
                                completed_attempt.expected_base_tree_sha
                            ),
                        }
                    )
                    if completed_attempt.actual_base_commit_sha is not None:
                        evidence_links["integration:actual_base_commit_sha"] = (
                            completed_attempt.actual_base_commit_sha
                        )
                    if completed_attempt.actual_base_tree_sha is not None:
                        evidence_links["integration:actual_base_tree_sha"] = (
                            completed_attempt.actual_base_tree_sha
                        )
                    if completed_attempt.resulting_tree_sha is not None:
                        evidence_links["integration:resulting_tree_sha"] = (
                            completed_attempt.resulting_tree_sha
                        )
                evidence_links.update(
                    {
                        "commit:integration_attempt_id": str(commit.integration_attempt_id),
                        "commit:tree_sha": commit.tree_sha,
                        "commit:parent_commit_sha": commit.parent_commit_sha,
                        "commit:remote_verified": str(commit.remote_verified).lower(),
                    }
                )
                completed_context = context.evolved(
                    artifact_ids=artifact_ids,
                    artifact_hashes=artifact_hashes,
                    approval_ids=approval_ids,
                    evidence_links=evidence_links,
                    commit_id=commit.commit_sha,
                )
                result = verify_completeness(completed_context)
                if result.complete:
                    await self.repository.append_transition(
                        workflow=workflow,
                        context=completed_context,
                        next_state=WorkflowState.COMPLETED,
                        step=WorkflowStepName.COMPLETENESS,
                        actor_type="system",
                        actor_id="workflow-engine",
                        reason="All mandatory evidence and hashes are bound",
                    )
                else:
                    workflow.failure_code = "INCOMPLETE_AUDIT_EVIDENCE"
                    workflow.failure_message = ", ".join(result.missing)
                    workflow.recommended_operator_action = (
                        "Restore missing immutable evidence and retry completion"
                    )
        await self.session.commit()
        return workflow

    async def notify(self, project_id: uuid.UUID) -> None:
        workflow = await self.session.scalar(
            select(WorkflowInstanceModel).where(WorkflowInstanceModel.project_id == project_id)
        )
        if workflow is None or WorkflowState(workflow.state) in TERMINAL_STATES:
            return
        await JobRepository(self.session).enqueue(
            project_id=project_id,
            run_id=None,
            job_type="advance_workflow",
            payload={
                "workflow_id": str(workflow.id),
                "correlation_id": str(workflow.correlation_id),
            },
            max_attempts=3,
        )
        await self.session.commit()

    async def dead_letter(self, *, project_id: uuid.UUID, error: str) -> None:
        workflow = await self.session.scalar(
            select(WorkflowInstanceModel)
            .where(WorkflowInstanceModel.project_id == project_id)
            .with_for_update()
        )
        if workflow is None or WorkflowState(workflow.state) in TERMINAL_STATES:
            return
        context = await self.repository.context(workflow)
        workflow.failure_code = "STEP_RETRIES_EXHAUSTED"
        workflow.failure_message = error
        workflow.recommended_operator_action = "Inspect the last checkpoint and retry manually"
        await self.repository.append_transition(
            workflow=workflow,
            context=context,
            next_state=WorkflowState.FAILED,
            step=None,
            actor_type="system",
            actor_id="workflow-engine",
            reason="Job retry policy exhausted",
            checkpoint=False,
        )
        await self.session.flush()

    async def cancel(
        self, *, workflow_id: uuid.UUID, actor_id: str, reason: str
    ) -> WorkflowInstanceModel:
        workflow = await self.repository.get(workflow_id, lock=True)
        state = WorkflowState(workflow.state)
        if state is WorkflowState.CANCELLED:
            return workflow
        if state in TERMINAL_STATES:
            raise WorkflowConflictError(f"Cannot cancel workflow in state {state}")
        context = await self.repository.context(workflow)
        context = await self.repository.append_transition(
            workflow=workflow,
            context=context.evolved(cancellation_requested=True),
            next_state=WorkflowState.CANCELLING,
            step=None,
            actor_type="human",
            actor_id=actor_id,
            reason=reason,
            checkpoint=False,
        )
        workflow.cancellation_requested_at = datetime.now(UTC)
        await self.repository.append_transition(
            workflow=workflow,
            context=context,
            next_state=WorkflowState.CANCELLED,
            step=None,
            actor_type="system",
            actor_id="workflow-engine",
            reason="Cancellation persisted; no active resource lease remains",
            checkpoint=False,
        )
        await AuditWriter(self.session).append_project_event(
            project_id=workflow.project_id,
            event_type="workflow.cancelled",
            actor_type="human",
            actor_id=actor_id,
            payload={
                "workflow_id": str(workflow.id),
                "reason": reason,
                "correlation_id": str(workflow.correlation_id),
            },
        )
        await self.session.commit()
        return workflow

    async def history(self, workflow_id: uuid.UUID) -> list[WorkflowTransitionModel]:
        await self.repository.get(workflow_id)
        return list(
            (
                await self.session.scalars(
                    select(WorkflowTransitionModel)
                    .where(WorkflowTransitionModel.workflow_id == workflow_id)
                    .order_by(WorkflowTransitionModel.sequence)
                )
            ).all()
        )
