from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from ai_enterprise.infrastructure.knowledge.models import R4EvaluationRecordModel
from ai_enterprise.infrastructure.r4_ai.evaluation import (
    evaluation_record,
    run_evaluation_case,
    run_evaluation_suite,
)

ROOT = Path(__file__).resolve().parents[3]
REPORT_SCHEMA = json.loads(
    (ROOT / "schemas/evidence-audit/r4-evaluation-report.schema.json").read_text(encoding="utf-8")
)


def test_r4_evaluation_case_calculates_required_quality_metrics() -> None:
    result = run_evaluation_case(
        case_path=ROOT / "evaluation/cases/clear-project-manifesto.txt",
        expected_path=ROOT / "evaluation/expected/clear-project-manifesto.json",
        run_id="eval-test-1",
    )

    assert result.case_id == "clear-project-manifesto"
    assert result.metrics.schema_compliance_rate == 1.0
    assert result.metrics.source_attribution_accuracy == 1.0
    assert result.metrics.unsupported_invention_rate == 0.0
    assert result.metrics.object_extraction_precision == 1.0
    assert result.metrics.object_extraction_recall == 1.0
    assert result.passed
    assert result.result_document["passed"] is True


def test_r4_evaluation_suite_writes_machine_readable_report(tmp_path: Path) -> None:
    report_path = tmp_path / "r4-report.json"

    report = run_evaluation_suite(
        evaluation_root=ROOT / "evaluation",
        run_id="eval-suite-test",
        report_path=report_path,
    )

    written = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "1.0"
    assert report["schema_ref"] == "schemas/evidence-audit/r4-evaluation-report.schema.json"
    assert report["case_count"] == 1
    assert report["passed"]
    assert len(report["report_hash"]) == 64
    assert written == report
    jsonschema.validate(report, REPORT_SCHEMA)


def test_r4_evaluation_suite_fails_closed_when_schema_validation_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from ai_enterprise.infrastructure.r4_ai import evaluation

    original_schema = evaluation._schema

    def stricter_schema() -> dict:
        schema = original_schema()
        return {**schema, "required": [*schema["required"], "impossible_field"]}

    monkeypatch.setattr(evaluation, "_schema", stricter_schema)

    try:
        run_evaluation_suite(
            evaluation_root=ROOT / "evaluation",
            run_id="eval-suite-test",
            report_path=tmp_path / "r4-report.json",
        )
    except RuntimeError as exc:
        assert "r4-evaluation-report.schema.json" in str(exc)
        assert "does not validate" in str(exc)
    else:
        raise AssertionError("invalid R4 evaluation report was accepted")
    assert not (tmp_path / "r4-report.json").exists()


def test_r4_evaluation_record_factory_matches_persistence_model() -> None:
    result = run_evaluation_case(
        case_path=ROOT / "evaluation/cases/clear-project-manifesto.txt",
        expected_path=ROOT / "evaluation/expected/clear-project-manifesto.json",
        run_id="eval-record-test",
    )

    row = evaluation_record(result)

    assert isinstance(row, R4EvaluationRecordModel)
    assert row.case_id == "clear-project-manifesto"
    assert row.metrics["unsupported_invention_rate"] == 0.0
    assert row.passed
