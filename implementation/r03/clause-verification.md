# P13 — R3 exact clause verification

Authoritative R source: `1/r3.txt`

This document records the R3 implementation baseline against current repository
symbols. It closes P13/R3 by mapping the deterministic foundation workflow to
existing code, schemas, migrations, examples, and tests.

| R3 clause | Status | Repository evidence |
|---|---|---|
| Accept an AEPM v0.1 manifest in JSON or YAML. | implemented | `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`; `apps/api/src/ai_enterprise/application/project_formation_service.py`; `examples/sample-project/aepm-0.1.json`; `examples/valid/inventory-management.aepm.yaml`; `apps/api/tests/test_r3_foundation_api.py`; `apps/api/tests/test_r3_foundation_specification.py` |
| Validate the manifest against a formal JSON Schema and reject structurally invalid manifests. | implemented | `specifications/aepm/AEPM-0.1.schema.json`; `specifications/AEPM-0.1.schema.json`; `apps/api/src/ai_enterprise/domain/aepm.py`; `apps/api/src/ai_enterprise/domain/aepm_validation.py`; `examples/invalid/incomplete-inventory-management.aepm.yaml`; `apps/api/tests/test_aepm_manifest.py`; `apps/api/tests/test_aepm_validation.py` |
| Convert a valid manifest into canonical AEIR objects. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `specifications/aeir/AEIR-0.1.schema.json`; `specifications/AEIR-0.1.schema.json`; `apps/api/tests/test_aeir_model.py` |
| Create first-class canonical relationships between objects. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `specifications/aeir/RELATIONSHIP-0.1.schema.json`; `specifications/RELATIONSHIP-0.1.schema.json`; `apps/api/tests/test_r3_foundation_specification.py`; `apps/api/tests/test_aeir_model.py` |
| Execute deterministic validation rules and produce structured validation findings. | implemented | `apps/api/src/ai_enterprise/domain/aepm_validation.py`; `specifications/validation/VALIDATION-FINDING-0.1.schema.json`; `specifications/VALIDATION-0.1.md`; `apps/api/tests/test_aepm_validation.py`; `apps/api/tests/test_r3_foundation_api.py::test_r3_foundation_validation_run_persists_structured_findings` |
| Persist the project, canonical objects, relationships, sources, versions, validation findings, and snapshots. | implemented | `apps/api/src/ai_enterprise/application/project_formation_service.py`; `apps/api/src/ai_enterprise/infrastructure/knowledge/aeir_repository.py`; `apps/api/src/ai_enterprise/infrastructure/knowledge/models.py`; `migrations/versions/0d4c2f9a7b81_add_r2_project_formation_records.py`; `migrations/versions/f3a7c1d9e204_add_aeir_knowledge_storage.py`; `apps/api/tests/test_aeir_knowledge_storage.py` |
| Create immutable project snapshots and reconstruct exact project state from a snapshot. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`; `specifications/SNAPSHOT-0.1.schema.json`; `apps/api/tests/test_r3_foundation_api.py::test_r3_foundation_snapshot_route_creates_immutable_snapshot`; `apps/api/tests/test_r3_foundation_api.py::test_r3_foundation_snapshot_route_reconstructs_model` |
| Retain traceability from every canonical object to its source manifest location. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py`; `apps/api/src/ai_enterprise/domain/traceability.py`; `specifications/TRACEABILITY-0.1.md`; `specifications/SOURCE-0.1.schema.json`; `apps/api/tests/test_traceability.py`; `apps/api/tests/test_aeir_model.py` |
| Provide manifest import, validation, and snapshot APIs. | implemented | `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`; `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`; `apps/api/tests/test_r3_foundation_api.py::test_r3_foundation_openapi_exposes_minimal_project_endpoints` |
| Exclude AI extraction, document generation, code generation, orchestration, deployment, graph database, marketplace, and autonomous approval from R3. | implemented | `specifications/MVP-NON-GOALS-0.1.md`; deterministic R3 tests do not require LLM/provider execution; `apps/api/tests/test_r2_specification_contracts.py::test_mvp_non_goals_exclude_expansive_v01_behaviors` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q \
  tests/test_r3_foundation_specification.py \
  tests/test_r3_foundation_api.py \
  tests/test_project_formation.py \
  tests/test_aeir_knowledge_storage.py \
  tests/test_aeir_model.py \
  tests/test_aepm_manifest.py \
  tests/test_aepm_validation.py
```

Result:

```text
56 passed
```

## Verdict

P13/R3 is implemented. No exact R3 clause remains blocked or missing in the
current repository baseline.
