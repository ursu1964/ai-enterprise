# P19 — R9 exact clause verification

Authoritative R source: `1/r9.txt`

This document records the R9 Universal AI-Enterprise Kernel contract against
current repository symbols. It closes P19/R9 by mapping kernel orchestration,
subsystem governance, events, lifecycle, transactions, checkpoints, plugins,
AI sessions, workspace scheduling, resources, SDK contracts, managers,
runtime replay, schedule dispatch, SDK publication, operational readiness,
API routes, and persistence to existing implementation evidence.

| R9 clause | Status | Repository evidence |
|---|---|---|
| The Kernel owns orchestration and all subsystem communication passes through governed kernel records. | implemented | `apps/api/src/ai_enterprise/domain/r9_uak.py`; `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_subsystem_event_lifecycle_transaction_and_checkpoint_are_hashed` |
| Kernel components are represented as specialized managers/subsystems without embedding project business logic. | implemented | `UakSubsystem`; manager records in `apps/api/src/ai_enterprise/domain/r9_uak.py`; R9 domain tests |
| Manifest, registry, knowledge, transformation, artifact, runtime, governance, AI, plugin, security, deployment, and monitoring manager responsibilities are modeled. | implemented | `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_registry_security_deployment_and_monitoring_managers_are_governed`; domain manager record types |
| Kernel events, lifecycle records, transactions, and checkpoints are deterministic and hash-bound. | implemented | `UakKernelEvent`; lifecycle/transaction/checkpoint records; `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_subsystem_event_lifecycle_transaction_and_checkpoint_are_hashed` |
| Direct subsystem access, partial transactions, and invalid checkpoints fail closed. | implemented | `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_rejects_direct_subsystem_access_partial_transactions_and_bad_checkpoints` |
| Plugin registration and AI session boundaries are governed. | implemented | plugin and AI session records in `apps/api/src/ai_enterprise/domain/r9_uak.py`; `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_plugin_registration_and_ai_session_boundaries_are_governed` |
| Workspace scheduling, resource coordination, and SDK contract records are governed. | implemented | `UakSchedulePlan`; resource and SDK records; `apps/api/tests/test_r9_uak_domain.py::test_r9_uak_workspace_scheduling_resource_and_sdk_records_are_governed` |
| Runtime event replay executes verified kernel events in deterministic order and rejects corrupt/unreplayable events. | implemented | `apps/api/src/ai_enterprise/application/r9_uak_runtime.py::replay_kernel_events`; tests `test_r9_runtime_replays_verified_kernel_events_in_order` and `test_r9_runtime_blocks_corrupt_or_unreplayable_events` |
| Scheduler dispatch sends ready schedules once. | implemented | `dispatch_ready_schedules`; `apps/api/tests/test_r9_uak_runtime.py::test_r9_runtime_dispatches_ready_schedules_once` |
| Physical SDK package generation materializes package metadata and source files. | implemented | `materialize_sdk_package`; tests `test_r9_runtime_materializes_physical_sdk_package` and `test_r9_runtime_materializes_typescript_sdk_package_metadata` |
| Operational readiness distinguishes local defaults from required external backends and fails closed when external event bus configuration is missing. | implemented | `r9_operational_readiness`; tests `test_r9_operational_readiness_defaults_to_local_event_bus_and_filesystem_registry` and `test_r9_event_bus_readiness_requires_external_backend_configuration` |
| SDK registry publication records filesystem publication and validates npm dry-run without credential leakage. | implemented | `publish_sdk_package_to_registry`; tests `test_r9_sdk_publication_records_filesystem_publication` and `test_r9_sdk_publication_dry_run_validates_npm_without_leaking_credentials` |
| R9 records are persisted as typed append-only kernel records with organization/project scope, object identity, hash uniqueness, and schema-backed documents. | implemented | `R9KernelRecordModel`; migration `a9c1e4f6b8d2_add_r9_kernel_records.py`; `apps/api/tests/test_r9_uak_persistence.py::test_r9_storage_model_is_append_only_typed_kernel_record_store` |
| R9 dashboard exposes kernel operating metrics. | implemented | `R9KernelDashboardResponse`; `apps/api/tests/test_r9_uak_persistence.py::test_r9_dashboard_response_exposes_kernel_operating_metrics` |
| R9 APIs expose kernel records, subsystem operations, runtime orchestration, dashboard views, and list/query surfaces. | implemented | `apps/api/src/ai_enterprise/api/routes/r9_uak.py`; `apps/api/src/ai_enterprise/api/r9_uak_schemas.py`; `apps/api/tests/test_r9_uak_persistence.py::test_r9_uak_routes_are_exposed_in_openapi` |

## Focused verification

Command:

```bash
cd apps/api && .venv/bin/pytest -q tests/test_r9_uak_domain.py tests/test_r9_uak_persistence.py tests/test_r9_uak_runtime.py tests/test_traceability.py
```

Result:

```text
28 passed
```

## Verdict

P19/R9 is implemented. No exact R9 clause remains blocked or missing in the
current repository baseline.
