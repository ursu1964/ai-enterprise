# P12 — R2 repository baseline

- R document: `1/r2.txt`
- R title: R2 — Foundational Domain and Manifest Concepts
- Specification hash: `12ca73363f6faccabb7b45f4c5dc8d1202768294512dc2f3650a6e0a765d9d4c`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r2.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/project_formation_service.py`<br>`apps/api/src/ai_enterprise/domain/aeir.py`<br>`apps/api/src/ai_enterprise/domain/aepm.py`<br>`apps/api/src/ai_enterprise/domain/aepm_interpretation.py`<br>`apps/api/src/ai_enterprise/domain/aepm_validation.py`<br>`apps/api/src/ai_enterprise/domain/clarification.py`<br>`apps/api/src/ai_enterprise/domain/traceability.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/project_formation_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/project_formation.py` |
| persistence_or_migration | implemented | `apps/api/src/ai_enterprise/infrastructure/knowledge/aeir_repository.py`<br>`migrations/versions/0d4c2f9a7b81_add_r2_project_formation_records.py`<br>`migrations/versions/1f2a3b4c5d6e_align_r4_aeir_promotion_schema.py`<br>`migrations/versions/5b8e1f7c3a29_add_aeir_source_evidence_links.py`<br>`migrations/versions/9b2e7c4f6a10_scope_aeir_model_hash_to_project.py`<br>`migrations/versions/f3a7c1d9e204_add_aeir_knowledge_storage.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/project_formation_schemas.py`<br>`specifications/AEIR-0.1.schema.json`<br>`specifications/AEPM-0.1.schema.json`<br>`specifications/CLARIFICATION-QUESTION-0.1.schema.json`<br>`specifications/aeir/AEIR-0.1.schema.json`<br>`specifications/aeir/RELATIONSHIP-0.1.schema.json`<br>`specifications/aepm/AEPM-0.1.schema.json` |
| tests | implemented | `apps/api/tests/test_aeir_knowledge_storage.py`<br>`apps/api/tests/test_aeir_model.py`<br>`apps/api/tests/test_aepm_interpretation.py`<br>`apps/api/tests/test_aepm_manifest.py`<br>`apps/api/tests/test_aepm_validation.py`<br>`apps/api/tests/test_clarification_engine.py`<br>`apps/api/tests/test_project_formation.py`<br>`apps/api/tests/test_traceability.py` |
| status_documentation | implemented | `docs/adrs/0006-specialized-project-formation-agents.md`<br>`docs/architecture/project-formation-orchestration.md`<br>`docs/reference-architecture/17-project-formation-orchestration/README.md`<br>`implementation/r02/acceptance-evidence.md`<br>`implementation/r02/api-changes/README.md`<br>`implementation/r02/completion-report.md`<br>`implementation/r02/gap-analysis.md`<br>`implementation/r02/implementation-plan.md`<br>`implementation/r02/migration-plan/README.md`<br>`implementation/r02/repository-baseline.md`<br>`implementation/r02/requirement-matrix.md`<br>`implementation/r02/schema-changes/README.md`<br>... 2 more |
