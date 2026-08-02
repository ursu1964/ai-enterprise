import uuid

import pytest
from pydantic import ValidationError

from ai_enterprise.application.workflow.completeness import verify_completeness
from ai_enterprise.application.workflow.repository import WorkflowRepository
from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.contracts import RequirementsContract
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName
from ai_enterprise.domain.workflow.state_machine import (
    AUTO_APPROVAL_TRANSITIONS,
    LEGAL_TRANSITIONS,
    IllegalWorkflowTransition,
    WorkflowPhasePolicy,
    WorkflowTransitionKind,
    require_transition,
)
from ai_enterprise.domain.workflow.step import StepResult, WorkflowStep
from ai_enterprise.infrastructure.database.workflow_models import WorkflowTransitionModel


class Scalars:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class WorkflowAppendSession:
    def __init__(self) -> None:
        self.added: list[object] = []

    async def scalar(self, statement: object) -> int:
        return 0

    def add(self, row: object) -> None:
        self.added.append(row)

    def add_all(self, rows: list[object]) -> None:
        self.added.extend(rows)

    async def flush(self) -> None:
        return None


def context() -> WorkflowContext:
    return WorkflowContext(
        workflow_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        current_state=WorkflowState.PROJECT_CREATED,
        correlation_id=uuid.uuid4(),
        actor_id="tester",
    )


def workflow_instance(state: WorkflowState):
    from ai_enterprise.infrastructure.database.workflow_models import WorkflowInstanceModel

    return WorkflowInstanceModel(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        definition_name="vertical_slice",
        workflow_version="1.0",
        state=state,
        current_step=None,
        context_version=1,
        correlation_id=uuid.uuid4(),
        optimistic_version=1,
    )


def test_state_machine_accepts_documented_graph_and_rejects_shortcuts() -> None:
    for previous, destinations in LEGAL_TRANSITIONS.items():
        for destination in destinations:
            require_transition(previous, destination)

    with pytest.raises(IllegalWorkflowTransition):
        require_transition(WorkflowState.PROJECT_CREATED, WorkflowState.INTEGRATING)


def test_auto_approval_skips_are_explicit_policy_decisions() -> None:
    policy = WorkflowPhasePolicy()
    expected = {
        (WorkflowState.REQUIREMENTS_RUNNING, WorkflowState.ARCHITECTURE_RUNNING),
        (WorkflowState.ARCHITECTURE_RUNNING, WorkflowState.PLANNING_RUNNING),
        (WorkflowState.PLANNING_RUNNING, WorkflowState.EXECUTION_RUNNING),
    }

    assert AUTO_APPROVAL_TRANSITIONS == expected
    for previous, current in AUTO_APPROVAL_TRANSITIONS:
        decision = policy.classify(previous, current)
        assert decision.kind is WorkflowTransitionKind.VERSIONED_AUTO_APPROVAL
        assert decision.requires_policy_evidence is True


def test_terminal_and_failure_transitions_are_classified_fail_closed() -> None:
    policy = WorkflowPhasePolicy()

    failure = policy.classify(WorkflowState.EXECUTION_RUNNING, WorkflowState.FAILED)
    cancellation = policy.classify(WorkflowState.EXECUTION_RUNNING, WorkflowState.CANCELLING)
    assert failure.kind is WorkflowTransitionKind.FAILURE
    assert cancellation.kind is WorkflowTransitionKind.CANCELLATION
    with pytest.raises(IllegalWorkflowTransition):
        policy.classify(WorkflowState.COMPLETED, WorkflowState.CANCELLING)


@pytest.mark.asyncio
async def test_repository_persists_auto_approval_policy_evidence() -> None:
    session = WorkflowAppendSession()
    workflow = workflow_instance(WorkflowState.REQUIREMENTS_RUNNING)

    await WorkflowRepository(session).append_transition(  # type: ignore[arg-type]
        workflow=workflow,
        context=context(),
        next_state=WorkflowState.ARCHITECTURE_RUNNING,
        step=WorkflowStepName.ARCHITECTURE,
        actor_type="system",
        actor_id="workflow-engine",
        reason="Auto-approved by policy.",
    )

    transition = next(item for item in session.added if isinstance(item, WorkflowTransitionModel))
    evidence = transition.policy_evidence
    assert evidence["transition_kind"] == WorkflowTransitionKind.VERSIONED_AUTO_APPROVAL
    assert evidence["requires_policy_evidence"] is True
    assert evidence["auto_approval"]["policy_version"] == "1.0"
    assert len(evidence["auto_approval"]["policy_hash"]) == 64
    assert evidence["auto_approval"]["phase"] == WorkflowStepName.ARCHITECTURE


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
