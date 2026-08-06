# P16 — R6 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r6.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r6_uagf_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r6_uagf.py` |
| persistence_or_migration | implemented | `migrations/versions/6a2b8c9d1e5f_add_r6_uagf_records.py`<br>`migrations/versions/7c4e2a9b8d1f_add_r6_lifecycle_events.py`<br>`migrations/versions/c8d3e7f1a9b2_add_r6_production_factory_layer.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r6_uagf_schemas.py` |
| tests | implemented | `apps/api/tests/test_r6_uagf_domain.py`<br>`apps/api/tests/test_r6_uagf_persistence.py` |
| status_documentation | implemented | `implementation/r06/acceptance-evidence.md`<br>`implementation/r06/api-changes/README.md`<br>`implementation/r06/completion-report.md`<br>`implementation/r06/gap-analysis.md`<br>`implementation/r06/implementation-plan.md`<br>`implementation/r06/migration-plan/README.md`<br>`implementation/r06/repository-baseline.md`<br>`implementation/r06/requirement-matrix.md`<br>`implementation/r06/schema-changes/README.md`<br>`implementation/r06/security-review.md`<br>`implementation/r06/test-plan.md` |
