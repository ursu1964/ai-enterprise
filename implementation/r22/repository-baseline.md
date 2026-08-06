# P32 — R22 repository baseline

- R document: `1/r22.txt`
- R title: R22 defines the **AI-Enterprise Artifact Intelligence and Evidence Graph**.
- Specification hash: `a75b807a225ff7a6106259a153cdf2765753135565c00d02b74a68c3a721ea42`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r22.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/r22_artifact_intelligence_runtime.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/r22_artifact_intelligence_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/r22_artifact_intelligence.py` |
| persistence_or_migration | implemented | `apps/api/src/ai_enterprise/infrastructure/r22/__init__.py`<br>`apps/api/src/ai_enterprise/infrastructure/r22/models.py`<br>`migrations/versions/e7f9a3b2d1c5_add_r22_artifact_intelligence_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/r22_artifact_intelligence_schemas.py`<br>`registry/artifact-types/r22-default.json`<br>`registry/classification-policies/r22-default.json`<br>`registry/lifecycle-policies/r22-promotion-policy.json`<br>`registry/relationship-types/r22-default.json`<br>`registry/retention-policies/r22-default.json`<br>`schemas/artifact-intelligence/artifact-version.schema.json`<br>`schemas/artifact-intelligence/artifact.schema.json`<br>`schemas/artifact-intelligence/evidence-package.schema.json`<br>`schemas/artifact-intelligence/evidence.schema.json`<br>`schemas/artifact-intelligence/provenance.schema.json`<br>`schemas/artifact-intelligence/trace-relationship.schema.json` |
| tests | implemented | `apps/api/tests/test_r22_artifact_intelligence_runtime.py` |
| status_documentation | implemented | `docs/R-AUDIT-02-r1-r22-alignment-matrix.md`<br>`docs/ir/R22-IR-01-constitutional-kernel-evolution-framework.md`<br>`docs/r22-artifact-intelligence-status.md`<br>`implementation/r22/acceptance-evidence.md`<br>`implementation/r22/api-changes/README.md`<br>`implementation/r22/completion-report.md`<br>`implementation/r22/gap-analysis.md`<br>`implementation/r22/implementation-plan.md`<br>`implementation/r22/migration-plan/README.md`<br>`implementation/r22/repository-baseline.md`<br>`implementation/r22/requirement-matrix.md`<br>`implementation/r22/schema-changes/README.md`<br>... 2 more |
