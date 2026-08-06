from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_enterprise.domain.hashing import hash_json
from ai_enterprise.domain.r4_interpretation import (
    EvaluationMetrics,
    InterpretationRequest,
    MockManifestExtractionAdapter,
    PromptDefinition,
    duplicate_candidate_findings,
    normalize_and_segment,
    register_text_source,
    validate_extraction_response,
)
from ai_enterprise.infrastructure.knowledge.models import R4EvaluationRecordModel


@dataclass(frozen=True, slots=True)
class R4EvaluationCaseResult:
    case_id: str
    run_id: str
    metrics: EvaluationMetrics
    passed: bool
    result_document: dict[str, Any]


def run_evaluation_case(
    *,
    case_path: Path,
    expected_path: Path,
    run_id: str,
) -> R4EvaluationCaseResult:
    case_id = expected_path.stem
    source_text = case_path.read_text(encoding="utf-8")
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    source = register_text_source(
        source_id="SRC-002",
        project_id=f"evaluation:{case_id}",
        name=case_id,
        text=source_text,
        captured_by="r4-evaluation-runner",
        media_type="text/plain",
    )
    normalized = normalize_and_segment(source)
    request = InterpretationRequest(
        operation_id="AIOP-0001",
        project_id=f"evaluation:{case_id}",
        source_segments=normalized.segments,
        prompt=PromptDefinition(),
        correlation_id=run_id,
    )
    adapter_result = MockManifestExtractionAdapter().interpret(request)
    schema_valid = True
    try:
        extraction = validate_extraction_response(
            adapter_result.structured_output,
            known_segment_ids={segment.id for segment in normalized.segments},
        )
    except ValueError as exc:
        schema_valid = False
        result_document = {
            "case_id": case_id,
            "run_id": run_id,
            "schema_error": str(exc),
            "adapter_result": adapter_result.model_dump(mode="json"),
        }
        metrics = EvaluationMetrics(
            schema_compliance_rate=0.0,
            source_attribution_accuracy=0.0,
            unsupported_invention_rate=1.0,
            object_extraction_precision=0.0,
            object_extraction_recall=0.0,
            human_acceptance_rate=0.0,
            blocking_ambiguity_recall=0.0,
        )
        return R4EvaluationCaseResult(
            case_id=case_id,
            run_id=run_id,
            metrics=metrics,
            passed=False,
            result_document=result_document,
        )

    candidate_objects = list(extraction.candidate_objects)
    extracted_types = {candidate.proposed_type for candidate in candidate_objects}
    expected_types = set(expected.get("expected_object_types", []))
    expected_links = set(expected.get("expected_source_segment_links", []))
    expected_ambiguities = set(expected.get("expected_ambiguities", []))
    candidate_text = " ".join(
        f"{candidate.name} {candidate.description}" for candidate in candidate_objects
    ).lower()
    prohibited = [item.lower() for item in expected.get("prohibited_invented_facts", [])]
    unsupported_count = sum(1 for item in prohibited if item in candidate_text)
    supported_links = [
        support.segment_id
        for candidate in candidate_objects
        for support in candidate.source_support
    ]
    metrics = EvaluationMetrics(
        schema_compliance_rate=1.0 if schema_valid else 0.0,
        source_attribution_accuracy=_ratio(
            sum(1 for link in supported_links if link in expected_links),
            len(supported_links),
            default=1.0,
        ),
        unsupported_invention_rate=_ratio(unsupported_count, len(candidate_objects)),
        object_extraction_precision=_ratio(
            len(extracted_types & expected_types),
            len(extracted_types),
        ),
        object_extraction_recall=_ratio(
            len(extracted_types & expected_types),
            len(expected_types),
            default=1.0,
        ),
        human_acceptance_rate=_ratio(
            sum(1 for candidate in candidate_objects if candidate.confidence >= 0.8),
            len(candidate_objects),
            default=1.0,
        ),
        blocking_ambiguity_recall=_ratio(
            len(extraction.ambiguities),
            len(expected_ambiguities),
            default=1.0,
        ),
    )
    result_document = {
        "case_id": case_id,
        "run_id": run_id,
        "expected": expected,
        "extraction": extraction.model_dump(mode="json"),
        "duplicate_findings": list(duplicate_candidate_findings(extraction)),
        "metrics": metrics.model_dump(mode="json"),
        "passed": metrics.passes_r4_thresholds,
        "result_hash": hash_json(
            {
                "case_id": case_id,
                "run_id": run_id,
                "metrics": metrics.model_dump(mode="json"),
            }
        ),
    }
    return R4EvaluationCaseResult(
        case_id=case_id,
        run_id=run_id,
        metrics=metrics,
        passed=metrics.passes_r4_thresholds,
        result_document=result_document,
    )


def run_evaluation_suite(
    *,
    evaluation_root: Path,
    run_id: str,
    report_path: Path | None = None,
) -> dict[str, Any]:
    results = [
        run_evaluation_case(
            case_path=case_path,
            expected_path=evaluation_root / "expected" / f"{case_path.stem}.json",
            run_id=run_id,
        )
        for case_path in sorted((evaluation_root / "cases").glob("*.txt"))
        if (evaluation_root / "expected" / f"{case_path.stem}.json").exists()
    ]
    report = {
        "run_id": run_id,
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result.passed),
        "failed_count": sum(1 for result in results if not result.passed),
        "cases": [result.result_document for result in results],
        "passed": all(result.passed for result in results) if results else False,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def evaluation_record(result: R4EvaluationCaseResult) -> R4EvaluationRecordModel:
    return R4EvaluationRecordModel(
        id=uuid.uuid4(),
        case_id=result.case_id,
        run_id=result.run_id,
        metrics=result.metrics.model_dump(mode="json"),
        passed=result.passed,
        result_document=result.result_document,
    )


def _ratio(numerator: int, denominator: int, *, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator
