import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.domain.enums import JobType
from ai_enterprise.domain.execution.enums import ExecutionStatus, TestStatus
from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.integration.enums import (
    IntegrationApprovalDecision,
    IntegrationAttemptStatus,
    PatchStatus,
)
from ai_enterprise.domain.integration.exceptions import (
    IntegrationApprovalNotActiveError,
    IntegrationBindingMismatchError,
    PatchNotEligibleError,
)
from ai_enterprise.domain.integration.policies import (
    IntegrationAuthorizationPolicy,
    PatchEligibilityPolicy,
)
from ai_enterprise.infrastructure.database.models import (
    ExecutionRunModel,
    ExecutionTestResultModel,
    IntegrationApprovalModel,
    IntegrationAttemptModel,
    IntegrationEligibilityModel,
    PatchReviewFindingModel,
    PatchReviewRunModel,
    ProjectModel,
    WorkPackageModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository


class IntegrationNotFoundError(Exception):
    pass


class ControlledIntegrationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def evaluate_eligibility(
        self, execution_run_id: uuid.UUID
    ) -> IntegrationEligibilityModel:
        execution = await self._session.get(ExecutionRunModel, execution_run_id)
        if execution is None:
            raise IntegrationNotFoundError("Candidate patch not found")
        reviews = (
            (
                await self._session.execute(
                    select(PatchReviewRunModel)
                    .where(PatchReviewRunModel.execution_run_id == execution.id)
                    .order_by(PatchReviewRunModel.finished_at.desc())
                )
            )
            .scalars()
            .all()
        )
        accepted = next((item for item in reviews if item.status == "accepted"), None)
        unresolved = False
        if accepted is not None:
            unresolved = (
                await self._session.scalar(
                    select(func.count())
                    .select_from(PatchReviewFindingModel)
                    .where(
                        PatchReviewFindingModel.patch_review_run_id == accepted.id,
                        PatchReviewFindingModel.status == "open",
                    )
                )
                or 0
            ) > 0
        tests = (
            (
                await self._session.execute(
                    select(ExecutionTestResultModel).where(
                        ExecutionTestResultModel.execution_run_id == execution.id
                    )
                )
            )
            .scalars()
            .all()
        )
        work_package = await self._session.get(WorkPackageModel, execution.work_package_id)
        decision = PatchEligibilityPolicy().evaluate(
            execution_succeeded=execution.status == ExecutionStatus.SUCCEEDED,
            patch_hash_present=bool(execution.patch_sha256 and execution.patch_artifact_id),
            accepted_review=accepted is not None,
            review_independent=accepted is not None,
            work_package_matches=accepted is not None
            and accepted.work_package_id == execution.work_package_id,
            base_commit_matches=work_package is not None
            and work_package.base_commit_sha == execution.base_commit,
            base_tree_present=bool(execution.base_tree_sha),
            scope_validation_passed=execution.status == ExecutionStatus.SUCCEEDED,
            required_tests_passed=bool(tests)
            and all(test.status == TestStatus.PASSED for test in tests),
            unresolved_findings=unresolved,
        )
        existing = await self._session.scalar(
            select(IntegrationEligibilityModel).where(
                IntegrationEligibilityModel.execution_run_id == execution.id
            )
        )
        eligibility = existing or IntegrationEligibilityModel(
            id=uuid.uuid4(), execution_run_id=execution.id
        )
        eligibility.eligible = decision.eligible
        eligibility.evaluated_at = datetime.now(UTC)
        eligibility.policy_version = decision.policy_version
        eligibility.patch_sha256 = execution.patch_sha256 or ""
        eligibility.base_commit_sha = execution.base_commit
        eligibility.base_tree_sha = execution.base_tree_sha or ""
        eligibility.accepted_review_id = accepted.id if accepted else None
        eligibility.failure_reasons = [
            {"code": item.code, "message": item.message} for item in decision.failures
        ]
        eligibility.evidence = {
            "execution_status": execution.status,
            "review_status": accepted.status if accepted else None,
            "test_count": len(tests),
        }
        self._session.add(eligibility)
        execution.patch_status = (
            PatchStatus.INTEGRATION_ELIGIBLE if decision.eligible else execution.patch_status
        )
        await self._append_audit_event(
            project_id=execution.project_id,
            event_type="patch.integration_eligibility_evaluated",
            actor_type="system",
            actor_id="control-plane",
            payload={
                "execution_run_id": str(execution.id),
                "eligible": decision.eligible,
                "failure_reasons": eligibility.failure_reasons,
            },
        )
        await self._session.commit()
        await self._session.refresh(eligibility)
        return eligibility

    async def approve(
        self,
        *,
        execution_run_id: uuid.UUID,
        actor_subject: str,
        actor_type: str,
        actor_role: str,
        target_branch: str,
        reason: str,
    ) -> IntegrationApprovalModel:
        policy = IntegrationAuthorizationPolicy()
        policy.require_human(actor_type=actor_type)
        if actor_role != "integration_approver":
            from ai_enterprise.domain.integration.exceptions import HumanApprovalRequiredError

            raise HumanApprovalRequiredError("The integration_approver role is required")
        execution = await self._session.get(ExecutionRunModel, execution_run_id)
        if execution is None:
            raise IntegrationNotFoundError("Candidate patch not found")
        project = await self._session.get(ProjectModel, execution.project_id)
        eligibility = await self._session.scalar(
            select(IntegrationEligibilityModel)
            .where(IntegrationEligibilityModel.execution_run_id == execution.id)
            .with_for_update()
        )
        if project is None or eligibility is None or not eligibility.eligible:
            raise PatchNotEligibleError("Candidate patch is not integration-eligible")
        policy.require_allowed_branch(
            target_branch=target_branch, allowed_branches=(project.default_branch,)
        )
        if not project.repository_url:
            raise IntegrationBindingMismatchError("Authoritative repository URL is required")
        work_package = await self._session.get(WorkPackageModel, execution.work_package_id)
        commands = (work_package.contract.get("command_policy", {}) if work_package else {}).get(
            "test_commands", []
        )
        normalized = [{"argv": command} for command in commands]
        now = datetime.now(UTC)
        approval = IntegrationApprovalModel(
            id=uuid.uuid4(),
            execution_run_id=execution.id,
            eligibility_id=eligibility.id,
            approver_subject=actor_subject,
            approver_role=actor_role,
            project_id=project.id,
            repository_url=project.repository_url,
            target_branch=target_branch,
            approved_patch_sha256=eligibility.patch_sha256,
            approved_base_commit_sha=eligibility.base_commit_sha,
            approved_base_tree_sha=eligibility.base_tree_sha,
            approved_test_commands=normalized,
            approved_test_commands_sha256=hash_json({"commands": normalized}),
            decision=IntegrationApprovalDecision.APPROVED,
            reason=reason,
            policy_version=policy.POLICY_VERSION,
            approved_at=now,
        )
        self._session.add(approval)
        execution.patch_status = PatchStatus.INTEGRATION_APPROVED
        await self._append_audit_event(
            project_id=project.id,
            event_type="patch.integration_approval_granted",
            actor_type=actor_type,
            actor_id=actor_subject,
            payload={
                "approval_id": str(approval.id),
                "execution_run_id": str(execution.id),
                "patch_sha256": approval.approved_patch_sha256,
                "target_branch": target_branch,
            },
        )
        await self._session.commit()
        await self._session.refresh(approval)
        return approval

    async def create_attempt(self, approval_id: uuid.UUID) -> IntegrationAttemptModel:
        approval = await self._session.scalar(
            select(IntegrationApprovalModel)
            .where(IntegrationApprovalModel.id == approval_id)
            .with_for_update()
        )
        if approval is None:
            raise IntegrationNotFoundError("Integration approval not found")
        if approval.decision != IntegrationApprovalDecision.APPROVED:
            raise IntegrationApprovalNotActiveError("Integration approval is not active")
        execution = await self._session.get(ExecutionRunModel, approval.execution_run_id)
        eligibility = await self._session.get(IntegrationEligibilityModel, approval.eligibility_id)
        if execution is None or eligibility is None or not eligibility.eligible:
            raise PatchNotEligibleError("Candidate patch is no longer eligible")
        if (
            execution.patch_sha256 != approval.approved_patch_sha256
            or execution.base_commit != approval.approved_base_commit_sha
            or execution.base_tree_sha != approval.approved_base_tree_sha
        ):
            raise IntegrationBindingMismatchError(
                "Approval binding no longer matches candidate patch"
            )
        attempt = IntegrationAttemptModel(
            id=uuid.uuid4(),
            execution_run_id=execution.id,
            integration_approval_id=approval.id,
            attempt_number=1,
            status=IntegrationAttemptStatus.QUEUED,
            project_id=approval.project_id,
            target_branch=approval.target_branch,
            expected_patch_sha256=approval.approved_patch_sha256,
            expected_base_commit_sha=approval.approved_base_commit_sha,
            expected_base_tree_sha=approval.approved_base_tree_sha,
            correlation_id=uuid.uuid4(),
        )
        self._session.add(attempt)
        approval.decision = IntegrationApprovalDecision.CONSUMED
        execution.patch_status = PatchStatus.INTEGRATING
        await self._append_audit_event(
            project_id=approval.project_id,
            event_type="integration.attempt_created",
            actor_type="system",
            actor_id="control-plane",
            payload={
                "attempt_id": str(attempt.id),
                "approval_id": str(approval.id),
                "correlation_id": str(attempt.correlation_id),
            },
        )
        await JobRepository(self._session).enqueue(
            project_id=approval.project_id,
            run_id=None,
            job_type=JobType.INTEGRATE_APPROVED_PATCH,
            payload={
                "integration_attempt_id": str(attempt.id),
                "correlation_id": str(attempt.correlation_id),
            },
            priority=50,
            max_attempts=1,
        )
        await self._session.commit()
        await self._session.refresh(attempt)
        return attempt

    async def _append_audit_event(
        self,
        *,
        project_id: uuid.UUID,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        await AuditWriter(self._session).append_project_event(
            project_id=project_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload,
        )
