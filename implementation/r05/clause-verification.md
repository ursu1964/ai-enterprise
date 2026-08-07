# P15 — R5 exact clause verification

Authoritative R source: `1/r5.txt`

This document records the R5 Universal Manifest Transformation Engine contract
against current repository symbols. It closes P15/R5 by mapping the
transformation pipeline to existing domain code, API routes, migrations,
generated artifacts, export bundles, and tests.

| R5 clause | Status | Repository evidence |
|---|---|---|
| Manifest-derived outputs are transformations, not inventions. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_emits_deterministic_registry_bound_artifact_specs` |
| Layer 1 semantic validation blocks generation until the manifest and canonical model are valid. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::verify_umte_transformation`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_fails_closed_on_unregistered_artifact_specs`; R2/R3 validation tests |
| Layer 2 normalization uses canonical AEIR objects as the downstream source. | implemented | `apps/api/src/ai_enterprise/domain/aeir.py::compile_aepm`; `apps/api/src/ai_enterprise/domain/r5_umte.py::compile_umte_transformation`; `apps/api/tests/test_aeir_model.py`; `apps/api/tests/test_r5_umte_domain.py` |
| Layer 3 dependency resolution derives affected/generated artifacts from object dependencies. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::affected_umte_artifact_keys`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_incremental_regeneration_marks_changed_object_dependencies` |
| Layer 4 object expansion derives lifecycle, permissions, validation, APIs, events, tests, docs, and related specs from registry rules. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::default_registry_rules`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_expands_entity_into_data_api_ui_security_events_tests_and_docs` |
| Layer 5 artifact generation produces deterministic generated artifact records. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::compile_umte_transformation`; `R5GeneratedArtifactModel`; `migrations/versions/4d9e2f7a6b1c_add_r5_generated_artifacts.py`; R5 domain and persistence tests |
| Layer 6 verification fails closed on registry, hash, or provenance drift. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::verify_umte_transformation`; tests `test_r5_umte_fails_closed_on_unregistered_artifact_specs` and `test_r5_umte_artifact_hash_tampering_fails_validation` |
| Generated artifacts preserve source traceability and bind to exact source model/manifest hashes. | implemented | `UmteArtifactProvenance` in `apps/api/src/ai_enterprise/domain/r5_umte.py`; tests assert `source_model_sha256`, `source_manifest_sha256`, and `source_artifact_spec_hash`; `apps/api/tests/test_traceability.py` |
| Production generation requires an approved snapshot gate. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::require_approved_snapshot`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_production_generation_requires_approved_snapshot_gate` |
| Transformation runs, artifacts, reports, and export bundles are persisted as append-only records. | implemented | migrations `3c8d1e4f6a7b_add_r5_umte_records.py`, `4d9e2f7a6b1c_add_r5_generated_artifacts.py`, `5e1a9c8d2f4b_add_r5_export_bundles.py`; R5 infrastructure models; `apps/api/tests/test_r5_umte_persistence.py` |
| Export bundles are deterministic, hash-bound, and include generated artifact entries. | implemented | `apps/api/src/ai_enterprise/domain/r5_umte.py::compile_umte_export_bundle`; `UmteExportBundle`; `apps/api/tests/test_r5_umte_domain.py::test_r5_umte_export_bundle_is_deterministic_and_hash_bound` |
| UMTE APIs expose transformation creation, retrieval, and export bundle creation. | implemented | `apps/api/src/ai_enterprise/api/routes/r5_umte.py`; `apps/api/src/ai_enterprise/api/r5_umte_schemas.py`; `apps/api/tests/test_r5_umte_persistence.py::test_r5_umte_routes_are_exposed_in_openapi` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q tests/test_r5_umte_domain.py tests/test_r5_umte_persistence.py tests/test_traceability.py tests/test_r3_foundation_api.py
```

Result:

```text
24 passed
```

## Verdict

P15/R5 is implemented. No exact R5 clause remains blocked or missing in the
current repository baseline.
