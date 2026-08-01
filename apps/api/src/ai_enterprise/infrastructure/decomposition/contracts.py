from dataclasses import dataclass
from typing import Protocol

from ai_enterprise.domain.decomposition.schema import CandidateDecomposition


@dataclass(frozen=True, slots=True)
class DecompositionCrewContext:
    repository_index: dict[str, object]
    requirements_document: dict[str, object]
    architecture_document: dict[str, object]
    revision_context: str | None = None


class DecompositionCrewProvider(Protocol):
    name: str
    model_name: str

    async def decompose(self, context: DecompositionCrewContext) -> CandidateDecomposition: ...
