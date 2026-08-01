import uuid

import pytest
from pydantic import ValidationError

from ai_enterprise.application.workflow.completeness import verify_completeness
from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.contracts import RequirementsContract
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName
from ai_enterprise.domain.workflow.state_machine import (
    LEGAL_TRANSITIONS,
    IllegalWorkflowTransition,
    require_transition,
)
from ai_enterprise.domain.workflow.step import StepResult, WorkflowStep


def context() -> WorkflowContext:
    return WorkflowContext(
        workflow_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        current_state=WorkflowState.PROJECT_CREATED,
        correlation_id=uuid.uuid4(),
        actor_id="tester",
    )


def test_state_machine_accepts_documented_graph_and_rejects_shortcuts() -> None:
    for previous, destinations in LEGAL_TRANSITIONS.items():
        for destination in destinations:
            require_transition(previous, destination)

    with pytest.raises(IllegalWorkflowTransition):
        require_transition(WorkflowState.PROJECT_CREATED, WorkflowState.INTEGRATING)


def test_context_updates_are_immutable_and_hash_bound() -> None:
    original = context()
    evolved = original.evolved(current_state=WorkflowState.REQUIREMENTS_RUNNING)

    assert original.current_state is WorkflowState.PROJECT_CREATED
    assert evolved.current_state is WorkflowState.REQUIREMENTS_RUNNING
    assert evolved.content_hash() != original.content_hash()
    with pytest.raises(ValidationError):
        original.current_state = WorkflowState.FAILED  # type: ignore[misc]


def test_versioned_contract_rejects_arbitrary_output() -> None:
    with pytest.raises(ValidationError):
        RequirementsContract.model_validate(
            {"schema_version": "1.0", "sections": ["Goals"], "unexpected": "value"}
        )


def test_completeness_fails_closed_with_actionable_missing_evidence() -> None:
    result = verify_completeness(context())

    assert not result.complete
    assert "artifact:manifest" in result.missing
    assert "approval:integration" in result.missing
    assert "commit" in result.missing


def test_cancel_transition_is_available_from_non_terminal_states() -> None:
    require_transition(WorkflowState.PATCH_REVIEW_RUNNING, WorkflowState.CANCELLING)
    require_transition(WorkflowState.CANCELLING, WorkflowState.CANCELLED)
    with pytest.raises(IllegalWorkflowTransition):
        require_transition(WorkflowState.COMPLETED, WorkflowState.CANCELLING)


class FakeRequirementsStep:
    name = WorkflowStepName.REQUIREMENTS
    version = "1.0"

    async def validate(self, context: WorkflowContext) -> None:
        assert context.current_state is WorkflowState.PROJECT_CREATED

    async def execute(self, context: WorkflowContext) -> StepResult:
        return StepResult(
            context=context, next_state=WorkflowState.REQUIREMENTS_RUNNING, reason="fake"
        )

    async def rollback(self, context: WorkflowContext) -> WorkflowContext:
        return context

    def next(self, context: WorkflowContext) -> WorkflowState:
        return WorkflowState.REQUIREMENTS_RUNNING


@pytest.mark.asyncio
async def test_step_adapter_contract_with_external_runtime_replaced_by_fake() -> None:
    adapter: WorkflowStep = FakeRequirementsStep()
    current = context()
    await adapter.validate(current)
    result = await adapter.execute(current)
    require_transition(current.current_state, result.next_state)
    assert adapter.next(current) is result.next_state
    assert await adapter.rollback(current) == current
