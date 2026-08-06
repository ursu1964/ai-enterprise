# P13 — R3 repository baseline

- R document: `1/r3.txt`
- R title: R3 should convert R1 and R2 into the first executable implementation specification. It should define exactly what the engineering team builds before introducing the frontend, document generators, or AI interpretation.
- Specification hash: `2802b5e715579548069f1c3ae88ef7b6a7d6ed11e0da0810b7c98915403436db`
- Repository baseline: existing AI-Enterprise architecture.
- Source root: `apps/api/src`.
- Rule: do not create a second root-level application source tree.

## Evidence summary

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r3.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/project_formation_service.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`<br>`apps/api/src/ai_enterprise/api/project_formation_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`<br>`apps/api/src/ai_enterprise/api/routes/project_formation.py` |
| persistence_or_migration | implemented | `migrations/versions/0d4c2f9a7b81_add_r2_project_formation_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`<br>`apps/api/src/ai_enterprise/api/project_formation_schemas.py` |
| tests | implemented | `apps/api/tests/test_project_formation.py` |
| status_documentation | implemented | `docs/adrs/0006-specialized-project-formation-agents.md`<br>`docs/architecture/project-formation-orchestration.md`<br>`docs/ir/R03-IR-01-registry-foundations-executable-foundation.md`<br>`docs/reference-architecture/17-project-formation-orchestration/README.md`<br>`implementation/r03/acceptance-evidence.md`<br>`implementation/r03/api-changes/README.md`<br>`implementation/r03/completion-report.md`<br>`implementation/r03/gap-analysis.md`<br>`implementation/r03/implementation-plan.md`<br>`implementation/r03/migration-plan/README.md`<br>`implementation/r03/repository-baseline.md`<br>`implementation/r03/requirement-matrix.md`<br>... 3 more |
