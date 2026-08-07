# P14 — R4 exact clause verification

Authoritative R source: `1/r4.txt`

This document records the R4 AI interpretation and manifest extraction
contract against current repository symbols. It closes P14/R4 by mapping the
controlled-AI workflow to existing code, schemas, migrations, security controls,
provider adapters, evaluation tooling, and tests.

| R4 clause | Status | Repository evidence |
|---|---|---|
| Accept unstructured client text as a registered source. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::register_text_source`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::register_source`; `apps/api/tests/test_r4_interpretation_domain.py`; `apps/api/tests/test_r4_interpretation_api.py` |
| Normalize source text into machine-processable source segments without changing business meaning. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::normalize_and_segment`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::normalize_source`; `apps/api/tests/test_r4_interpretation_domain.py::test_r4_text_source_normalization_segments_source_with_stable_evidence` |
| Invoke one configured AI model through a versioned interpretation contract. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::InterpretationRequest`; `apps/api/src/ai_enterprise/domain/r4_interpretation.py::PromptDefinition`; `apps/api/src/ai_enterprise/infrastructure/r4_ai/provider.py`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::start_interpretation`; `apps/api/tests/test_r4_provider_retry_security.py` |
| Receive structured output conforming to an approved response schema and reject malformed or schema-invalid AI output. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::validate_extraction_response`; `specifications/AI-EXTRACTION-RESPONSE-0.1.schema.json`; `apps/api/tests/test_r4_interpretation_domain.py::test_r4_extraction_validation_rejects_unknown_segments_and_ai_approval`; `apps/api/tests/test_r4_provider_retry_security.py::test_r4_ollama_provider_parses_schema_json_response` |
| Create staged candidate AEPM/AEIR objects and relationships from valid AI output. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::CandidateObject`; `apps/api/src/ai_enterprise/domain/r4_interpretation.py::CandidateRelationship`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::_candidate_rows`; `apps/api/tests/test_r4_interpretation_persistence.py`; `migrations/versions/8c1d4e6f9a23_add_r4_ai_interpretation_records.py` |
| Mark AI-derived knowledge as inferred/pending and prevent AI approval. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py`; `apps/api/tests/test_r4_interpretation_domain.py::test_r4_mock_adapter_output_is_schema_valid_and_pending_review_only`; `apps/api/tests/test_r4_interpretation_domain.py::test_r4_extraction_validation_rejects_unknown_segments_and_ai_approval` |
| Preserve traceability to exact source segments and AI-operation provenance. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py::SourceSupport`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py`; `apps/api/src/ai_enterprise/domain/aepm_interpretation.py`; `specifications/AI-PROVENANCE-0.1.schema.json`; `apps/api/tests/test_aepm_interpretation.py` |
| Generate ambiguity, assumption, probable-contradiction, missing-information, and clarification-question records. | implemented | `apps/api/src/ai_enterprise/domain/r4_interpretation.py`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py`; `apps/api/tests/test_r4_interpretation_api.py`; `apps/api/tests/test_r4_interpretation_persistence.py` |
| Allow human review actions and promote only approved candidate knowledge into canonical AEIR. | implemented | `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::review_candidate`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::promote_candidate`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::_promote_relationship_candidate`; `migrations/versions/1f2a3b4c5d6e_align_r4_aeir_promotion_schema.py`; `apps/api/tests/test_r4_interpretation_api.py` |
| Prevent AI from directly modifying approved canonical knowledge. | implemented | candidate staging and promotion routes require human actor/review state before canonical writes; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py`; `apps/api/tests/test_r4_interpretation_api.py`; `docs/ir/R04-IR-01-controlled-ai-participation.md` |
| Record retries, provider failures, usage/cost metadata, and secure prompt handling. | implemented | `apps/api/src/ai_enterprise/infrastructure/r4_ai/retry.py`; `apps/api/src/ai_enterprise/infrastructure/r4_ai/provider.py`; `apps/api/src/ai_enterprise/infrastructure/r4_ai/security.py`; `apps/api/tests/test_r4_provider_retry_security.py` |
| Redact secret-like material before provider exposure and reject unredacted secret-like output. | implemented | `apps/api/src/ai_enterprise/infrastructure/r4_ai/security.py`; `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py::start_interpretation`; `apps/api/tests/test_r4_provider_retry_security.py::test_r4_secret_redaction_replaces_sensitive_source_before_model_submission` |
| Pass automated evaluation against representative source examples. | implemented | `apps/api/src/ai_enterprise/infrastructure/r4_ai/evaluation.py`; `schemas/evidence-audit/r4-evaluation-report.schema.json`; `apps/api/tests/test_r4_evaluation_runner.py` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q \
  tests/test_r4_interpretation_domain.py \
  tests/test_r4_provider_retry_security.py \
  tests/test_r4_interpretation_api.py \
  tests/test_r4_interpretation_persistence.py \
  tests/test_r4_evaluation_runner.py \
  tests/test_aepm_interpretation.py
```

Result:

```text
31 passed
```

## Verdict

P14/R4 is implemented. No exact R4 clause remains blocked or missing in the
current repository baseline.
