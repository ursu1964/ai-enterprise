# P18 — R8 repository baseline

- R document: `1/r8.txt`
- R title: R8 — Universal Governance, Evolution & Intelligence Framework (UGEIF)
- Specification hash: `968912f2385d30a8c0c5349e85397ce63c44f074a8ac4edb7fb4e2f9405437f0`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r8.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/domain/r8_ugeif.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r8_ugeif_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r8_ugeif.py` |
| persistence_or_migration | implemented | `migrations/versions/f4b8d2a6c9e1_add_r8_ugeif_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r8_ugeif_schemas.py` |
| tests | implemented | `apps/api/tests/test_r8_ugeif_domain.py`<br>`apps/api/tests/test_r8_ugeif_persistence.py` |
| status_documentation | implemented | `implementation/r08/acceptance-evidence.md`<br>`implementation/r08/api-changes/README.md`<br>`implementation/r08/completion-report.md`<br>`implementation/r08/gap-analysis.md`<br>`implementation/r08/implementation-plan.md`<br>`implementation/r08/migration-plan/README.md`<br>`implementation/r08/repository-baseline.md`<br>`implementation/r08/requirement-matrix.md`<br>`implementation/r08/schema-changes/README.md`<br>`implementation/r08/security-review.md`<br>`implementation/r08/test-plan.md` |
