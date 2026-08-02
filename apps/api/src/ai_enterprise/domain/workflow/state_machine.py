from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName


class IllegalWorkflowTransition(ValueError):
    pass


class WorkflowTransitionKind(StrEnum):
    STANDARD = "standard"
    VERSIONED_AUTO_APPROVAL = "versioned_auto_approval"
    FAILURE = "failure"
    CANCELLATION = "cancellation"


@dataclass(frozen=True, slots=True)
class WorkflowTransitionDecision:
    previous: WorkflowState
    current: WorkflowState
    kind: WorkflowTransitionKind
    requires_policy_evidence: bool = False

    def policy_evidence(self, step: WorkflowStepName | None) -> dict[str, Any]:
        evidence = {
            "transition_kind": self.kind,
            "requires_policy_evidence": self.requires_policy_evidence,
            "from_state": self.previous,
            "to_state": self.current,
            "phase": step,
        }
        if self.kind is WorkflowTransitionKind.VERSIONED_AUTO_APPROVAL:
            policy = {
                "policy_name": "workflow-phase-auto-approval",
                "policy_version": "1.0",
                "phase": step,
                "risk_class": "low",
                "from_state": self.previous,
                "to_state": self.current,
            }
            evidence["auto_approval"] = policy | {"policy_hash": hash_json(policy)}
        return evidence


AUTO_APPROVAL_TRANSITIONS: frozenset[tuple[WorkflowState, WorkflowState]] = frozenset(
    {
        (WorkflowState.REQUIREMENTS_RUNNING, WorkflowState.ARCHITECTURE_RUNNING),
        (WorkflowState.ARCHITECTURE_RUNNING, WorkflowState.PLANNING_RUNNING),
        (WorkflowState.PLANNING_RUNNING, WorkflowState.EXECUTION_RUNNING),
    }
)


LEGAL_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.PROJECT_CREATED: frozenset({WorkflowState.REQUIREMENTS_RUNNING}),
    WorkflowState.REQUIREMENTS_RUNNING: frozenset(
        {
            WorkflowState.WAITING_REQUIREMENTS_APPROVAL,
            WorkflowState.ARCHITECTURE_RUNNING,
            WorkflowState.FAILED,
        }
    ),
    WorkflowState.WAITING_REQUIREMENTS_APPROVAL: frozenset(
        {WorkflowState.ARCHITECTURE_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.ARCHITECTURE_RUNNING: frozenset(
        {
            WorkflowState.WAITING_ARCHITECTURE_APPROVAL,
            WorkflowState.PLANNING_RUNNING,
            WorkflowState.FAILED,
        }
    ),
    WorkflowState.WAITING_ARCHITECTURE_APPROVAL: frozenset(
        {WorkflowState.PLANNING_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.PLANNING_RUNNING: frozenset(
        {
            WorkflowState.WAITING_WORK_PACKAGE_APPROVAL,
            WorkflowState.EXECUTION_RUNNING,
            WorkflowState.FAILED,
        }
    ),
    WorkflowState.WAITING_WORK_PACKAGE_APPROVAL: frozenset(
        {WorkflowState.EXECUTION_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.EXECUTION_RUNNING: frozenset(
        {WorkflowState.PATCH_REVIEW_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.PATCH_REVIEW_RUNNING: frozenset(
        {WorkflowState.WAITING_INTEGRATION_APPROVAL, WorkflowState.FAILED}
    ),
    WorkflowState.WAITING_INTEGRATION_APPROVAL: frozenset(
        {WorkflowState.INTEGRATING, WorkflowState.FAILED}
    ),
    WorkflowState.INTEGRATING: frozenset(
        {WorkflowState.COMPLETED, WorkflowState.MANUAL_INTERVENTION, WorkflowState.FAILED}
    ),
    WorkflowState.MANUAL_INTERVENTION: frozenset({WorkflowState.INTEGRATING, WorkflowState.FAILED}),
}


class WorkflowPhasePolicy:
    def classify(
        self, previous: WorkflowState, current: WorkflowState
    ) -> WorkflowTransitionDecision:
        if current is WorkflowState.CANCELLING and previous not in {
            WorkflowState.COMPLETED,
            WorkflowState.CANCELLED,
            WorkflowState.FAILED,
        }:
            return WorkflowTransitionDecision(
                previous,
                current,
                WorkflowTransitionKind.CANCELLATION,
            )
        if previous is WorkflowState.CANCELLING and current is WorkflowState.CANCELLED:
            return WorkflowTransitionDecision(
                previous,
                current,
                WorkflowTransitionKind.CANCELLATION,
            )
        if current is WorkflowState.FAILED and previous not in {
            WorkflowState.COMPLETED,
            WorkflowState.CANCELLED,
            WorkflowState.FAILED,
        }:
            return WorkflowTransitionDecision(previous, current, WorkflowTransitionKind.FAILURE)
        if (previous, current) in AUTO_APPROVAL_TRANSITIONS:
            return WorkflowTransitionDecision(
                previous,
                current,
                WorkflowTransitionKind.VERSIONED_AUTO_APPROVAL,
                requires_policy_evidence=True,
            )
        if current in LEGAL_TRANSITIONS.get(previous, frozenset()):
            return WorkflowTransitionDecision(previous, current, WorkflowTransitionKind.STANDARD)
        raise IllegalWorkflowTransition(f"Illegal workflow transition: {previous} -> {current}")


def require_transition(previous: WorkflowState, current: WorkflowState) -> None:
    WorkflowPhasePolicy().classify(previous, current)
