from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from hashlib import sha256

from ai_enterprise.domain.requirements_revision.models import RequirementsArtifactDocument

from .parser import ArtifactParseFailure, RequirementsArtifactParser


class RequirementsOutputError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RequirementsExecutionInput:
    project_name: str
    objective: str
    manifest: dict[str, object]
    source_context: dict[str, object]
    previous_artifact: dict[str, object] | None = None
    revision_cycle_number: int | None = None
    revision_feedback_summary: str | None = None
    revision_feedback: tuple[dict[str, object], ...] = ()
    revision_feedback_hash: str | None = None


@dataclass(frozen=True, slots=True)
class RequirementsExecutionResult:
    artifact: RequirementsArtifactDocument
    raw_output_hash: str
    repair_attempted: bool
    repair_succeeded: bool | None
    validation_errors: tuple[dict[str, object], ...]


class StructuredRequirementsAdapter:
    """Strict JSON adapter with exactly zero or one repair call."""

    def __init__(
        self,
        execute: Callable[[str], Awaitable[str]],
        *,
        repair: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._execute = execute
        self._repair = repair
        self._parser = RequirementsArtifactParser()

    async def run(self, value: RequirementsExecutionInput) -> RequirementsExecutionResult:
        prompt = build_revision_prompt(value)
        raw = await self._execute(prompt)
        try:
            artifact = self._parser.parse(raw)
            return RequirementsExecutionResult(
                artifact, sha256(raw.encode()).hexdigest(), False, None, ()
            )
        except Exception as exc:
            failure = self._parser.failure(raw, exc)
            parse_error = exc
        if self._repair is None:
            raise RequirementsOutputError(
                "Requirements output failed strict validation"
            ) from parse_error
        repair_prompt = build_repair_prompt(raw, failure)
        repaired = await self._repair(repair_prompt)
        try:
            artifact = self._parser.parse(repaired)
        except Exception as repair_exc:
            raise RequirementsOutputError(
                "Requirements output remained invalid after one repair"
            ) from repair_exc
        return RequirementsExecutionResult(
            artifact,
            failure.raw_output_hash,
            True,
            True,
            failure.errors,
        )


def build_revision_prompt(value: RequirementsExecutionInput) -> str:
    schema = RequirementsArtifactDocument.model_json_schema()
    payload = {
        "project_name": value.project_name,
        "objective": value.objective,
        "manifest": value.manifest,
        "source_context": value.source_context,
        "previous_artifact": value.previous_artifact,
        "revision_cycle_number": value.revision_cycle_number,
        "revision_feedback_summary": value.revision_feedback_summary,
        "revision_feedback": value.revision_feedback,
        "revision_feedback_hash": value.revision_feedback_hash,
    }
    return (
        "Return exactly one JSON object matching the supplied schema. Preserve valid previous "
        "requirements and address every immutable revision finding. No Markdown or commentary.\n"
        f"INPUT={json.dumps(payload, sort_keys=True, separators=(',', ':'))}\n"
        f"SCHEMA={json.dumps(schema, sort_keys=True, separators=(',', ':'))}"
    )


def build_repair_prompt(raw: str, failure: ArtifactParseFailure) -> str:
    return (
        "Repair this into exactly one schema-valid JSON object. No Markdown or explanation. "
        "Preserve valid substantive content.\n"
        f"ERRORS={json.dumps(failure.errors, separators=(',', ':'))}\n"
        f"INVALID={raw[:100_000]}"
    )


async def run_sync(call: Callable[[str], str], prompt: str) -> str:
    return await asyncio.to_thread(call, prompt)
