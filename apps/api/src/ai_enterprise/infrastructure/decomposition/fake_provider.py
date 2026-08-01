from collections import deque

from pydantic import ValidationError

from ai_enterprise.domain.decomposition.schema import CandidateDecomposition

from .contracts import DecompositionCrewContext


class ScriptedDecompositionProvider:
    name = "scripted"
    model_name = "deterministic-fake"

    def __init__(self, outputs: list[dict[str, object] | str | Exception]) -> None:
        self._outputs = deque(outputs)
        self.calls: list[DecompositionCrewContext] = []

    async def decompose(self, context: DecompositionCrewContext) -> CandidateDecomposition:
        self.calls.append(context)
        if not self._outputs:
            raise AssertionError("Unexpected decomposition provider invocation")
        value = self._outputs.popleft()
        if isinstance(value, Exception):
            raise value
        try:
            if isinstance(value, str):
                return CandidateDecomposition.model_validate_json(value)
            return CandidateDecomposition.model_validate(value)
        except ValidationError:
            raise
