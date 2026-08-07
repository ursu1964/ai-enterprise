# P17 — R7 exact clause verification

Authoritative R source: `1/r7.txt`

This document records the R7 Universal Execution and Runtime Model contract
against current repository symbols. It closes P17/R7 by mapping runtime
execution, health, events, workflows, synchronization, policy, provider,
observability, and governance clauses to existing domain code, API routes,
migrations, and tests.

| R7 clause | Status | Repository evidence |
|---|---|---|
| Runtime never becomes the source of truth; runtime deployments bind back to manifest, R6 build, and generated artifact hashes. | implemented | `apps/api/src/ai_enterprise/domain/r7_uerm.py::register_uerm_runtime_deployment`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_registers_deterministic_runtime_deployment` |
| Every runtime exposes mandatory operational capabilities: configuration, health, logging, audit, authorization, events, metrics, tracing, diagnostics, and lifecycle management. | implemented | `UermRuntimeDeployment`; `R7RuntimeDeploymentModel`; `apps/api/tests/test_r7_uerm_persistence.py::test_r7_storage_models_cover_runtime_registry_health_and_events` |
| Execution context carries standardized request, correlation, tenant, user, role, permission, locale, timezone, manifest version, and application version fields. | implemented | `UermExecutionContext`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_runtime_events_include_standard_context_and_hashes` |
| Business operations follow a governed execution pipeline with authentication, authorization, validation, business rules, workflow, persistence, events, audit, and response semantics. | implemented | `UermRuntimeEvent`; `UermPolicyEvaluation`; `UermRuntimeAuditRecord`; runtime route schemas; R7 domain and persistence tests |
| Workflow instances are state-machine driven and reject illegal transitions. | implemented | `UermWorkflowInstance`; workflow transition validation in `apps/api/src/ai_enterprise/domain/r7_uerm.py`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_workflow_runtime_rejects_illegal_transitions` |
| Health reports derive runtime status from component checks rather than handwritten status claims. | implemented | `uerm_health_report`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_health_report_status_is_derived_from_component_checks` |
| Runtime events are hash-bound, context-bound, and traceable. | implemented | `record_uerm_runtime_event`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_runtime_events_include_standard_context_and_hashes` |
| Runtime integrity validation rejects tampered runtime hashes. | implemented | `verify_uerm_runtime_deployment`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_rejects_tampered_runtime_hashes` |
| Compatibility checks detect manifest/runtime/application drift and outdated runtime versions. | implemented | `uerm_compatibility_report`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_compatibility_detects_outdated_runtime_versions` |
| Runtime errors, recovery actions, and digital-twin snapshots are deterministic and hash-bound. | implemented | `record_uerm_runtime_error`; `plan_uerm_recovery_action`; `create_uerm_digital_twin_snapshot`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_standard_errors_recovery_and_digital_twin_are_hashed` |
| Runtime providers, policy evaluations, event dispatch, governed AI requests, and plugin bindings are represented as production integration contracts. | implemented | `register_uerm_runtime_provider`; `evaluate_uerm_runtime_policy`; `dispatch_uerm_event`; `record_uerm_runtime_ai_request`; `bind_uerm_plugin`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_runtime_providers_policy_dispatch_ai_and_plugins_are_realized` |
| Runtime configuration snapshots, audit records, telemetry batches, and governance traces are hash-bound and persisted. | implemented | `record_uerm_runtime_configuration_snapshot`; `record_uerm_runtime_audit`; `record_uerm_runtime_telemetry`; `record_uerm_runtime_governance_trace`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_runtime_configuration_audit_telemetry_and_governance_are_hashed` |
| Runtime synchronization and upgrade planning keep deployed runtime state aligned with manifest/runtime baselines. | implemented | `create_uerm_runtime_synchronization_report`; `plan_uerm_runtime_upgrade`; `apps/api/tests/test_r7_uerm_domain.py::test_r7_uerm_runtime_synchronization_and_upgrade_plans_are_hashed` |
| R7 records are persisted with JSONB contracts, foreign keys, uniqueness, indexes, and append-only runtime evidence. | implemented | migrations `8d2f6a1c9b3e_add_r7_uerm_records.py`, `9e4a7c2d5f6b_add_r7_runtime_operations.py`, `a6f1b8c3d9e2_add_r7_runtime_realization.py`, `b7c2d9e4f1a6_add_r7_runtime_observability_governance.py`, `d1f4a7c9e2b6_add_r7_runtime_registry_location.py`, `e2a9c4f7b1d3_add_r7_production_runtime_integration.py`; `apps/api/tests/test_r7_uerm_persistence.py` |
| R7 APIs expose runtime deployments, health, events, compatibility, workflows, errors, recovery, digital twin snapshots, providers, policy, dispatch, AI requests, plugin bindings, audit, telemetry, synchronization, and upgrade plans. | implemented | `apps/api/src/ai_enterprise/api/routes/r7_uerm.py`; `apps/api/src/ai_enterprise/api/r7_uerm_schemas.py`; `apps/api/tests/test_r7_uerm_persistence.py::test_r7_uerm_routes_are_exposed_in_openapi` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q tests/test_r7_uerm_domain.py tests/test_r7_uerm_persistence.py tests/test_traceability.py
```

Result:

```text
21 passed
```

## Verdict

P17/R7 is implemented. No exact R7 clause remains blocked or missing in the
current repository baseline.
