from __future__ import annotations

import json

import httpx
import pytest

from ai_enterprise.domain.r4_interpretation import (
    AdapterResult,
    InterpretationRequest,
    PromptDefinition,
    normalize_and_segment,
    register_text_source,
)
from ai_enterprise.infrastructure.r4_ai.provider import (
    OllamaManifestExtractionAdapter,
    R4ProviderConfig,
    R4ProviderTransientError,
)
from ai_enterprise.infrastructure.r4_ai.retry import R4RetryPolicy, execute_with_retries
from ai_enterprise.infrastructure.r4_ai.security import (
    contains_unredacted_secret,
    redact_source_segments,
)


def _request() -> InterpretationRequest:
    source = register_text_source(
        source_id="SRC-002",
        project_id="project-1",
        name="Client manifesto",
        text="# Inventory\n\nTrack stock levels",
        captured_by="analyst",
        media_type="text/markdown",
    )
    normalized = normalize_and_segment(source)
    return InterpretationRequest(
        operation_id="AIOP-0001",
        project_id="project-1",
        source_segments=normalized.segments,
        prompt=PromptDefinition(),
        correlation_id="corr-1",
    )


@pytest.mark.anyio
async def test_r4_ollama_provider_parses_schema_json_response() -> None:
    request = _request()

    async def handler(request_: httpx.Request) -> httpx.Response:
        payload = json.loads(request_.content)
        assert payload["format"] == "json"
        assert payload["messages"][1]["content"].count("SOURCE_DATA_JSON") == 1
        return httpx.Response(
            200,
            json={
                "model": "gemma3:12b",
                "message": {
                    "content": json.dumps(
                        {
                            "operation_id": "AIOP-0001",
                            "source_summary": {
                                "supported_language": "en",
                                "source_scope": "inventory",
                            },
                            "candidate_objects": [
                                {
                                    "candidate_id": "CAND-OBJ-0001",
                                    "proposed_type": "Intent",
                                    "proposed_id": "INT-001",
                                    "name": "Inventory",
                                    "description": "Track stock levels",
                                    "truth_status": "asserted",
                                    "approval_status": "pending",
                                    "confidence": 0.9,
                                    "source_support": [
                                        {
                                            "source_id": "SRC-002",
                                            "segment_id": "SEG-002-0001",
                                            "support_type": "direct",
                                            "quoted_fragment": "# Inventory",
                                        }
                                    ],
                                    "attributes": {},
                                    "interpretation_rationale": "Directly stated.",
                                    "warnings": [],
                                }
                            ],
                            "candidate_relationships": [],
                            "ambiguities": [],
                            "assumptions": [],
                            "probable_contradictions": [],
                            "missing_information": [],
                            "clarification_candidates": [],
                            "unsupported_requests": [],
                        }
                    )
                },
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        )

    adapter = OllamaManifestExtractionAdapter(
        R4ProviderConfig(provider="ollama"),
        transport=httpx.MockTransport(handler),
    )

    result = await adapter.interpret(request)

    assert result.model_metadata["provider"] == "ollama"
    assert result.structured_output["operation_id"] == "AIOP-0001"
    assert result.input_token_count == 100
    assert result.output_token_count == 50


@pytest.mark.anyio
async def test_r4_retry_orchestrator_retries_transient_provider_failure() -> None:
    request = _request()
    calls = 0

    class FlakyAdapter:
        name = "flaky"
        model_name = "flaky-model"

        async def interpret(self, request_: InterpretationRequest) -> AdapterResult:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise R4ProviderTransientError("rate limited")
            return AdapterResult(
                operation_id=request_.operation_id,
                structured_output={
                    "operation_id": request_.operation_id,
                    "source_summary": {},
                    "candidate_objects": [],
                    "candidate_relationships": [],
                    "ambiguities": [],
                    "assumptions": [],
                    "probable_contradictions": [],
                    "missing_information": [],
                    "clarification_candidates": [],
                    "unsupported_requests": [],
                },
                raw_provider_response_ref="test://ok",
                model_metadata={"provider": "flaky", "model": "flaky-model"},
                input_token_count=1,
                output_token_count=1,
                latency_ms=0,
                finish_status="stop",
                provider_request_id="req-1",
            )

        async def repair(
            self,
            request_: InterpretationRequest,
            *,
            invalid_output: dict[str, object],
            error_summary: str,
        ) -> AdapterResult:
            return await self.interpret(request_)

    failures: list[tuple[str, int, str, str]] = []

    async def on_failure(
        failure_type: str,
        retry_count: int,
        final_status: str,
        error_summary: str,
    ) -> None:
        failures.append((failure_type, retry_count, final_status, error_summary))

    result = await execute_with_retries(
        FlakyAdapter(),
        request,
        known_segment_ids={segment.id for segment in request.source_segments},
        policy=R4RetryPolicy(provider_retries=2, schema_repair_attempts=0),
        on_failure=on_failure,
    )

    assert calls == 2
    assert result.provider_retry_count == 1
    assert failures[0][0] == "provider_transient"


def test_r4_secret_redaction_replaces_sensitive_source_before_model_submission() -> None:
    source = register_text_source(
        source_id="SRC-002",
        project_id="project-1",
        name="Secret fixture",
        text="api_key = sk-test-secret-123456789 Track stock levels",
        captured_by="analyst",
    )
    normalized = normalize_and_segment(source)

    result = redact_source_segments(normalized.segments, enabled=True)

    assert result.redacted
    assert result.indicators == ("api_key_assignment",)
    assert "[REDACTED_SECRET]" in result.segments[0].text
    assert not contains_unredacted_secret([segment.text for segment in result.segments])
