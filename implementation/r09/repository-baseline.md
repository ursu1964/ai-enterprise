# P19 — R9 repository baseline

- R document: `1/r9.txt`
- R title: R9 — Universal AI-Enterprise Kernel (UAK)
- Specification hash: `5145ab46548c4b7345fc535922ff931b0fca832591ba6b188d0b1256e66ec499`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r9.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r9_uak_runtime.py`<br>`apps/api/src/ai_enterprise/domain/r9_uak.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r9_uak_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r9_uak.py` |
| persistence_or_migration | implemented | `migrations/versions/a9c1e4f6b8d2_add_r9_kernel_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r9_uak_schemas.py` |
| tests | implemented | `apps/api/tests/test_r9_uak_domain.py`<br>`apps/api/tests/test_r9_uak_persistence.py`<br>`apps/api/tests/test_r9_uak_runtime.py` |
| status_documentation | implemented | `implementation/r09/acceptance-evidence.md`<br>`implementation/r09/api-changes/README.md`<br>`implementation/r09/completion-report.md`<br>`implementation/r09/gap-analysis.md`<br>`implementation/r09/implementation-plan.md`<br>`implementation/r09/migration-plan/README.md`<br>`implementation/r09/repository-baseline.md`<br>`implementation/r09/requirement-matrix.md`<br>`implementation/r09/schema-changes/README.md`<br>`implementation/r09/security-review.md`<br>`implementation/r09/test-plan.md` |
