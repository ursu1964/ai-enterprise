# P18 — R8 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r8.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/domain/r8_ugeif.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r8_ugeif_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r8_ugeif.py` |
| persistence_or_migration | implemented | `migrations/versions/f4b8d2a6c9e1_add_r8_ugeif_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r8_ugeif_schemas.py` |
| tests | implemented | `apps/api/tests/test_r8_ugeif_domain.py`<br>`apps/api/tests/test_r8_ugeif_persistence.py` |
| status_documentation | implemented | `docs/ir/R08-IR-01-governance-evolution-intelligence-framework.md`<br>`implementation/r08/acceptance-evidence.md`<br>`implementation/r08/api-changes/README.md`<br>`implementation/r08/completion-report.md`<br>`implementation/r08/gap-analysis.md`<br>`implementation/r08/implementation-plan.md`<br>`implementation/r08/migration-plan/README.md`<br>`implementation/r08/repository-baseline.md`<br>`implementation/r08/requirement-matrix.md`<br>`implementation/r08/schema-changes/README.md`<br>`implementation/r08/security-review.md`<br>`implementation/r08/test-plan.md` |
