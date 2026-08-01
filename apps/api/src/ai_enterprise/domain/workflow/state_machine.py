from ai_enterprise.domain.workflow.enums import WorkflowState


class IllegalWorkflowTransition(ValueError):
    pass


LEGAL_TRANSITIONS: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.PROJECT_CREATED: frozenset({WorkflowState.REQUIREMENTS_RUNNING}),
    WorkflowState.REQUIREMENTS_RUNNING: frozenset(
        {WorkflowState.WAITING_REQUIREMENTS_APPROVAL, WorkflowState.FAILED}
    ),
    WorkflowState.WAITING_REQUIREMENTS_APPROVAL: frozenset(
        {WorkflowState.ARCHITECTURE_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.ARCHITECTURE_RUNNING: frozenset(
        {WorkflowState.WAITING_ARCHITECTURE_APPROVAL, WorkflowState.FAILED}
    ),
    WorkflowState.WAITING_ARCHITECTURE_APPROVAL: frozenset(
        {WorkflowState.PLANNING_RUNNING, WorkflowState.FAILED}
    ),
    WorkflowState.PLANNING_RUNNING: frozenset(
        {WorkflowState.WAITING_WORK_PACKAGE_APPROVAL, WorkflowState.FAILED}
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


def require_transition(previous: WorkflowState, current: WorkflowState) -> None:
    if current in {WorkflowState.CANCELLING, WorkflowState.FAILED} and previous not in {
        WorkflowState.COMPLETED,
        WorkflowState.CANCELLED,
        WorkflowState.FAILED,
    }:
        return
    if previous is WorkflowState.CANCELLING and current is WorkflowState.CANCELLED:
        return
    if current not in LEGAL_TRANSITIONS.get(previous, frozenset()):
        raise IllegalWorkflowTransition(f"Illegal workflow transition: {previous} -> {current}")
