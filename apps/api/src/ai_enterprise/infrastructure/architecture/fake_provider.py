from collections import deque

from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureExecutionContext,
    ModelInvocationResult,
)


class ScriptedArchitectureProvider:
    name = "scripted"
    model_name = "deterministic-fake"

    def __init__(self, outputs: list[str | Exception]) -> None:
        self._outputs = deque(outputs)
        self.operations: list[str] = []

    def _next(self, operation: str) -> ModelInvocationResult:
        self.operations.append(operation)
        if not self._outputs:
            raise AssertionError("Unexpected architecture provider invocation")
        result = self._outputs.popleft()
        if isinstance(result, Exception):
            raise result
        return ModelInvocationResult(result, self.model_name, "fake-prompt-bundle", {})

    async def generate(self, context: ArchitectureExecutionContext) -> ModelInvocationResult:
        return self._next("generate")

    async def repair(
        self,
        context: ArchitectureExecutionContext,
        *,
        invalid_output: str,
        validation_report: tuple[dict[str, str], ...],
    ) -> ModelInvocationResult:
        return self._next("repair")
