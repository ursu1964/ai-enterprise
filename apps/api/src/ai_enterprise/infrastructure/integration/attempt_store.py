from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.integration.processor import IntegrationCommand
from ai_enterprise.domain.execution.policies import DEFAULT_FORBIDDEN_PATHS, ExecutionScope
from ai_enterprise.domain.hashing import hash_json, hash_text
from ai_enterprise.domain.integration.enums import (
    IntegrationApprovalDecision,
    IntegrationAttemptStatus,
    PatchStatus,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    ExecutionRunModel,
    IntegrationApprovalModel,
    IntegrationAttemptModel,
    IntegrationEligibilityModel,
    PatchReviewRunModel,
    ProjectModel,
    WorkPackageModel,
)

from .models import (
    ApprovedTestCommand,
    CandidateCommit,
    IntegrationBinding,
    RemoteEvidence,
    RepositoryPolicy,
    TestRunEvidence,
)


class IntegrationAttemptLoadError(RuntimeError):
    pass


class SqlAlchemyIntegrationAttemptStore:
    """Durable stage transitions with an audit event in the same transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim_and_load(self, attempt_id: uuid.UUID, worker_id: str) -> IntegrationCommand:
        attempt = await self._session.scalar(
            select(IntegrationAttemptModel)
            .where(IntegrationAttemptModel.id == attempt_id)
            .with_for_update(skip_locked=True)
        )
        if attempt is None:
            raise IntegrationAttemptLoadError("INTEGRATION_ATTEMPT_NOT_FOUND_OR_CLAIMED")
        if attempt.status != IntegrationAttemptStatus.QUEUED:
            raise IntegrationAttemptLoadError("INTEGRATION_ATTEMPT_NOT_QUEUED")

        approval = await self._session.get(
            IntegrationApprovalModel, attempt.integration_approval_id
        )
        execution = await self._session.get(ExecutionRunModel, attempt.execution_run_id)
        if approval is None or execution is None:
            raise IntegrationAttemptLoadError("INTEGRATION_BINDING_MISSING")
        eligibility = await self._session.get(IntegrationEligibilityModel, approval.eligibility_id)
        project = await self._session.get(ProjectModel, attempt.project_id)
        work_package = await self._session.get(WorkPackageModel, execution.work_package_id)
        artifact = (
            await self._session.get(ArtifactModel, execution.patch_artifact_id)
            if execution.patch_artifact_id
            else None
        )
        review = (
            await self._session.get(PatchReviewRunModel, eligibility.accepted_review_id)
            if eligibility and eligibility.accepted_review_id
            else None
        )
        if None in (eligibility, project, work_package, artifact, review):
            raise IntegrationAttemptLoadError("INTEGRATION_EVIDENCE_MISSING")
        assert eligibility is not None
        assert project is not None
        assert work_package is not None
        assert artifact is not None
        assert review is not None

        self._validate_bindings(
            attempt=attempt,
            approval=approval,
            execution=execution,
            eligibility=eligibility,
            project=project,
            artifact=artifact,
            review=review,
        )
        commands = self._approved_commands(approval)
        scope = self._scope(work_package.contract)
        attempt.status = IntegrationAttemptStatus.VERIFYING
        attempt.worker_id = worker_id
        attempt.started_at = datetime.now(UTC)
        attempt.failure_code = None
        attempt.failure_message = None
        await self._audit(
            attempt,
            "integration.verifying",
            {
                "worker_id": worker_id,
                "approval_id": str(approval.id),
                "patch_sha256": approval.approved_patch_sha256,
            },
        )
        await self._session.commit()

        return IntegrationCommand(
            attempt_id=attempt.id,
            project_id=attempt.project_id,
            worker_id=worker_id,
            policy=RepositoryPolicy(
                repository_id=str(project.id),
                remote_url=approval.repository_url,
                target_branch=approval.target_branch,
                allowed_target_branches=(project.default_branch,),
            ),
            binding=IntegrationBinding(
                patch_id=str(execution.id),
                patch_sha256=execution.patch_sha256 or "",
                artifact_sha256=artifact.content_hash,
                audit_patch_sha256=eligibility.patch_sha256,
                approved_patch_sha256=approval.approved_patch_sha256,
                base_commit_sha=approval.approved_base_commit_sha,
                base_tree_sha=approval.approved_base_tree_sha,
                approval_id=str(approval.id),
                attempt_id=str(attempt.id),
            ),
            patch_bytes=artifact.content.encode("utf-8"),
            scope=scope,
            tests=commands,
            commit_message=self._commit_message(
                project_id=project.id,
                work_package_id=work_package.id,
                execution_id=execution.id,
                review_id=review.id,
                approval_id=approval.id,
                attempt_id=attempt.id,
                patch_sha256=approval.approved_patch_sha256,
            ),
            commit_timestamp=approval.approved_at or approval.created_at,
        )

    async def transition(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None:
        attempt = await self._locked(attempt_id)
        attempt.status = status
        if value := evidence.get("actual_base_commit_sha"):
            attempt.actual_base_commit_sha = str(value)
        if value := evidence.get("actual_base_tree_sha"):
            attempt.actual_base_tree_sha = str(value)
        if value := evidence.get("candidate_tree_sha") or evidence.get("tested_tree_sha"):
            attempt.resulting_tree_sha = str(value)
        await self._audit(attempt, event_type, evidence)
        await self._session.commit()

    async def fail(
        self,
        attempt_id: uuid.UUID,
        status: IntegrationAttemptStatus,
        code: str,
        message: str,
    ) -> None:
        attempt = await self._locked(attempt_id)
        attempt.status = status
        attempt.failure_code = code
        attempt.failure_message = message
        attempt.completed_at = datetime.now(UTC)
        execution = await self._session.get(ExecutionRunModel, attempt.execution_run_id)
        if execution is not None:
            execution.patch_status = PatchStatus.INTEGRATION_FAILED
        await self._audit(
            attempt,
            "integration.attempt_failed",
            {"status": status, "failure_code": code, "failure_message": message},
        )
        await self._session.commit()

    async def complete(
        self,
        command: IntegrationCommand,
        candidate: CandidateCommit,
        remote: RemoteEvidence,
        tests: tuple[TestRunEvidence, ...],
    ) -> None:
        attempt = await self._locked(command.attempt_id)
        if attempt.status != IntegrationAttemptStatus.PUSHING:
            raise IntegrationAttemptLoadError("INVALID_INTEGRATION_COMPLETION_STATE")
        attempt.status = IntegrationAttemptStatus.INTEGRATED
        attempt.resulting_tree_sha = remote.tree_sha
        attempt.completed_at = datetime.now(UTC)
        execution = await self._session.get(ExecutionRunModel, attempt.execution_run_id)
        if execution is None:
            raise IntegrationAttemptLoadError("EXECUTION_NOT_FOUND")
        execution.patch_status = PatchStatus.INTEGRATED
        await self._audit(
            attempt,
            "integration.completed",
            {
                "commit_sha": remote.commit_sha,
                "tree_sha": remote.tree_sha,
                "parent_sha": remote.parent_sha,
                "branch": remote.branch,
                "author_identity": candidate.author_identity,
                "committer_identity": candidate.committer_identity,
                "test_runs": [
                    {
                        "command_index": item.command_index,
                        "command_sha256": item.command_sha256,
                        "status": item.status,
                        "exit_code": item.exit_code,
                        "duration_ms": item.duration_ms,
                    }
                    for item in tests
                ],
            },
        )
        await self._session.commit()

    async def _locked(self, attempt_id: uuid.UUID) -> IntegrationAttemptModel:
        attempt = await self._session.scalar(
            select(IntegrationAttemptModel)
            .where(IntegrationAttemptModel.id == attempt_id)
            .with_for_update()
        )
        if attempt is None:
            raise IntegrationAttemptLoadError("INTEGRATION_ATTEMPT_NOT_FOUND")
        return attempt

    @staticmethod
    def _validate_bindings(
        *,
        attempt: IntegrationAttemptModel,
        approval: IntegrationApprovalModel,
        execution: ExecutionRunModel,
        eligibility: IntegrationEligibilityModel,
        project: ProjectModel,
        artifact: ArtifactModel,
        review: PatchReviewRunModel,
    ) -> None:
        hashes = {
            attempt.expected_patch_sha256,
            approval.approved_patch_sha256,
            eligibility.patch_sha256,
            execution.patch_sha256,
            artifact.content_hash,
            review.actual_patch_sha256,
            hash_text(artifact.content),
        }
        if None in hashes or len(hashes) != 1:
            raise IntegrationAttemptLoadError("PATCH_ARTIFACT_MISMATCH")
        if approval.decision != IntegrationApprovalDecision.CONSUMED:
            raise IntegrationAttemptLoadError("INTEGRATION_APPROVAL_NOT_ACTIVE")
        if not eligibility.eligible or review.status != "accepted":
            raise IntegrationAttemptLoadError("PATCH_NOT_ELIGIBLE")
        if (
            approval.execution_run_id != execution.id
            or eligibility.execution_run_id != execution.id
        ):
            raise IntegrationAttemptLoadError("EXECUTION_BINDING_MISMATCH")
        if (
            len(
                {
                    attempt.expected_base_commit_sha,
                    approval.approved_base_commit_sha,
                    eligibility.base_commit_sha,
                    execution.base_commit,
                }
            )
            != 1
        ):
            raise IntegrationAttemptLoadError("BASE_COMMIT_BINDING_MISMATCH")
        if (
            len(
                {
                    attempt.expected_base_tree_sha,
                    approval.approved_base_tree_sha,
                    eligibility.base_tree_sha,
                    execution.base_tree_sha,
                }
            )
            != 1
        ):
            raise IntegrationAttemptLoadError("BASE_TREE_BINDING_MISMATCH")
        if approval.repository_url != project.repository_url:
            raise IntegrationAttemptLoadError("REPOSITORY_BINDING_MISMATCH")
        if (
            approval.target_branch != project.default_branch
            or attempt.target_branch != project.default_branch
        ):
            raise IntegrationAttemptLoadError("TARGET_BRANCH_NOT_ALLOWED")
        if (
            hash_json({"commands": approval.approved_test_commands})
            != approval.approved_test_commands_sha256
        ):
            raise IntegrationAttemptLoadError("TEST_COMMAND_BINDING_MISMATCH")

    @staticmethod
    def _approved_commands(
        approval: IntegrationApprovalModel,
    ) -> tuple[ApprovedTestCommand, ...]:
        commands: list[ApprovedTestCommand] = []
        for item in approval.approved_test_commands:
            argv = item.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
                raise IntegrationAttemptLoadError("INVALID_APPROVED_TEST_COMMAND")
            commands.append(
                ApprovedTestCommand(
                    argv=tuple(argv),
                    timeout_seconds=int(item.get("timeout_seconds", 300)),
                    environment=dict(item.get("environment", {})),
                )
            )
        return tuple(commands)

    @staticmethod
    def _scope(contract: dict[str, Any]) -> ExecutionScope:
        file_scope = contract["file_scope"]
        allowed = tuple([*file_scope["allowed_files"], *file_scope.get("allowed_directories", [])])
        forbidden = tuple(
            [
                *file_scope.get("forbidden_files", []),
                *file_scope.get("forbidden_directories", []),
                *DEFAULT_FORBIDDEN_PATHS,
            ]
        )
        return ExecutionScope(allowed_paths=allowed, forbidden_paths=forbidden)

    async def _audit(
        self,
        attempt: IntegrationAttemptModel,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        await AuditWriter(self._session).append_project_event(
            project_id=attempt.project_id,
            event_type=event_type,
            actor_type="integration_worker",
            actor_id=attempt.worker_id or "unclaimed",
            payload={
                "attempt_id": str(attempt.id),
                "correlation_id": str(attempt.correlation_id),
                **payload,
            },
        )

    @staticmethod
    def _commit_message(**values: uuid.UUID | str) -> str:
        return (
            "integrate(work-package): apply approved patch\n\n"
            f"Project: {values['project_id']}\n"
            f"Work package: {values['work_package_id']}\n"
            f"Execution attempt: {values['execution_id']}\n"
            f"Patch SHA-256: {values['patch_sha256']}\n"
            f"Review: {values['review_id']}\n"
            f"Integration approval: {values['approval_id']}\n"
            f"Integration attempt: {values['attempt_id']}\n"
        )
