from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArchitectureExecutionContext:
    run_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    project_description: str
    project_manifest_checksum: str
    requirements_artifact_id: uuid.UUID
    requirements_version: int
    requirements_checksum: str
    requirements_markdown: str
    approved_requirement_ids: frozenset[str]
    schema_version: str
    crew_version: str
    deadline_at: datetime
    attempt_number_offset: int = 0


@dataclass(frozen=True, slots=True)
class ModelInvocationResult:
    raw_output: str
    model_name: str
    prompt_bundle_hash: str
    token_usage: dict[str, int]


class ArchitectureModelProvider(Protocol):
    name: str
    model_name: str

    async def generate(self, context: ArchitectureExecutionContext) -> ModelInvocationResult: ...

    async def repair(
        self,
        context: ArchitectureExecutionContext,
        *,
        invalid_output: str,
        validation_report: tuple[dict[str, str], ...],
    ) -> ModelInvocationResult: ...


@dataclass(frozen=True, slots=True)
class AttemptEvidence:
    run_id: uuid.UUID
    attempt_number: int
    operation: str
    status: str
    model_name: str
    provider_name: str
    prompt_bundle_hash: str
    raw_output_hash: str | None
    raw_output: str | None
    token_usage: dict[str, int]
    validation_report: tuple[dict[str, str], ...]
    started_at: datetime
    completed_at: datetime
    failure_code: str | None = None


class ArchitectureAttemptEvidenceWriter(Protocol):
    """Persistence port for later `architecture_execution_attempts` storage."""

    async def record(self, evidence: AttemptEvidence) -> None: ...
