from enum import StrEnum


class WorkflowState(StrEnum):
    PROJECT_CREATED = "project_created"
    REQUIREMENTS_RUNNING = "requirements_running"
    WAITING_REQUIREMENTS_APPROVAL = "waiting_requirements_approval"
    ARCHITECTURE_RUNNING = "architecture_running"
    WAITING_ARCHITECTURE_APPROVAL = "waiting_architecture_approval"
    PLANNING_RUNNING = "planning_running"
    WAITING_WORK_PACKAGE_APPROVAL = "waiting_work_package_approval"
    EXECUTION_RUNNING = "execution_running"
    PATCH_REVIEW_RUNNING = "patch_review_running"
    WAITING_INTEGRATION_APPROVAL = "waiting_integration_approval"
    INTEGRATING = "integrating"
    COMPLETED = "completed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    FAILED = "failed"
    MANUAL_INTERVENTION = "manual_intervention"


class WorkflowStepName(StrEnum):
    REQUIREMENTS = "requirements"
    ARCHITECTURE = "architecture"
    PLANNING = "planning"
    EXECUTION = "execution"
    REVIEW = "review"
    INTEGRATION = "integration"
    COMPLETENESS = "completeness"


class WorkflowEventName(StrEnum):
    STARTED = "workflow.started"
    RELINKED = "workflow.relinked"
    TRANSITIONED = "workflow.transitioned"
    CANCELLED = "workflow.cancelled"
    FAILED = "workflow.failed"
    COMPLETED = "workflow.completed"


TERMINAL_STATES = frozenset(
    {WorkflowState.COMPLETED, WorkflowState.CANCELLED, WorkflowState.FAILED}
)
