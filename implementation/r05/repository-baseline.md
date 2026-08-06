# P15 — R5 repository baseline

- R document: `1/r5.txt`
- R title: R5 — Universal Manifest Transformation Engine (UMTE)
- Specification hash: `d764e5c3f6a5b3ce3a5cbdc8be41615286ddbcb0e2cfea460931234277894687`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r5.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r5_umte_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r5_umte.py` |
| persistence_or_migration | implemented | `migrations/versions/3c8d1e4f6a7b_add_r5_umte_records.py`<br>`migrations/versions/4d9e2f7a6b1c_add_r5_generated_artifacts.py`<br>`migrations/versions/5e1a9c8d2f4b_add_r5_export_bundles.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r5_umte_schemas.py` |
| tests | implemented | `apps/api/tests/test_r5_umte_domain.py`<br>`apps/api/tests/test_r5_umte_persistence.py` |
| status_documentation | implemented | `docs/ir/R05-IR-01-manifest-transformation-engine.md`<br>`implementation/r05/acceptance-evidence.md`<br>`implementation/r05/api-changes/README.md`<br>`implementation/r05/completion-report.md`<br>`implementation/r05/gap-analysis.md`<br>`implementation/r05/implementation-plan.md`<br>`implementation/r05/migration-plan/README.md`<br>`implementation/r05/repository-baseline.md`<br>`implementation/r05/requirement-matrix.md`<br>`implementation/r05/schema-changes/README.md`<br>`implementation/r05/security-review.md`<br>`implementation/r05/test-plan.md` |
