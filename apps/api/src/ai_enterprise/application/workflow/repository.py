import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName
from ai_enterprise.domain.workflow.state_machine import require_transition
from ai_enterprise.infrastructure.database.workflow_models import (
    WorkflowCheckpointModel,
    WorkflowContextModel,
    WorkflowInstanceModel,
    WorkflowTransitionModel,
)
from ai_enterprise.observability import increment_metric


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, workflow_id: uuid.UUID, *, lock: bool = False) -> WorkflowInstanceModel:
        query = select(WorkflowInstanceModel).where(WorkflowInstanceModel.id == workflow_id)
        if lock:
            query = query.with_for_update()
        workflow = await self.session.scalar(query)
        if workflow is None:
            raise WorkflowNotFoundError(str(workflow_id))
        return workflow

    async def context(self, workflow: WorkflowInstanceModel) -> WorkflowContext:
        row = await self.session.scalar(
            select(WorkflowContextModel).where(
                WorkflowContextModel.workflow_id == workflow.id,
                WorkflowContextModel.version == workflow.context_version,
            )
        )
        if row is None:
            raise RuntimeError("Workflow context is missing")
        context = WorkflowContext.model_validate(row.context)
        if context.content_hash() != row.context_hash:
            raise RuntimeError("Workflow context integrity check failed")
        return context

    async def append_transition(
        self,
        *,
        workflow: WorkflowInstanceModel,
        context: WorkflowContext,
        next_state: WorkflowState,
        step: WorkflowStepName | None,
        actor_type: str,
        actor_id: str,
        reason: str,
        checkpoint: bool = True,
    ) -> WorkflowContext:
        previous = WorkflowState(workflow.state)
        require_transition(previous, next_state)
        sequence = (
            int(
                await self.session.scalar(
                    select(func.count())
                    .select_from(WorkflowTransitionModel)
                    .where(WorkflowTransitionModel.workflow_id == workflow.id)
                )
                or 0
            )
            + 1
        )
        version = workflow.context_version + 1
        evolved = context.evolved(current_state=next_state)
        context_hash = evolved.content_hash()
        self.session.add_all(
            [
                WorkflowContextModel(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    version=version,
                    state=next_state,
                    context=evolved.model_dump(mode="json"),
                    context_hash=context_hash,
                ),
                WorkflowTransitionModel(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    sequence=sequence,
                    previous_state=previous,
                    current_state=next_state,
                    step=step,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    reason=reason,
                    workflow_version=workflow.workflow_version,
                    correlation_id=workflow.correlation_id,
                ),
            ]
        )
        if checkpoint and step is not None:
            self.session.add(
                WorkflowCheckpointModel(
                    id=uuid.uuid4(),
                    workflow_id=workflow.id,
                    step=step,
                    step_version="1.0",
                    context_version=version,
                    context_hash=context_hash,
                    retry_count=0,
                    artifact_ids=[str(item) for item in evolved.artifact_ids.values()],
                    open_resources=[],
                    running_commands=[],
                    status="succeeded",
                )
            )
        workflow.state = next_state
        workflow.current_step = step
        workflow.context_version = version
        workflow.optimistic_version += 1
        if next_state in {WorkflowState.COMPLETED, WorkflowState.CANCELLED}:
            workflow.completed_at = datetime.now(UTC)
        await self.session.flush()
        increment_metric("workflow_transitions_total")
        if next_state is WorkflowState.COMPLETED:
            increment_metric("workflow_completed_total")
        if next_state is WorkflowState.FAILED:
            increment_metric("workflow_failed_total")
        return evolved
