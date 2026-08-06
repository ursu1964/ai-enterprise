# P27 — R17 repository baseline

- R document: `1/r17.txt`
- R title: R17 — AI-Enterprise Execution Planning Engine Specification
- Specification hash: `c97a703c449cefc177fe208e32ee9adb669d015f7ed8eda2149f3cf682e1d948`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r17.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r17_execution_planner_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r17_execution_planner_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r17_execution_planner.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r17_execution_planner_schemas.py` |
| tests | implemented | `apps/api/tests/test_r17_execution_planner_runtime.py` |
| status_documentation | implemented | `docs/ir/R17-IR-01-deployment-runtime-engine.md`<br>`docs/r17-execution-planner-status.md`<br>`implementation/r17/acceptance-evidence.md`<br>`implementation/r17/api-changes/README.md`<br>`implementation/r17/completion-report.md`<br>`implementation/r17/gap-analysis.md`<br>`implementation/r17/implementation-plan.md`<br>`implementation/r17/migration-plan/README.md`<br>`implementation/r17/repository-baseline.md`<br>`implementation/r17/requirement-matrix.md`<br>`implementation/r17/schema-changes/README.md`<br>`implementation/r17/security-review.md`<br>... 1 more |
