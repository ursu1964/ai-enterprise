from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from ai_enterprise.domain.r4_interpretation import (
    AdapterResult,
    ExtractionResponse,
    InterpretationRequest,
    validate_extraction_response,
)
from ai_enterprise.infrastructure.r4_ai.provider import (
    R4AsyncModelAdapter,
    R4ProviderTransientError,
)


@dataclass(frozen=True, slots=True)
class R4RetryPolicy:
    provider_retries: int = 2
    schema_repair_attempts: int = 1


@dataclass(frozen=True, slots=True)
class R4InterpretationExecution:
    adapter_result: AdapterResult
    extraction: ExtractionResponse
    provider_retry_count: int
    schema_repair_count: int


async def execute_with_retries(
    adapter: R4AsyncModelAdapter,
    request: InterpretationRequest,
    *,
    known_segment_ids: set[str],
    policy: R4RetryPolicy,
    on_failure: Callable[[str, int, str, str], Awaitable[None]] | None = None,
) -> R4InterpretationExecution:
    provider_failures = 0
    while True:
        try:
            adapter_result = await adapter.interpret(request)
            break
        except R4ProviderTransientError as exc:
            if on_failure is not None:
                await on_failure(
                    "provider_transient",
                    provider_failures,
                    "provider_failed",
                    str(exc),
                )
            if provider_failures >= policy.provider_retries:
                raise
            provider_failures += 1

    schema_repairs = 0
    while True:
        try:
            extraction = validate_extraction_response(
                adapter_result.structured_output,
                known_segment_ids=known_segment_ids,
            )
            return R4InterpretationExecution(
                adapter_result=adapter_result,
                extraction=extraction,
                provider_retry_count=provider_failures,
                schema_repair_count=schema_repairs,
            )
        except ValueError as exc:
            if on_failure is not None:
                await on_failure(
                    "schema_validation",
                    schema_repairs,
                    "schema_failed",
                    str(exc),
                )
            if schema_repairs >= policy.schema_repair_attempts:
                raise
            adapter_result = await adapter.repair(
                request,
                invalid_output=adapter_result.structured_output,
                error_summary=str(exc),
            )
            schema_repairs += 1
