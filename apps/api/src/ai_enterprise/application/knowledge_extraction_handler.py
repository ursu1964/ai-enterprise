import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from ai_enterprise.infrastructure.knowledge.models import KnowledgeSourceModel


class ExtractedKnowledgeCandidate(BaseModel):
    candidate_type: str
    title: str = Field(min_length=5, max_length=200)
    statement: str = Field(min_length=10, max_length=4000)
    scope_type: str
    scope_id: uuid.UUID
    evidence_locators: list[dict[str, Any]] = Field(min_length=1)
    confidence_band: str
    classification: str


class ExtractionOutput(BaseModel):
    candidates: list[ExtractedKnowledgeCandidate] = Field(max_length=10)


class GovernedExtractionRuntime(Protocol):
    async def execute(
        self,
        *,
        workflow_type: str,
        source_id: uuid.UUID,
        source_hash: str,
        requested_capability: str,
        allowed_candidate_types: tuple[str, ...],
    ) -> tuple[uuid.UUID, uuid.UUID, dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class ExtractionCommand:
    source_id: uuid.UUID
    allowed_candidate_types: tuple[str, ...]


class ExtractKnowledgeCandidatesHandler:
    """Invokes only the governed runtime, then persists schema-validated candidates."""

    def __init__(
        self,
        *,
        source_loader: Callable[[uuid.UUID], Awaitable[KnowledgeSourceModel | None]],
        runtime: GovernedExtractionRuntime,
        persister: Callable[
            [KnowledgeSourceModel, uuid.UUID, uuid.UUID, list[dict[str, Any]]],
            Awaitable[tuple[uuid.UUID, ...]],
        ],
    ) -> None:
        self.source_loader = source_loader
        self.runtime = runtime
        self.persister = persister

    async def handle(self, command: ExtractionCommand) -> tuple[uuid.UUID, ...]:
        source = await self.source_loader(command.source_id)
        if source is None:
            raise LookupError("KNOW-001 SOURCE_NOT_FOUND")
        runtime_session_id, skill_version_id, raw_output = await self.runtime.execute(
            workflow_type="knowledge-extraction",
            source_id=source.id,
            source_hash=source.source_hash,
            requested_capability="extract-knowledge-candidates",
            allowed_candidate_types=command.allowed_candidate_types,
        )
        output = ExtractionOutput.model_validate(raw_output)
        if any(
            item.candidate_type not in command.allowed_candidate_types for item in output.candidates
        ):
            raise ValueError("KNOW-007 UNSUPPORTED_CLAIM")
        return await self.persister(
            source,
            runtime_session_id,
            skill_version_id,
            [item.model_dump() for item in output.candidates],
        )
