# P28 — R18 repository baseline

- R document: `1/r18.txt`
- R title: R18 — AI-Enterprise Generator Orchestration Framework
- Specification hash: `a0c48d2388e4c450bc4f436f14f0e99e9b9315942e89db91ddcf6bd61ac9221b`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r18.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r18_generator_orchestration_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r18_generator_orchestration_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r18_generator_orchestration.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r18_generator_orchestration_schemas.py` |
| tests | implemented | `apps/api/tests/test_r18_generator_orchestration_runtime.py`<br>`apps/api/tests/test_r18_live_provider_smoke.py` |
| status_documentation | implemented | `docs/r18-generator-orchestration-status.md`<br>`docs/runbooks/r18-live-provider-orchestration.md`<br>`implementation/r18/acceptance-evidence.md`<br>`implementation/r18/api-changes/README.md`<br>`implementation/r18/completion-report.md`<br>`implementation/r18/gap-analysis.md`<br>`implementation/r18/implementation-plan.md`<br>`implementation/r18/migration-plan/README.md`<br>`implementation/r18/repository-baseline.md`<br>`implementation/r18/requirement-matrix.md`<br>`implementation/r18/schema-changes/README.md`<br>`implementation/r18/security-review.md`<br>... 1 more |
