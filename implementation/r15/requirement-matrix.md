# P25 — R15 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r15.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r15_manifest_compiler_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r15_manifest_compiler_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r15_manifest_compiler.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r15_manifest_compiler_schemas.py` |
| tests | implemented | `apps/api/tests/test_r15_manifest_compiler_runtime.py` |
| status_documentation | implemented | `docs/ir/R15-IR-01-workflow-process-engine.md`<br>`docs/r15-manifest-compiler-status.md`<br>`implementation/r15/acceptance-evidence.md`<br>`implementation/r15/api-changes/README.md`<br>`implementation/r15/completion-report.md`<br>`implementation/r15/gap-analysis.md`<br>`implementation/r15/implementation-plan.md`<br>`implementation/r15/migration-plan/README.md`<br>`implementation/r15/repository-baseline.md`<br>`implementation/r15/requirement-matrix.md`<br>`implementation/r15/schema-changes/README.md`<br>`implementation/r15/security-review.md`<br>... 1 more |
