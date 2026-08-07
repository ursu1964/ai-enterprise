# P20 — R10 exact clause verification

Authoritative R source: `1/r10.txt`

Additional reconciled implementation-ready contract:
`docs/ir/R10-IR-01-verification-validation-engine.md`

This document records the P20/R10 reconciliation against current repository
symbols. The repository contains two intentional R10 surfaces:

- R10 UEIF: Universal Experience and Interaction Framework from `1/r10.txt`.
- BK/R10 VVE: Verification and Validation Engine from the later IR contract.

The reconciliation preserves both instead of replacing one with the other.

## R10 UEIF clause mapping

| R10 clause | Status | Repository evidence |
|---|---|---|
| Interfaces never own project information; the Manifest remains the project source of truth. | implemented | `apps/api/src/ai_enterprise/domain/r10_ueif.py`; `apps/api/tests/test_r10_ueif_domain.py::test_r10_role_workspace_preserves_manifest_ownership_boundary` |
| Role-based workspaces expose different perspectives without changing data ownership. | implemented | `create_role_workspace`; `apps/api/tests/test_r10_ueif_domain.py::test_r10_role_workspace_preserves_manifest_ownership_boundary` |
| Manifest Studio and visual modeling are controlled interfaces over manifest-backed objects. | implemented | manifest studio and visual model records in `apps/api/src/ai_enterprise/domain/r10_ueif.py`; `apps/api/tests/test_r10_ueif_domain.py::test_r10_manifest_studio_and_visual_model_are_controlled_manifest_interfaces` |
| AI proposals require explicit human approval before affecting governed state. | implemented | AI proposal and approval workspace records; `apps/api/tests/test_r10_ueif_domain.py::test_r10_ai_proposals_and_approvals_require_human_review` |
| Search, explainability, profiles, traceability, and collaboration are platform-derived interaction records. | implemented | `apps/api/tests/test_r10_ueif_domain.py::test_r10_search_explainability_profile_traceability_and_collaboration` |
| Notifications, dashboards, navigation, and documentation surfaces are derived from platform state. | implemented | `apps/api/tests/test_r10_ueif_domain.py::test_r10_notifications_dashboards_navigation_and_docs_are_platform_derived` |
| Workspace surfaces, AI interaction constraints, and experience API contracts are explicit. | implemented | `apps/api/tests/test_r10_ueif_domain.py::test_r10_workspace_surfaces_ai_constraints_and_experience_api_are_explicit` |
| R10 experience records are persisted append-only with project scope and hash uniqueness. | implemented | migration `b3e6f9a1c4d7_add_r10_experience_records.py`; `apps/api/tests/test_r10_ueif_persistence.py::test_r10_storage_model_is_append_only_project_experience_record_store` |
| R10 UEIF APIs expose role workspaces, manifest studio sessions, visual models, search, AI proposals, approvals, explainability, profiles, traceability, collaboration, notifications, dashboards, navigation, docs, workspace surfaces, AI policies, and API contracts. | implemented | `apps/api/src/ai_enterprise/api/routes/r10_ueif.py`; `apps/api/src/ai_enterprise/api/r10_ueif_schemas.py`; `apps/api/tests/test_r10_ueif_persistence.py::test_r10_ueif_routes_are_exposed_in_openapi` |

## BK/R10 VVE clause mapping

| BK/R10 clause | Status | Repository evidence |
|---|---|---|
| Verification campaigns bind exact handoff and baseline references. | implemented | `bk_r10_create_campaign`; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_campaign_binds_exact_handoff_and_baselines` |
| Entry gates require a verified environment before campaign start. | implemented | `bk_r10_start_campaign`; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_entry_requires_verified_environment` |
| No evidence, no pass; silent omission is blocked. | implemented | result recording and verdict logic; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_no_evidence_no_pass_and_no_silent_omission` |
| Passed obligations require evidence and can generate a positive structured verdict. | implemented | `bk_r10_record_result`; `bk_r10_generate_verdict`; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_records_pass_only_with_evidence_and_generates_positive_verdict` |
| Failed results remain visible after retry and flaky retry blocks unqualified verdicts. | implemented | retry/flaky classification in `apps/api/src/ai_enterprise/application/bk_r10_verification_runtime.py`; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_failed_result_remains_visible_and_flaky_retry_blocks_verdict` |
| Waivers require scope, risk, expiry, authority, and compensating controls. | implemented | `bk_r10_apply_waiver`; `apps/api/tests/test_bk_r10_verification_runtime.py::test_bk_r10_governed_waiver_requires_scope_risk_expiry_and_controls` |
| Verification contracts, JSON schemas, registries, policies, and conformance reports are published and validated. | implemented | `schemas/verification/*.schema.json`; `registry/verification-*/*.json`; `apps/api/tests/test_bk_r10_verification_contracts.py` |
| Persistence uses JSONB documents, query indexes, append-only tables, and migration after R22. | implemented | `apps/api/src/ai_enterprise/infrastructure/bk_r10/models.py`; migration `f8a6c2d4e9b1_add_bk_r10_verification_records.py`; `apps/api/tests/test_bk_r10_verification_persistence.py` |
| External verification readiness fails closed for production mock backends and missing credentials. | implemented | `bk_r10_external_readiness`; tests `test_bk_r10_external_readiness_fails_closed_for_production_mock_backend`, `test_bk_r10_external_execution_blocks_unready_production_backend` |
| Mock and HTTP adapters execute provider-neutral verification and reject invalid provider payloads. | implemented | `bk_r10_execute_external_verification`; `bk_r10_http_verification_adapter`; tests `test_bk_r10_external_mock_execution_returns_obligation_evidence`, `test_bk_r10_http_adapter_executes_provider_neutral_verification`, `test_bk_r10_http_adapter_rejects_invalid_provider_payload` |
| BK/R10 APIs expose contract, conformance, handoff/campaign, external readiness, and external execution endpoints. | implemented | `apps/api/src/ai_enterprise/api/routes/bk_r10_verification.py`; `apps/api/src/ai_enterprise/api/bk_r10_verification_schemas.py`; BK/R10 route tests |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q tests/test_r10_ueif_domain.py tests/test_r10_ueif_persistence.py tests/test_bk_r10_verification_contracts.py tests/test_bk_r10_verification_persistence.py tests/test_bk_r10_verification_runtime.py tests/test_traceability.py
```

Result:

```text
45 passed
```

## Verdict

P20/R10 is implemented. No exact R10 UEIF clause or BK/R10 verification clause
remains blocked or missing in the current repository baseline.
