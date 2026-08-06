# P14 — R4 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r4.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/domain/aepm_interpretation.py`<br>`apps/api/src/ai_enterprise/domain/r4_interpretation.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r4_ai_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r4_ai_interpretation.py` |
| persistence_or_migration | implemented | `apps/api/src/ai_enterprise/infrastructure/r4_ai/__init__.py`<br>`apps/api/src/ai_enterprise/infrastructure/r4_ai/evaluation.py`<br>`apps/api/src/ai_enterprise/infrastructure/r4_ai/provider.py`<br>`apps/api/src/ai_enterprise/infrastructure/r4_ai/retry.py`<br>`apps/api/src/ai_enterprise/infrastructure/r4_ai/security.py`<br>`migrations/versions/1f2a3b4c5d6e_align_r4_aeir_promotion_schema.py`<br>`migrations/versions/8c1d4e6f9a23_add_r4_ai_interpretation_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r4_ai_schemas.py` |
| tests | implemented | `apps/api/tests/test_aepm_interpretation.py`<br>`apps/api/tests/test_r4_evaluation_runner.py`<br>`apps/api/tests/test_r4_interpretation_api.py`<br>`apps/api/tests/test_r4_interpretation_domain.py`<br>`apps/api/tests/test_r4_interpretation_persistence.py`<br>`apps/api/tests/test_r4_provider_retry_security.py` |
| status_documentation | implemented | `docs/ir/R04-IR-01-controlled-ai-participation.md`<br>`implementation/r04/acceptance-evidence.md`<br>`implementation/r04/api-changes/README.md`<br>`implementation/r04/completion-report.md`<br>`implementation/r04/gap-analysis.md`<br>`implementation/r04/implementation-plan.md`<br>`implementation/r04/migration-plan/README.md`<br>`implementation/r04/repository-baseline.md`<br>`implementation/r04/requirement-matrix.md`<br>`implementation/r04/schema-changes/README.md`<br>`implementation/r04/security-review.md`<br>`implementation/r04/test-plan.md` |
