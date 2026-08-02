from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.application.audit.writer import AuditWriter
from ai_enterprise.application.recovery.processor import RecoveryCommand
from ai_enterprise.domain.execution.policies import DEFAULT_FORBIDDEN_PATHS, ExecutionScope
from ai_enterprise.domain.hashing import canonical_json, hash_json, hash_text
from ai_enterprise.domain.recovery.bindings import approval_binding_hash
from ai_enterprise.domain.recovery.enums import (
    FailureClass,
    PipelineStage,
    RecoveryAttemptStatus,
    RecoveryStrategy,
    RollbackApprovalStatus,
)
from ai_enterprise.infrastructure.database.models import (
    ArtifactModel,
    ProjectModel,
    RecoveryAssessmentModel,
    RecoveryAttemptModel,
    RecoveryAttemptRunModel,
    RecoveryCommitModel,
    RecoveryRemoteVerificationModel,
    RecoveryStageExecutionModel,
    RecoveryTestRunModel,
    RollbackApprovalModel,
    RollbackRecordModel,
)
from ai_enterprise.infrastructure.integration.models import (
    ApprovedTestCommand,
    CandidateCommit,
    RemoteEvidence,
    RepositoryPolicy,
    TestRunEvidence,
)


class RecoveryAttemptStoreError(RuntimeError):
    pass


class SqlAlchemyRecoveryAttemptStore:
    """Fenced, durable state and evidence store for controlled recovery."""

    CLAIM_DURATION = timedelta(hours=1)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._active_runs: dict[uuid.UUID, uuid.UUID] = {}

    async def claim_and_load(self, attempt_id: uuid.UUID, worker_id: str) -> RecoveryCommand:
        attempt = await self._session.scalar(
            select(RecoveryAttemptModel)
            .where(RecoveryAttemptModel.id == attempt_id)
            .with_for_update(skip_locked=True)
        )
        if attempt is None:
            raise RecoveryAttemptStoreError("RECOVERY_ATTEMPT_NOT_FOUND_OR_CLAIMED")
        stored_status = RecoveryAttemptStatus(attempt.status)
        latest_run = await self._session.scalar(
            select(RecoveryAttemptRunModel)
            .where(RecoveryAttemptRunModel.recovery_attempt_id == attempt.id)
            .order_by(RecoveryAttemptRunModel.run_number.desc())
            .limit(1)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            latest_run is not None
            and latest_run.completed_at is None
            and latest_run.claim_expires_at > now
        ):
            raise RecoveryAttemptStoreError("RECOVERY_ATTEMPT_ALREADY_CLAIMED")
        safe_restart_statuses = {
            RecoveryAttemptStatus.QUEUED,
            RecoveryAttemptStatus.CLAIMED,
            RecoveryAttemptStatus.PREPARING_WORKSPACE,
            RecoveryAttemptStatus.CREATING_REVERT,
            RecoveryAttemptStatus.RUNNING_TESTS,
            RecoveryAttemptStatus.CREATING_COMMIT,
        }
        if stored_status == RecoveryAttemptStatus.PUSHING or (
            attempt.push_started_at is not None and stored_status != RecoveryAttemptStatus.RECOVERED
        ):
            initial_status = RecoveryAttemptStatus.PUSH_UNCERTAIN
        elif stored_status in safe_restart_statuses:
            initial_status = RecoveryAttemptStatus.QUEUED
        elif stored_status == RecoveryAttemptStatus.PUSH_UNCERTAIN:
            initial_status = stored_status
        else:
            raise RecoveryAttemptStoreError("RECOVERY_ATTEMPT_NOT_CLAIMABLE")
        approval = await self._session.get(RollbackApprovalModel, attempt.rollback_approval_id)
        assessment = await self._session.get(
            RecoveryAssessmentModel, attempt.recovery_assessment_id
        )
        rollback = await self._session.get(RollbackRecordModel, attempt.rollback_record_id)
        project = await self._session.get(ProjectModel, attempt.project_id)
        if None in (approval, assessment, rollback, project):
            raise RecoveryAttemptStoreError("RECOVERY_BINDING_MISSING")
        assert approval is not None
        assert assessment is not None
        assert rollback is not None
        assert project is not None
        self._validate(attempt, approval, assessment, rollback, project)

        if latest_run is not None and latest_run.completed_at is None:
            latest_run.status = "expired"
            latest_run.failure_class = FailureClass.TRANSIENT_INFRASTRUCTURE
            latest_run.failure_code = "CLAIM_EXPIRED"
            latest_run.completed_at = now
        run_number = (
            int(
                await self._session.scalar(
                    select(func.max(RecoveryAttemptRunModel.run_number)).where(
                        RecoveryAttemptRunModel.recovery_attempt_id == attempt.id
                    )
                )
                or 0
            )
            + 1
        )
        claim_token = uuid.uuid4().hex
        run = RecoveryAttemptRunModel(
            id=uuid.uuid4(),
            recovery_attempt_id=attempt.id,
            run_number=run_number,
            worker_id=worker_id,
            status="running",
            current_stage=PipelineStage.CLAIM,
            claim_token_hash=hash_text(claim_token),
            claim_expires_at=now + self.CLAIM_DURATION,
            started_at=now,
        )
        self._session.add(run)
        self._active_runs[attempt.id] = run.id
        attempt.status = (
            RecoveryAttemptStatus.PUSH_UNCERTAIN
            if initial_status == RecoveryAttemptStatus.PUSH_UNCERTAIN
            else RecoveryAttemptStatus.CLAIMED
        )
        attempt.worker_id = worker_id
        attempt.started_at = attempt.started_at or now
        await self._audit(
            attempt,
            "recovery.attempt_claimed",
            worker_id,
            {
                "run_id": str(run.id),
                "run_number": run_number,
                "initial_status": initial_status,
            },
        )
        await self._session.commit()

        existing = (
            await self._existing_candidate(attempt.id)
            if initial_status == RecoveryAttemptStatus.PUSH_UNCERTAIN
            else None
        )
        return RecoveryCommand(
            attempt_id=attempt.id,
            project_id=attempt.project_id,
            worker_id=worker_id,
            initial_status=initial_status,
            policy=RepositoryPolicy(
                repository_id=str(project.id),
                remote_url=project.repository_url or "",
                target_branch=attempt.target_branch,
                allowed_target_branches=(project.default_branch,),
            ),
            expected_remote_head_sha=attempt.expected_remote_head_sha,
            integration_commit_sha=attempt.integration_commit_sha,
            rollback_record_id=rollback.id,
            approval_id=approval.id,
            approval_binding_sha256=approval.approval_binding_sha256,
            scope=self._scope(rollback),
            tests=self._commands(approval),
            commit_message=self._commit_message(attempt, assessment),
            commit_timestamp=approval.approved_at,
            existing_candidate=existing,
        )

    async def transition(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        stage: PipelineStage,
        event_type: str,
        evidence: dict[str, Any],
    ) -> None:
        attempt, run = await self._locked(command)
        now = datetime.now(UTC)
        previous = await self._session.scalar(
            select(RecoveryStageExecutionModel)
            .where(
                RecoveryStageExecutionModel.run_id == run.id,
                RecoveryStageExecutionModel.status == "running",
            )
            .order_by(RecoveryStageExecutionModel.started_at.desc())
            .limit(1)
        )
        if previous is not None:
            previous.status = "completed"
            previous.completed_at = now
            previous.duration_ms = max(0, int((now - previous.started_at).total_seconds() * 1000))
            previous.output_binding_sha256 = hash_json({"evidence": evidence})
        run.current_stage = stage
        if stage == PipelineStage.PUSH:
            attempt.push_started_at = attempt.push_started_at or now
        attempt.status = status
        stage_number = (
            int(
                await self._session.scalar(
                    select(func.count())
                    .select_from(RecoveryStageExecutionModel)
                    .where(
                        RecoveryStageExecutionModel.run_id == run.id,
                        RecoveryStageExecutionModel.stage_name == stage,
                    )
                )
                or 0
            )
            + 1
        )
        self._session.add(
            RecoveryStageExecutionModel(
                id=uuid.uuid4(),
                run_id=run.id,
                stage_name=stage,
                stage_attempt=stage_number,
                status="running",
                input_binding_sha256=hash_json(
                    {
                        "approval_binding_sha256": command.approval_binding_sha256,
                        "stage": stage,
                        "attempt": stage_number,
                    }
                ),
                output_binding_sha256=None,
                started_at=now,
                completed_at=None,
                duration_ms=None,
            )
        )
        await self._audit(
            attempt, event_type, command.worker_id, {"run_id": str(run.id), **evidence}
        )
        await self._session.commit()

    async def record_tests(
        self, command: RecoveryCommand, tests: tuple[TestRunEvidence, ...]
    ) -> None:
        attempt, _ = await self._locked(command)
        for item in tests:
            stdout = self._artifact(attempt.project_id, "recovery_test_stdout", item.stdout)
            stderr = self._artifact(attempt.project_id, "recovery_test_stderr", item.stderr)
            self._session.add_all(
                (
                    stdout,
                    stderr,
                    RecoveryTestRunModel(
                        id=uuid.uuid4(),
                        recovery_attempt_id=attempt.id,
                        command_index=item.command_index,
                        command={"argv": list(item.argv), "sha256": item.command_sha256},
                        status=item.status,
                        exit_code=item.exit_code,
                        stdout_artifact_id=stdout.id,
                        stderr_artifact_id=stderr.id,
                        duration_ms=item.duration_ms,
                    ),
                )
            )
        await self._audit(
            attempt,
            "recovery.tests_completed",
            command.worker_id,
            {
                "test_runs": [
                    {
                        "index": item.command_index,
                        "status": item.status,
                        "exit_code": item.exit_code,
                    }
                    for item in tests
                ]
            },
        )
        await self._session.commit()

    async def record_commit(self, command: RecoveryCommand, candidate: CandidateCommit) -> None:
        attempt, _ = await self._locked(command)
        existing = await self._session.scalar(
            select(RecoveryCommitModel).where(RecoveryCommitModel.recovery_attempt_id == attempt.id)
        )
        if existing is not None:
            if (existing.commit_sha, existing.tree_sha, existing.parent_commit_sha) != (
                candidate.commit_sha,
                candidate.tree_sha,
                candidate.parent_sha,
            ):
                raise RecoveryAttemptStoreError("RECOVERY_COMMIT_REPLAY_MISMATCH")
            return
        name, email = self._identity(candidate.author_identity)
        self._session.add(
            RecoveryCommitModel(
                id=uuid.uuid4(),
                recovery_attempt_id=attempt.id,
                commit_sha=candidate.commit_sha,
                tree_sha=candidate.tree_sha,
                parent_commit_sha=candidate.parent_sha,
                reverted_integration_commit_sha=command.integration_commit_sha,
                commit_message_sha256=hash_text(candidate.message),
                author_name=name,
                author_email=email,
            )
        )
        await self._audit(
            attempt,
            "recovery.commit_created",
            command.worker_id,
            {
                "commit_sha": candidate.commit_sha,
                "tree_sha": candidate.tree_sha,
                "parent_sha": candidate.parent_sha,
            },
        )
        await self._session.commit()

    async def record_remote(self, command: RecoveryCommand, remote: RemoteEvidence) -> None:
        attempt, _ = await self._locked(command)
        commit = await self._session.scalar(
            select(RecoveryCommitModel).where(RecoveryCommitModel.recovery_attempt_id == attempt.id)
        )
        if commit is None:
            raise RecoveryAttemptStoreError("RECOVERY_COMMIT_NOT_FOUND")
        existing = await self._session.scalar(
            select(RecoveryRemoteVerificationModel).where(
                RecoveryRemoteVerificationModel.recovery_commit_id == commit.id
            )
        )
        if existing is None:
            self._session.add(
                RecoveryRemoteVerificationModel(
                    id=uuid.uuid4(),
                    recovery_commit_id=commit.id,
                    remote_commit_sha=remote.commit_sha,
                    remote_tree_sha=remote.tree_sha,
                    remote_parent_sha=remote.parent_sha,
                    integration_commit_in_history=True,
                    verified_at=datetime.now(UTC),
                )
            )
        elif (existing.remote_commit_sha, existing.remote_tree_sha, existing.remote_parent_sha) != (
            remote.commit_sha,
            remote.tree_sha,
            remote.parent_sha,
        ):
            raise RecoveryAttemptStoreError("RECOVERY_REMOTE_REPLAY_MISMATCH")
        await self._session.commit()

    async def record_conflict(
        self, command: RecoveryCommand, paths: tuple[str, ...], message: str
    ) -> None:
        attempt, run = await self._locked(command)
        content = canonical_json({"paths": list(paths), "message": message[:2000]})
        artifact = self._artifact(attempt.project_id, "recovery_revert_conflict", content)
        self._session.add(artifact)
        stage = await self._session.scalar(
            select(RecoveryStageExecutionModel)
            .where(
                RecoveryStageExecutionModel.run_id == run.id,
                RecoveryStageExecutionModel.stage_name == PipelineStage.REVERT,
            )
            .order_by(RecoveryStageExecutionModel.stage_attempt.desc())
            .limit(1)
        )
        if stage is None:
            stage = RecoveryStageExecutionModel(
                id=uuid.uuid4(),
                run_id=run.id,
                stage_name=PipelineStage.REVERT,
                stage_attempt=1,
                status="failed",
                input_binding_sha256=command.approval_binding_sha256,
                evidence_artifact_id=artifact.id,
                failure_code="REVERT_CONFLICT",
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_ms=0,
            )
            self._session.add(stage)
        else:
            stage.status = "failed"
            stage.evidence_artifact_id = artifact.id
            stage.failure_code = "REVERT_CONFLICT"
        await self._session.commit()

    async def fail(
        self,
        command: RecoveryCommand,
        status: RecoveryAttemptStatus,
        failure_class: FailureClass,
        code: str,
        message: str,
    ) -> None:
        attempt, run = await self._locked(command)
        attempt.status = status
        attempt.failure_class = failure_class
        attempt.failure_code = code
        attempt.failure_message = message[:2000]
        if status != RecoveryAttemptStatus.PUSH_UNCERTAIN:
            attempt.completed_at = datetime.now(UTC)
        run.status = "failed"
        run.failure_class = failure_class
        run.failure_code = code
        run.completed_at = datetime.now(UTC)
        await self._close_stage(run.id, status="failed", failure_code=code)
        await self._audit(
            attempt,
            "recovery.attempt_failed",
            command.worker_id,
            {
                "status": status,
                "failure_class": failure_class,
                "failure_code": code,
            },
        )
        await self._session.commit()

    async def complete(
        self, command: RecoveryCommand, candidate: CandidateCommit, remote: RemoteEvidence
    ) -> None:
        attempt, run = await self._locked(command)
        if (candidate.commit_sha, candidate.tree_sha, candidate.parent_sha) != (
            remote.commit_sha,
            remote.tree_sha,
            remote.parent_sha,
        ):
            raise RecoveryAttemptStoreError("RECOVERY_COMPLETION_BINDING_MISMATCH")
        attempt.status = RecoveryAttemptStatus.RECOVERED
        attempt.completed_at = datetime.now(UTC)
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        await self._close_stage(run.id, status="completed")
        await self._audit(
            attempt,
            "recovery.completed",
            command.worker_id,
            {
                "commit_sha": remote.commit_sha,
                "tree_sha": remote.tree_sha,
                "parent_sha": remote.parent_sha,
            },
        )
        await self._session.commit()

    async def _locked(
        self, command: RecoveryCommand
    ) -> tuple[RecoveryAttemptModel, RecoveryAttemptRunModel]:
        attempt = await self._session.scalar(
            select(RecoveryAttemptModel)
            .where(RecoveryAttemptModel.id == command.attempt_id)
            .with_for_update()
        )
        run_id = self._active_runs.get(command.attempt_id)
        run = await self._session.get(RecoveryAttemptRunModel, run_id) if run_id else None
        if (
            attempt is None
            or run is None
            or run.worker_id != command.worker_id
            or run.completed_at is not None
            or run.claim_expires_at <= datetime.now(UTC)
        ):
            raise RecoveryAttemptStoreError("RECOVERY_CLAIM_FENCE_LOST")
        run.claim_expires_at = datetime.now(UTC) + self.CLAIM_DURATION
        return attempt, run

    async def _close_stage(
        self, run_id: uuid.UUID, *, status: str, failure_code: str | None = None
    ) -> None:
        stage = await self._session.scalar(
            select(RecoveryStageExecutionModel)
            .where(
                RecoveryStageExecutionModel.run_id == run_id,
                RecoveryStageExecutionModel.status == "running",
            )
            .order_by(RecoveryStageExecutionModel.started_at.desc())
            .limit(1)
        )
        if stage is None:
            return
        now = datetime.now(UTC)
        stage.status = status
        stage.failure_code = failure_code
        stage.completed_at = now
        stage.duration_ms = max(0, int((now - stage.started_at).total_seconds() * 1000))

    @staticmethod
    def _validate(
        attempt: RecoveryAttemptModel,
        approval: RollbackApprovalModel,
        assessment: RecoveryAssessmentModel,
        rollback: RollbackRecordModel,
        project: ProjectModel,
    ) -> None:
        if approval.status != RollbackApprovalStatus.CONSUMED:
            raise RecoveryAttemptStoreError("ROLLBACK_APPROVAL_NOT_CONSUMED")
        if (
            attempt.recovery_strategy != RecoveryStrategy.REVERT_COMMIT
            or approval.recovery_strategy != RecoveryStrategy.REVERT_COMMIT
            or not assessment.direct_revert_possible
        ):
            raise RecoveryAttemptStoreError("RECOVERY_STRATEGY_NOT_EXECUTABLE")
        if (
            attempt.rollback_approval_id != approval.id
            or attempt.recovery_assessment_id != assessment.id
            or attempt.rollback_record_id != rollback.id
            or approval.recovery_assessment_id != assessment.id
            or approval.rollback_record_id != rollback.id
        ):
            raise RecoveryAttemptStoreError("RECOVERY_ID_BINDING_MISMATCH")
        if (
            not project.repository_url
            or attempt.target_branch != project.default_branch
            or approval.target_branch != attempt.target_branch
        ):
            raise RecoveryAttemptStoreError("RECOVERY_REPOSITORY_BINDING_MISMATCH")
        commands_hash = hash_json({"commands": approval.required_test_commands})
        if commands_hash != approval.required_test_commands_sha256:
            raise RecoveryAttemptStoreError("RECOVERY_TEST_BINDING_MISMATCH")
        expected = approval_binding_hash(
            recovery_assessment_id=str(assessment.id),
            rollback_record_id=str(rollback.id),
            repository_id=str(project.id),
            target_branch=approval.target_branch,
            strategy=approval.recovery_strategy,
            expected_remote_head_sha=approval.expected_remote_head_sha,
            integration_commit_sha=approval.integration_commit_sha,
            required_test_commands_sha256=commands_hash,
            assessment_policy_version=assessment.assessment_policy_version,
            recovery_policy_version=rollback.recovery_policy_version,
        )
        if (
            expected != approval.approval_binding_sha256
            or attempt.expected_remote_head_sha != approval.expected_remote_head_sha
            or attempt.integration_commit_sha != rollback.integration_commit_sha
        ):
            raise RecoveryAttemptStoreError("RECOVERY_APPROVAL_BINDING_MISMATCH")

    @staticmethod
    def _commands(approval: RollbackApprovalModel) -> tuple[ApprovedTestCommand, ...]:
        result = []
        for item in approval.required_test_commands:
            argv = item.get("argv")
            if (
                not isinstance(argv, list)
                or not argv
                or not all(isinstance(value, str) for value in argv)
            ):
                raise RecoveryAttemptStoreError("INVALID_RECOVERY_TEST_COMMAND")
            result.append(
                ApprovedTestCommand(
                    tuple(argv),
                    int(item.get("timeout_seconds", 300)),
                    dict(item.get("environment", {})),
                )
            )
        return tuple(result)

    @staticmethod
    def _scope(rollback: RollbackRecordModel) -> ExecutionScope:
        paths = tuple(str(item["path"]) for item in rollback.changed_paths)
        return ExecutionScope(allowed_paths=paths, forbidden_paths=DEFAULT_FORBIDDEN_PATHS)

    async def _existing_candidate(self, attempt_id: uuid.UUID) -> CandidateCommit | None:
        value = await self._session.scalar(
            select(RecoveryCommitModel).where(RecoveryCommitModel.recovery_attempt_id == attempt_id)
        )
        if value is None:
            return None
        identity = f"{value.author_name} <{value.author_email}>"
        return CandidateCommit(
            value.commit_sha, value.tree_sha, value.parent_commit_sha, "", identity, identity
        )

    @staticmethod
    def _commit_message(attempt: RecoveryAttemptModel, assessment: RecoveryAssessmentModel) -> str:
        return (
            f"Revert controlled integration {attempt.integration_commit_sha}\n\n"
            f"Recovery assessment: {assessment.id}\n"
            f"Rollback approval: {attempt.rollback_approval_id}\n\n"
            "Generated by Controlled Recovery Worker"
        )

    @staticmethod
    def _artifact(project_id: uuid.UUID, artifact_type: str, content: str) -> ArtifactModel:
        return ArtifactModel(
            id=uuid.uuid4(),
            project_id=project_id,
            run_id=None,
            artifact_type=artifact_type,
            media_type="text/plain",
            content=content,
            content_hash=hash_text(content),
        )

    async def _audit(
        self, attempt: RecoveryAttemptModel, event: str, actor: str, payload: dict[str, Any]
    ) -> None:
        await AuditWriter(self._session).append_project_event(
            project_id=attempt.project_id,
            event_type=event,
            actor_type="recovery_worker",
            actor_id=actor,
            payload={
                "attempt_id": str(attempt.id),
                "correlation_id": str(attempt.correlation_id),
                **payload,
            },
        )

    @staticmethod
    def _identity(value: str) -> tuple[str, str]:
        if " <" in value and value.endswith(">"):
            name, email = value[:-1].split(" <", 1)
            return name, email
        return value, "recovery-worker@internal.invalid"
