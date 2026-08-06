# P24 — R14 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r14.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r14_manifest_schema_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r14_manifest_schema_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r14_manifest_schema.py` |
| persistence_or_migration | verified_not_applicable | No separate repository artifact required; verified as not applicable. |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r14_manifest_schema_schemas.py`<br>`manifest/crm.r14.json`<br>`manifest/invalid-technical.r14.json`<br>`schemas/Manifest.schema.json` |
| tests | implemented | `apps/api/tests/test_r14_manifest_schema_runtime.py` |
| status_documentation | implemented | `docs/ir/R14-IR-01-agent-framework.md`<br>`docs/r14-manifest-schema-status.md`<br>`implementation/r14/acceptance-evidence.md`<br>`implementation/r14/api-changes/README.md`<br>`implementation/r14/completion-report.md`<br>`implementation/r14/gap-analysis.md`<br>`implementation/r14/implementation-plan.md`<br>`implementation/r14/migration-plan/README.md`<br>`implementation/r14/repository-baseline.md`<br>`implementation/r14/requirement-matrix.md`<br>`implementation/r14/schema-changes/README.md`<br>`implementation/r14/security-review.md`<br>... 1 more |
