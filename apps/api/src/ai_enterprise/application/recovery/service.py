import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.enums import JobType
from ai_enterprise.domain.recovery.bindings import (
    approval_binding_hash,
    assessment_binding_hash,
    hash_commands,
)
from ai_enterprise.domain.recovery.entities import ChangedPath, RemoteState, RollbackRecord
from ai_enterprise.domain.recovery.enums import RecoveryAttemptStatus, RollbackApprovalStatus
from ai_enterprise.domain.recovery.exceptions import (
    RecoveryAssessmentStale,
    RollbackApprovalHumanRequired,
    RollbackApprovalNotActive,
    RollbackRecordNotFound,
)
from ai_enterprise.domain.recovery.policies import RecoveryStrategyPolicy
from ai_enterprise.infrastructure.database.models import (
    AuditEventModel,
    IntegrationAttemptModel,
    ProjectModel,
    RecoveryAssessmentModel,
    RecoveryAttemptModel,
    RecoveryIncidentModel,
    RollbackApprovalModel,
    RollbackRecordModel,
)
from ai_enterprise.infrastructure.jobs.repository import JobRepository
from ai_enterprise.infrastructure.recovery.git_runner import IsolatedGitRunner


class RecoveryNotFoundError(Exception):
    pass


class RecoveryControlPlaneService:
    ASSESSMENT_POLICY_VERSION = RecoveryStrategyPolicy.POLICY_VERSION
    RECOVERY_POLICY_VERSION = "recovery-v1"

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def assess_from_trusted_checkout(
        self,
        *,
        incident_id: uuid.UUID,
        actor_subject: str,
        actor_type: str,
        actor_role: str,
    ) -> RecoveryAssessmentModel:
        incident = await self._session.get(RecoveryIncidentModel, incident_id)
        if incident is None:
            raise RecoveryNotFoundError("Recovery incident not found")
        rollback = await self._session.get(RollbackRecordModel, incident.rollback_record_id)
        project = await self._session.get(ProjectModel, incident.project_id)
        if rollback is None or project is None:
            raise RollbackRecordNotFound("Recovery repository evidence is unavailable")
        if not project.repository_url:
            raise RecoveryAssessmentStale("Authoritative repository URL is unavailable")
        runner = IsolatedGitRunner()
        repository = Path(project.repository_path).resolve()
        remote_result = runner.run(
            repository,
            "ls-remote",
            "--exit-code",
            project.repository_url,
            f"refs/heads/{rollback.target_branch}",
        )
        remote_fields = remote_result.stdout.split()
        if remote_result.returncode != 0 or len(remote_fields) != 2:
            raise RecoveryAssessmentStale("Cannot inspect the authoritative branch head")
        head = remote_fields[0]
        tree_result = runner.run(repository, "rev-parse", f"{head}^{{tree}}")
        ancestry = runner.run(
            repository, "merge-base", "--is-ancestor", rollback.integration_commit_sha, head
        )
        if tree_result.returncode != 0 or ancestry.returncode not in (0, 1):
            raise RecoveryAssessmentStale("Cannot verify trusted repository state")
        return await self.assess(
            incident_id=incident_id,
            actor_subject=actor_subject,
            actor_type=actor_type,
            actor_role=actor_role,
            remote_head_sha=head,
            remote_tree_sha=tree_result.stdout.strip(),
            integration_commit_is_ancestor=ancestry.returncode == 0,
        )

    async def create_incident(
        self,
        *,
        integration_attempt_id: uuid.UUID,
        actor_subject: str,
        actor_type: str,
        actor_role: str,
        severity: str,
        summary: str,
        details: str,
        affected_environment: str,
        detected_at: datetime,
        external_reference: str | None,
    ) -> RecoveryIncidentModel:
        self._require_human_role(actor_type, actor_role, "incident_reporter")
        attempt = await self._session.get(IntegrationAttemptModel, integration_attempt_id)
        if attempt is None:
            raise RecoveryNotFoundError("Integration attempt not found")
        rollback = await self._session.scalar(
            select(RollbackRecordModel).where(
                RollbackRecordModel.integration_attempt_id == integration_attempt_id
            )
        )
        if rollback is None:
            raise RollbackRecordNotFound("Verified rollback metadata is required")
        incident = RecoveryIncidentModel(
            id=uuid.uuid4(),
            integration_attempt_id=attempt.id,
            rollback_record_id=rollback.id,
            project_id=attempt.project_id,
            reported_by=actor_subject,
            severity=severity,
            summary=summary,
            details=details,
            affected_environment=affected_environment,
            detected_at=detected_at,
            external_reference=external_reference,
        )
        self._session.add(incident)
        self._audit(
            attempt.project_id,
            "recovery.incident_created",
            actor_type,
            actor_subject,
            {
                "incident_id": str(incident.id),
                "integration_attempt_id": str(attempt.id),
                "rollback_record_id": str(rollback.id),
                "severity": severity,
            },
        )
        await self._commit_refresh(incident)
        return incident

    async def assess(
        self,
        *,
        incident_id: uuid.UUID,
        actor_subject: str,
        actor_type: str,
        actor_role: str,
        remote_head_sha: str,
        remote_tree_sha: str,
        integration_commit_is_ancestor: bool,
    ) -> RecoveryAssessmentModel:
        self._require_human_role(actor_type, actor_role, "recovery_assessor")
        incident = await self._session.get(RecoveryIncidentModel, incident_id)
        if incident is None:
            raise RecoveryNotFoundError("Recovery incident not found")
        rollback = await self._session.get(RollbackRecordModel, incident.rollback_record_id)
        if rollback is None:
            raise RollbackRecordNotFound("Rollback record not found")
        decision = RecoveryStrategyPolicy().determine(
            rollback_record=self._to_domain(rollback),
            remote_state=RemoteState(
                remote_head_sha, remote_tree_sha, integration_commit_is_ancestor
            ),
        )
        commands = tuple(rollback.approved_test_commands)
        commands_hash = hash_commands(commands)
        assessment = RecoveryAssessmentModel(
            id=uuid.uuid4(),
            incident_id=incident.id,
            rollback_record_id=rollback.id,
            status=decision.status,
            recommended_strategy=decision.strategy,
            risk_level=decision.risk_level,
            expected_remote_head_sha=remote_head_sha,
            integration_commit_is_ancestor=integration_commit_is_ancestor,
            direct_revert_possible=decision.direct_revert_possible,
            database_coordination_required=decision.database_coordination_required,
            external_coordination_required=decision.external_coordination_required,
            required_test_commands=list(commands),
            findings=[
                {"code": item.code, "severity": item.severity, "message": item.message}
                for item in decision.findings
            ],
            assessment_policy_version=self.ASSESSMENT_POLICY_VERSION,
            assessment_binding_sha256=assessment_binding_hash(
                incident_id=str(incident.id),
                rollback_record_id=str(rollback.id),
                strategy=decision.strategy,
                expected_remote_head_sha=remote_head_sha,
                required_test_commands_sha256=commands_hash,
                assessment_policy_version=self.ASSESSMENT_POLICY_VERSION,
            ),
            assessed_by=actor_subject,
            assessed_at=datetime.now(UTC),
        )
        self._session.add(assessment)
        self._audit(
            incident.project_id,
            "recovery.assessment_completed",
            actor_type,
            actor_subject,
            {
                "assessment_id": str(assessment.id),
                "incident_id": str(incident.id),
                "strategy": decision.strategy,
                "binding_sha256": assessment.assessment_binding_sha256,
            },
        )
        await self._commit_refresh(assessment)
        return assessment

    async def approve(
        self,
        *,
        assessment_id: uuid.UUID,
        actor_subject: str,
        actor_type: str,
        actor_role: str,
        reason: str,
    ) -> RollbackApprovalModel:
        self._require_human_role(actor_type, actor_role, "rollback_approver")
        assessment = await self._session.scalar(
            select(RecoveryAssessmentModel)
            .where(RecoveryAssessmentModel.id == assessment_id)
            .with_for_update()
        )
        if assessment is None:
            raise RecoveryNotFoundError("Recovery assessment not found")
        if not assessment.direct_revert_possible:
            raise RecoveryAssessmentStale("Assessment does not authorize an automated revert")
        incident = await self._session.get(RecoveryIncidentModel, assessment.incident_id)
        rollback = await self._session.get(RollbackRecordModel, assessment.rollback_record_id)
        if incident is None or rollback is None:
            raise RecoveryAssessmentStale("Assessment dependencies are missing")
        commands = tuple(assessment.required_test_commands)
        commands_hash = hash_commands(commands)
        now = datetime.now(UTC)
        approval = RollbackApprovalModel(
            id=uuid.uuid4(),
            recovery_assessment_id=assessment.id,
            rollback_record_id=rollback.id,
            project_id=incident.project_id,
            target_branch=rollback.target_branch,
            recovery_strategy=assessment.recommended_strategy,
            expected_remote_head_sha=assessment.expected_remote_head_sha,
            integration_commit_sha=rollback.integration_commit_sha,
            required_test_commands=list(commands),
            required_test_commands_sha256=commands_hash,
            approval_binding_sha256=approval_binding_hash(
                recovery_assessment_id=str(assessment.id),
                rollback_record_id=str(rollback.id),
                repository_id=str(incident.project_id),
                target_branch=rollback.target_branch,
                strategy=assessment.recommended_strategy,
                expected_remote_head_sha=assessment.expected_remote_head_sha,
                integration_commit_sha=rollback.integration_commit_sha,
                required_test_commands_sha256=commands_hash,
                assessment_policy_version=assessment.assessment_policy_version,
                recovery_policy_version=rollback.recovery_policy_version,
            ),
            status=RollbackApprovalStatus.ACTIVE,
            approver_subject=actor_subject,
            reason=reason,
            approved_at=now,
            expires_at=now + timedelta(hours=1),
        )
        self._session.add(approval)
        self._audit(
            incident.project_id,
            "recovery.rollback_approval_granted",
            actor_type,
            actor_subject,
            {
                "approval_id": str(approval.id),
                "assessment_id": str(assessment.id),
                "expected_remote_head_sha": approval.expected_remote_head_sha,
                "binding_sha256": approval.approval_binding_sha256,
            },
        )
        await self._commit_refresh(approval)
        return approval

    async def create_attempt(
        self, *, approval_id: uuid.UUID, actor_subject: str, actor_type: str, actor_role: str
    ) -> RecoveryAttemptModel:
        self._require_human_role(actor_type, actor_role, "recovery_operator")
        approval = await self._session.scalar(
            select(RollbackApprovalModel)
            .where(RollbackApprovalModel.id == approval_id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if approval is None:
            raise RecoveryNotFoundError("Rollback approval not found")
        if approval.status != RollbackApprovalStatus.ACTIVE or (
            approval.expires_at is not None and approval.expires_at <= now
        ):
            raise RollbackApprovalNotActive("Rollback approval is not active")
        attempt = RecoveryAttemptModel(
            id=uuid.uuid4(),
            rollback_approval_id=approval.id,
            recovery_assessment_id=approval.recovery_assessment_id,
            rollback_record_id=approval.rollback_record_id,
            project_id=approval.project_id,
            target_branch=approval.target_branch,
            expected_remote_head_sha=approval.expected_remote_head_sha,
            integration_commit_sha=approval.integration_commit_sha,
            recovery_strategy=approval.recovery_strategy,
            status=RecoveryAttemptStatus.QUEUED,
            correlation_id=uuid.uuid4(),
        )
        self._session.add(attempt)
        approval.status = RollbackApprovalStatus.CONSUMED
        approval.consumed_at = now
        self._audit(
            approval.project_id,
            "recovery.attempt_created",
            actor_type,
            actor_subject,
            {
                "attempt_id": str(attempt.id),
                "approval_id": str(approval.id),
                "correlation_id": str(attempt.correlation_id),
            },
        )
        await JobRepository(self._session).enqueue(
            project_id=approval.project_id,
            run_id=None,
            job_type=JobType.RECOVER_INTEGRATION,
            payload={
                "recovery_attempt_id": str(attempt.id),
                "correlation_id": str(attempt.correlation_id),
            },
            priority=40,
            max_attempts=1,
        )
        await self._commit_refresh(attempt)
        return attempt

    @staticmethod
    def _require_human_role(actor_type: str, actor_role: str, required_role: str) -> None:
        if actor_type != "human" or actor_role != required_role:
            raise RollbackApprovalHumanRequired(f"The human {required_role} role is required")

    def _audit(
        self,
        project_id: uuid.UUID,
        event: str,
        actor_type: str,
        actor_id: str,
        payload: dict[str, object],
    ) -> None:
        self._session.add(
            AuditEventModel(
                id=uuid.uuid4(),
                project_id=project_id,
                event_type=event,
                actor_type=actor_type,
                actor_id=actor_id,
                payload=payload,
            )
        )

    async def _commit_refresh(self, model: object) -> None:
        await self._session.commit()
        await self._session.refresh(model)

    @staticmethod
    def _to_domain(model: RollbackRecordModel) -> RollbackRecord:
        return RollbackRecord(
            id=model.id,
            integration_attempt_id=model.integration_attempt_id,
            integration_commit_id=model.integration_commit_id,
            repository_id=model.project_id,
            target_branch=model.target_branch,
            integration_commit_sha=model.integration_commit_sha,
            parent_commit_sha=model.parent_commit_sha,
            integration_tree_sha=model.integration_tree_sha,
            parent_tree_sha=model.parent_tree_sha,
            changed_paths=tuple(ChangedPath(**item) for item in model.changed_paths),
            changed_paths_sha256=model.changed_paths_sha256,
            inverse_diff_artifact_id=model.inverse_diff_artifact_id,
            inverse_diff_sha256=model.inverse_diff_sha256,
            original_patch_sha256=model.original_patch_sha256,
            approved_test_commands=tuple(model.approved_test_commands),
            approved_test_commands_sha256=model.approved_test_commands_sha256,
            external_side_effects_declared=model.external_side_effects_declared,
            database_change_detected=model.database_change_detected,
            deployment_change_detected=model.deployment_change_detected,
            recovery_policy_version=model.recovery_policy_version,
            rollback_binding_sha256=model.rollback_binding_sha256,
            created_at=model.created_at,
        )
