# P16 — R6 exact clause verification

Authoritative R source: `1/r6.txt`

This document records the R6 Universal Artifact Generation Framework contract
against current repository symbols. It closes P16/R6 by mapping the artifact
factory clauses to existing domain code, API routes, migrations, repository
publication adapters, validation gates, lifecycle rules, and tests.

| R6 clause | Status | Repository evidence |
|---|---|---|
| R6 consumes validated R5 transformation/export output and does not reinterpret business intent. | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py::compile_uagf_generation`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_generates_deterministic_verified_file_build_from_r5_bundle` |
| Artifact categories are generated as technology-specific deliverables from deterministic generator logic. | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py::_render_content`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_typed_generators_emit_target_specific_contracts` |
| Every generated file has stable identity, metadata, generator/template/version traceability, dependency metadata, and content hash. | implemented | `UagfGeneratedFile`; `UagfBuildManifest`; file/build hash helpers in `apps/api/src/ai_enterprise/domain/r6_uagf.py`; R6 domain tests |
| Generation produces a reproducible Build Manifest binding generated files, checksums, dependencies, source bundle, and validation report. | implemented | `UagfBuildManifest`; `UagfGenerationResult`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_generates_deterministic_verified_file_build_from_r5_bundle` |
| Validation gates reject unsafe paths, hash tampering, missing R5 payload coverage, dependency drift, target path drift, and invalid target syntax. | implemented | `validate_uagf_files`; `_validate_target_syntax`; `_artifact_consistency_findings`; tests `test_r6_uagf_rejects_file_hash_tampering_and_unsafe_paths`, `test_r6_uagf_requires_artifacts_to_match_export_bundle`, `test_r6_uagf_validation_enforces_cross_artifact_consistency`, `test_r6_uagf_validation_blocks_dependency_coverage_drift`, `test_r6_uagf_validation_blocks_target_path_drift`, `test_r6_uagf_validation_blocks_invalid_json_target_syntax`, `test_r6_uagf_validation_blocks_invalid_python_target_syntax` |
| Cross-artifact consistency is verified across generated outputs for shared source objects and dependencies. | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py::_artifact_consistency_findings`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_validation_enforces_cross_artifact_consistency` |
| Incremental regeneration computes impact and reuses unchanged generated files. | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py::plan_uagf_regeneration`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_incremental_regeneration_reuses_unchanged_files` |
| Regeneration preserves developer-owned custom regions. | implemented | `apps/api/src/ai_enterprise/domain/r6_uagf.py::preserve_uagf_custom_regions`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_incremental_regeneration_preserves_custom_regions` |
| Artifact lifecycle requires review and approval before publication. | implemented | `transition_uagf_lifecycle`; `current_uagf_lifecycle_status`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_lifecycle_requires_review_approval_before_publish` |
| Generator packs are certified, versioned, installable, multi-technology, and hash-bound. | implemented | `certified_uagf_generator_packs`; `install_uagf_generator_pack`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_certified_generator_packs_support_multi_technology_factory` |
| Parallel generation planning is represented as a deterministic, hash-bound execution plan. | implemented | `plan_parallel_uagf_generation`; `UagfParallelGenerationPlan`; `apps/api/tests/test_r6_uagf_domain.py::test_r6_uagf_parallel_gates_and_repository_publication_are_hashed` |
| Artifact repository publication supports filesystem/git/S3/package-registry readiness and fail-closed backend configuration. | implemented | `publish_uagf_artifacts_to_repository`; `apps/api/src/ai_enterprise/api/routes/r6_uagf.py::_materialize_repository_publication`; `_artifact_repository_readiness`; persistence tests for git, S3, and package registry readiness |
| R6 records are persisted with JSONB contracts, foreign keys, uniqueness, and append-only lifecycle/build evidence. | implemented | migrations `6a2b8c9d1e5f_add_r6_uagf_records.py`, `7c4e2a9b8d1f_add_r6_lifecycle_events.py`, `c8d3e7f1a9b2_add_r6_production_factory_layer.py`; `apps/api/tests/test_r6_uagf_persistence.py` |
| R6 APIs expose generation, regeneration, lifecycle transitions/events, pack marketplace/installations, parallel plans, validation gates, repository readiness, and publication. | implemented | `apps/api/src/ai_enterprise/api/routes/r6_uagf.py`; `apps/api/src/ai_enterprise/api/r6_uagf_schemas.py`; `apps/api/tests/test_r6_uagf_persistence.py::test_r6_uagf_routes_are_exposed_in_openapi` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q tests/test_r6_uagf_domain.py tests/test_r6_uagf_persistence.py tests/test_traceability.py
```

Result:

```text
30 passed
```

## Verdict

P16/R6 is implemented. No exact R6 clause remains blocked or missing in the
current repository baseline.
