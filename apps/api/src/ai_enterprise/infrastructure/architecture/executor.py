from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from ai_enterprise.domain.architecture.renderer import render_architecture_markdown
from ai_enterprise.domain.architecture.schema import ArchitectureArtifactDocument
from ai_enterprise.domain.architecture.validation import (
    ArchitectureValidationError,
    validate_architecture,
)
from ai_enterprise.infrastructure.architecture.contracts import (
    ArchitectureAttemptEvidenceWriter,
    ArchitectureExecutionContext,
    ArchitectureModelProvider,
    AttemptEvidence,
    ModelInvocationResult,
)
from ai_enterprise.infrastructure.architecture.parser import (
    ArchitectureOutputParseError,
    parse_architecture_json,
)


@dataclass(frozen=True, slots=True)
class ValidatedArchitectureExecution:
    document: ArchitectureArtifactDocument
    markdown: str
    structured_checksum: str
    markdown_checksum: str
    invocation_count: int


class TrustedArchitectureExecutor:
    def __init__(
        self,
        *,
        provider: ArchitectureModelProvider,
        evidence_writer: ArchitectureAttemptEvidenceWriter,
        maximum_raw_output_bytes: int = 2_000_000,
        maximum_repair_attempts: int = 1,
    ) -> None:
        if maximum_repair_attempts not in {0, 1}:
            raise ValueError("Architecture repair attempts must be zero or one")
        self._provider = provider
        self._evidence_writer = evidence_writer
        self._maximum_bytes = maximum_raw_output_bytes
        self._maximum_repairs = maximum_repair_attempts

    async def execute(
        self, context: ArchitectureExecutionContext
    ) -> ValidatedArchitectureExecution:
        invalid_output = ""
        report: tuple[dict[str, str], ...] = ()
        total = 1 + self._maximum_repairs
        for index in range(total):
            operation = "generate" if index == 0 else "repair"
            started = datetime.now(UTC)
            invocation: ModelInvocationResult | None = None
            try:
                remaining = (context.deadline_at - started).total_seconds()
                if remaining <= 0:
                    raise TimeoutError("Architecture execution deadline elapsed")
                invocation = await asyncio.wait_for(
                    self._invoke(operation, context, invalid_output, report), timeout=remaining
                )
                document = parse_architecture_json(
                    invocation.raw_output, maximum_bytes=self._maximum_bytes
                )
                validate_architecture(
                    document, approved_requirement_ids=context.approved_requirement_ids
                )
            except (ArchitectureOutputParseError, ArchitectureValidationError) as exc:
                invalid_output = invocation.raw_output if invocation is not None else ""
                report = self._report(exc)
                await self._record(
                    context,
                    context.attempt_number_offset + index + 1,
                    operation,
                    "validation_failed",
                    started,
                    invocation,
                    report,
                    "invalid_architecture_output",
                )
                if index + 1 >= total:
                    raise
                continue
            except TimeoutError:
                await self._record(
                    context,
                    context.attempt_number_offset + index + 1,
                    operation,
                    "timed_out",
                    started,
                    None,
                    (),
                    "architecture_execution_timeout",
                )
                raise
            except Exception:
                await self._record(
                    context,
                    context.attempt_number_offset + index + 1,
                    operation,
                    "failed",
                    started,
                    invocation,
                    (),
                    "architecture_provider_error",
                )
                raise
            await self._record(
                context,
                context.attempt_number_offset + index + 1,
                operation,
                "succeeded",
                started,
                invocation,
                (),
                None,
            )
            structured = document.model_dump_json()
            markdown = render_architecture_markdown(document)
            return ValidatedArchitectureExecution(
                document=document,
                markdown=markdown,
                structured_checksum=hashlib.sha256(structured.encode()).hexdigest(),
                markdown_checksum=hashlib.sha256(markdown.encode()).hexdigest(),
                invocation_count=index + 1,
            )
        raise AssertionError("unreachable")

    async def _invoke(
        self,
        operation: str,
        context: ArchitectureExecutionContext,
        invalid: str,
        report: tuple[dict[str, str], ...],
    ) -> ModelInvocationResult:
        if operation == "generate":
            return await self._provider.generate(context)
        return await self._provider.repair(
            context, invalid_output=invalid, validation_report=report
        )

    @staticmethod
    def _report(exc: Exception) -> tuple[dict[str, str], ...]:
        if isinstance(exc, ArchitectureValidationError):
            return tuple(
                {"code": item.code, "location": item.location, "message": item.message}
                for item in exc.issues
            )
        return ({"code": "schema_invalid", "location": "$", "message": str(exc)},)

    async def _record(
        self,
        context: ArchitectureExecutionContext,
        number: int,
        operation: str,
        status: str,
        started: datetime,
        invocation: ModelInvocationResult | None,
        report: tuple[dict[str, str], ...],
        failure_code: str | None,
    ) -> None:
        await self._evidence_writer.record(
            AttemptEvidence(
                run_id=context.run_id,
                attempt_number=number,
                operation=operation,
                status=status,
                model_name=invocation.model_name if invocation else self._provider.model_name,
                provider_name=self._provider.name,
                prompt_bundle_hash=invocation.prompt_bundle_hash if invocation else "",
                raw_output_hash=(
                    hashlib.sha256(invocation.raw_output.encode()).hexdigest()
                    if invocation
                    else None
                ),
                raw_output=invocation.raw_output if invocation else None,
                token_usage=invocation.token_usage if invocation else {},
                validation_report=report,
                started_at=started,
                completed_at=datetime.now(UTC),
                failure_code=failure_code,
            )
        )
