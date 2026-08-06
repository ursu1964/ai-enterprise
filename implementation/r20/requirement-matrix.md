# P30 — R20 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r20.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r20_runtime_kernel_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r20_runtime_kernel_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r20_runtime_kernel.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r20_runtime_kernel_schemas.py` |
| tests | implemented | `apps/api/tests/test_r20_runtime_kernel_runtime.py` |
| status_documentation | implemented | `docs/ir/R20-IR-01-organizational-knowledge-engine.md`<br>`docs/r20-runtime-kernel-status.md`<br>`implementation/r20/acceptance-evidence.md`<br>`implementation/r20/api-changes/README.md`<br>`implementation/r20/completion-report.md`<br>`implementation/r20/gap-analysis.md`<br>`implementation/r20/implementation-plan.md`<br>`implementation/r20/migration-plan/README.md`<br>`implementation/r20/repository-baseline.md`<br>`implementation/r20/requirement-matrix.md`<br>`implementation/r20/schema-changes/README.md`<br>`implementation/r20/security-review.md`<br>... 1 more |
