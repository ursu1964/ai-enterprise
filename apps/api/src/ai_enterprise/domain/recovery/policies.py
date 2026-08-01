from dataclasses import dataclass
from pathlib import PurePosixPath

from ai_enterprise.domain.recovery.entities import (
    RecoveryDecision,
    RecoveryFinding,
    RemoteState,
    RollbackApproval,
    RollbackRecord,
)
from ai_enterprise.domain.recovery.enums import (
    FailureClass,
    PipelineStage,
    PushReconciliation,
    RecoveryAssessmentStatus,
    RecoveryStrategy,
)
from ai_enterprise.domain.recovery.exceptions import (
    RecoveryHistoryInvalid,
    RecoveryRemoteStateChanged,
)


class RecoveryStrategyPolicy:
    POLICY_VERSION = "recovery-assessment-v1"

    def determine(
        self,
        *,
        rollback_record: RollbackRecord,
        remote_state: RemoteState,
    ) -> RecoveryDecision:
        findings: list[RecoveryFinding] = []
        if not remote_state.integration_commit_is_ancestor:
            findings.append(
                RecoveryFinding(
                    code="INTEGRATION_COMMIT_NOT_IN_HISTORY",
                    severity="critical",
                    message="The integration commit is not in protected-branch history.",
                )
            )
            return RecoveryDecision(
                strategy=RecoveryStrategy.MANUAL_RECOVERY,
                status=RecoveryAssessmentStatus.MANUAL_INTERVENTION_REQUIRED,
                risk_level="critical",
                direct_revert_possible=False,
                database_coordination_required=rollback_record.database_change_detected,
                external_coordination_required=True,
                findings=tuple(findings),
            )

        risk_signals = (
            (rollback_record.database_change_detected, "DATABASE_CHANGE_DETECTED"),
            (rollback_record.deployment_change_detected, "DEPLOYMENT_CHANGE_DETECTED"),
            (
                rollback_record.external_side_effects_declared,
                "EXTERNAL_SIDE_EFFECTS_DECLARED",
            ),
        )
        findings.extend(
            RecoveryFinding(code=code, severity="high", message=code.replace("_", " ").title())
            for present, code in risk_signals
            if present
        )
        if findings:
            return RecoveryDecision(
                strategy=RecoveryStrategy.COMPENSATING_PATCH,
                status=RecoveryAssessmentStatus.COMPENSATION_REQUIRED,
                risk_level="high",
                direct_revert_possible=False,
                database_coordination_required=rollback_record.database_change_detected,
                external_coordination_required=(
                    rollback_record.external_side_effects_declared
                    or rollback_record.deployment_change_detected
                ),
                findings=tuple(findings),
            )

        return RecoveryDecision(
            strategy=RecoveryStrategy.REVERT_COMMIT,
            status=RecoveryAssessmentStatus.REVERTIBLE,
            risk_level="medium",
            direct_revert_possible=True,
            database_coordination_required=False,
            external_coordination_required=False,
            findings=(),
        )


class RecoveryRiskClassifier:
    DATABASE_PREFIXES = ("alembic/versions/", "migrations/", "db/migrations/", "schema/")
    DEPLOYMENT_PREFIXES = ("terraform/", "helm/", "k8s/", "deploy/")
    DATABASE_TOKENS = ("DROP TABLE", "ALTER TABLE", "CREATE INDEX")

    def classify(
        self,
        *,
        changed_paths: tuple[str, ...],
        patch_text: str = "",
        external_side_effects_declared: bool = False,
    ) -> tuple[bool, bool, bool]:
        normalized = tuple(self._normalize(path) for path in changed_paths)
        database = any(
            path.startswith(self.DATABASE_PREFIXES) for path in normalized
        ) or any(token in patch_text.upper() for token in self.DATABASE_TOKENS)
        deployment = any(path.startswith(self.DEPLOYMENT_PREFIXES) for path in normalized)
        return database, deployment, external_side_effects_declared

    @staticmethod
    def _normalize(path: str) -> str:
        candidate = PurePosixPath(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            return "__unsafe_path__"
        return candidate.as_posix().lstrip("./")


class RecoveryRemoteStatePolicy:
    def verify_before_execution(
        self,
        *,
        approval: RollbackApproval,
        current_remote_head_sha: str,
        integration_commit_is_ancestor: bool,
    ) -> None:
        if current_remote_head_sha != approval.expected_remote_head_sha:
            raise RecoveryRemoteStateChanged(
                "The target branch changed after rollback approval."
            )
        if not integration_commit_is_ancestor:
            raise RecoveryHistoryInvalid(
                "The integration commit is no longer an ancestor of the protected branch."
            )


@dataclass(frozen=True, slots=True)
class RetryDecision:
    automatically_retry: bool
    requires_fresh_workspace: bool
    reconcile_remote_first: bool
    reason: str


class RecoveryRetryPolicy:
    def decide(
        self,
        *,
        stage: PipelineStage,
        failure_class: FailureClass,
        workspace_modified: bool,
        push_started: bool,
    ) -> RetryDecision:
        if push_started or stage in {
            PipelineStage.PUSH,
            PipelineStage.REMOTE_RESULT_VERIFICATION,
        }:
            return RetryDecision(False, True, True, "Remote state must be reconciled first.")
        safe_stage = stage in {
            PipelineStage.CLAIM,
            PipelineStage.ARTIFACT_READ,
            PipelineStage.SNAPSHOT,
        }
        retry = safe_stage and failure_class == FailureClass.TRANSIENT_INFRASTRUCTURE
        return RetryDecision(
            retry,
            workspace_modified,
            False,
            "Transient pre-modification failure." if retry else "Failure requires assessment.",
        )


class PushReconciliationPolicy:
    def reconcile(
        self,
        *,
        remote_head_sha: str,
        expected_commit_sha: str,
        old_head_sha: str,
    ) -> PushReconciliation:
        if remote_head_sha == expected_commit_sha:
            return PushReconciliation.PUSH_SUCCEEDED
        if remote_head_sha == old_head_sha:
            return PushReconciliation.NOT_PUSHED
        return PushReconciliation.REMOTE_DIVERGED
