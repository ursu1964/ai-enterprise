from dataclasses import dataclass
from typing import Protocol

from ai_enterprise.domain.workflow.context import WorkflowContext
from ai_enterprise.domain.workflow.enums import WorkflowState, WorkflowStepName


@dataclass(frozen=True, slots=True)
class StepResult:
    context: WorkflowContext
    next_state: WorkflowState
    reason: str


class WorkflowStep(Protocol):
    name: WorkflowStepName
    version: str

    async def validate(self, context: WorkflowContext) -> None: ...
    async def execute(self, context: WorkflowContext) -> StepResult: ...
    async def rollback(self, context: WorkflowContext) -> WorkflowContext: ...
    def next(self, context: WorkflowContext) -> WorkflowState: ...
