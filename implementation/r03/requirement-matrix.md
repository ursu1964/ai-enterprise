# P13 — R3 requirement matrix

This matrix maps the R requirement areas to repository evidence.

| Requirement area | Status | Evidence |
|---|---|---|
| source_specification | implemented | `1/r3.txt` |
| domain_or_runtime | implemented | `apps/api/src/ai_enterprise/application/project_formation_service.py` |
| api_contract | implemented | `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`<br>`apps/api/src/ai_enterprise/api/project_formation_schemas.py` |
| api_route | implemented | `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`<br>`apps/api/src/ai_enterprise/api/routes/project_formation.py` |
| persistence_or_migration | implemented | `migrations/versions/0d4c2f9a7b81_add_r2_project_formation_records.py` |
| schema_or_registry | implemented | `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`<br>`apps/api/src/ai_enterprise/api/project_formation_schemas.py` |
| tests | implemented | `apps/api/tests/test_project_formation.py` |
| status_documentation | implemented | `docs/adrs/0006-specialized-project-formation-agents.md`<br>`docs/architecture/project-formation-orchestration.md`<br>`docs/reference-architecture/17-project-formation-orchestration/README.md`<br>`implementation/r03/acceptance-evidence.md`<br>`implementation/r03/api-changes/README.md`<br>`implementation/r03/completion-report.md`<br>`implementation/r03/gap-analysis.md`<br>`implementation/r03/implementation-plan.md`<br>`implementation/r03/migration-plan/README.md`<br>`implementation/r03/repository-baseline.md`<br>`implementation/r03/requirement-matrix.md`<br>`implementation/r03/schema-changes/README.md`<br>... 2 more |
