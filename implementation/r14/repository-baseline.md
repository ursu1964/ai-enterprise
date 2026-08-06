# P24 — R14 repository baseline

- R document: `1/r14.txt`
- R title: R14 — Executable AI-Enterprise Manifest Schema
- Specification hash: `50e47ef2850f6960464a8e87dd0e58f4e1f7a0d3ca6be58731f3c370377e4cb4`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

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
