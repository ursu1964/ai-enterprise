# P31 — R21 exact clause verification

Status: COMPLETE  
Scope: `1/r21.txt` — Execution Orchestrator and Universal Project Generation Pipeline  
Verification date: 2026-08-07

## Source reconciliation

| Source | Role | Decision |
|---|---|---|
| `1/r21.txt` | Authoritative product-platform R21 contract | Verified as Execution Orchestrator and Universal Project Generation Pipeline. |
| `docs/ir/R21-IR-01-platform-administration-operations.md` | Later implementation-ready IR contract | Preserved as Platform Administration and Operations architecture. It explicitly does not replace product-platform R21. |

R21 is closed against the execution-orchestrator contract. Platform administration and operations remain a separate IR architecture contract and are not a missing R21 execution-orchestrator item.

## Clause-to-symbol verification

| R21 clause | Requirement | Repository evidence | Status |
|---|---|---|---|
| 1. Purpose | Convert approved Manifest into controlled, observable, resumable, auditable project-generation execution. | `r21_compile_project`; `r21_create_execution_plan`; `r21_start_execution`; delivery-package tests | IMPLEMENTED |
| 2. Architectural Position | Coordinate validation, registry resolution, compilation, planning, workers, artifacts, evidence, delivery without bypassing governance. | R15/R16/R17 integration inside compilation; worker requests; evidence records; delivery package | IMPLEMENTED |
| 3. Core Responsibilities / Manifest intake | Accept only valid Manifest with project ID, schema, objectives, constraints, acceptance/governance/delivery data. | `r21_compile_project`; invalid-manifest test; schema validation via R15 | IMPLEMENTED |
| 3.2 Project compilation | Compile Manifest into executable project model with metadata, stakeholders, requirements, policies, work, dependencies, approvals, evidence, permissions. | `R21ProjectCompilation`; `_compiled_model` | IMPLEMENTED |
| 3.3 Dependency graph construction | Represent executable project as DAG of work packages and dependency/evidence/approval edges. | `R21ExecutionPlan.dependency_edges`; `_parallel_groups`; dependency-order tests | IMPLEMENTED |
| 4.1 Manifest-driven execution | Every work package has traceable Manifest relationship; untraceable work rejected. | `R21ManifestTrace`; `_manifest_sources`; traceability assertions | IMPLEMENTED |
| 4.2 Bounded autonomy | Worker tasks define inputs, tools, repositories, outputs, resource/time limits, prohibited behavior, validators, approvals. | `R21WorkPackage`; `R21WorkPackagePermissions`; `_worker_request` | IMPLEMENTED |
| 4.3 Evidence before completion | Task completion requires artifacts, validators, traceability, provenance, evidence, approvals. | `_complete_package`; `R21ValidationResult`; `R21EvidenceRecord`; delivery-package test | IMPLEMENTED |
| 4.4 Deterministic control | Deterministic state transitions, eligibility, dependencies, approvals, retries, rollback/promotion. | immutable models; deterministic hashes; sorted scheduling; retry tests | IMPLEMENTED |
| 4.5 Human authority | Human approval remains mandatory for high-impact decisions. | `R21ApprovalGate`; `r21_apply_approval`; human approval/rejection tests | IMPLEMENTED |
| 5.1 Project states | Explicit project execution state machine. | `PROJECT_STATES`; execution/pause/cancel/resume tests | IMPLEMENTED |
| 5.2 Work-package states | Explicit work-package lifecycle. | `WORK_PACKAGE_STATES`; mutation and retry/remediation tests | IMPLEMENTED |
| 5.3 State-transition requirements | Transitions record previous/new state, actor, event, reason/evidence, correlation. | `R21StateTransition`; `_transition`; tests assert transitions | IMPLEMENTED |
| 6. Executable Work Package | Work package is smallest controlled unit with required structure. | `R21WorkPackage`; `_work_packages`; contract endpoint | IMPLEMENTED |
| 7. Execution Plan Generation | Generate plan from Manifest, Registry, policies, workers, environment, delivery, risk. | `r21_create_execution_plan`; strategy/phases/gates/parallel groups | IMPLEMENTED |
| 7.1 Execution plan contents | Plan includes IDs, snapshots, strategy, phases, work packages, approval gates. | `R21ExecutionPlan`; plan tests | IMPLEMENTED |
| 8. Worker Contract | Workers use common request/response-style contract; invalid responses rejected by validation. | `R21WorkerRequest`; `R21ValidationResult`; validation-failure test | IMPLEMENTED |
| 9. Specialized Worker Categories | Support constrained definition, architecture/engineering, quality, delivery workers. | `WORKER_TYPES`; generated vertical-slice workers | IMPLEMENTED |
| 10. Scheduling and Parallel Execution | Dependency/approval/resource/policy eligibility, parallel groups, retry/cancel/remediation. | `_run_until_blocked_or_complete`; `_parallel_groups`; scheduler tests | IMPLEMENTED |
| 11. Retry and Remediation Policy | Controlled retries, retry records, max attempts, remediation states. | `R21RetryRecord`; `_retry`; `r21_retry_work_package`; validation-failure tests | IMPLEMENTED |
| 12. Human Approval Gates | Executable governance object; approvals bound to exact artifact versions and invalidated by changes. | `R21ApprovalGate`; bound artifact hashes; impact-analysis invalidated gate IDs | IMPLEMENTED |
| 13. Artifact Promotion | Generated artifacts progress through controlled promotion levels and are not treated as approved by default. | `ARTIFACT_PROMOTION_LEVELS`; `R21ArtifactVersion.promotion_level`; validation tests | IMPLEMENTED |
| 14. Execution Events | Structured orchestration events and event envelope. | `R21ExecutionEvent`; `_event`; event assertions; audit persistence | IMPLEMENTED |
| 15. Checkpointing and Recovery | Persist checkpoints and recover without duplicating irreversible work. | `R21Checkpoint`; `r21_recover_execution`; persistence/recovery tests | IMPLEMENTED |
| 16. Idempotency | Stable idempotency identifiers for work packages and external operations. | `R21WorkPackage.idempotency_key`; `R21IdempotencyRecordModel`; persistence test | IMPLEMENTED |
| 17. Conflict and Contradiction Handling | Material contradictions create explicit blockers until authorized resolution. | `R21Contradiction`; `_detect_manifest_contradictions`; diagnostics in plan | IMPLEMENTED |
| 18. Change Propagation | Manifest change impact analysis determines affected work/artifacts/approvals and plan regeneration. | `r21_analyze_manifest_change`; impact-analysis test | IMPLEMENTED |
| 19. Orchestrator APIs | Project, work-package, approval, evidence, provenance, traceability APIs. | `/api/v1/r21/*` routes; OpenAPI/API tests | IMPLEMENTED |
| 20. Repository Bootstrap | Add orchestrator service, contracts, schemas, registry, examples while preserving existing repo architecture. | Implemented under `apps/api/src`; docs explain no second root service tree | IMPLEMENTED |
| 21. Persistence Model | Compilation, plan, execution, checkpoint, work package, approval, event, evidence, idempotency records. | `apps/api/src/ai_enterprise/infrastructure/r21/models.py`; migration `d6e8f2a1c9b4` | IMPLEMENTED |
| 22. Security Requirements | Service/worker identity, least privilege, isolation, audit, allowlists, quotas, artifact integrity. | API authority checks; worker permissions; policy-violation test; audit writer | IMPLEMENTED |
| 23. Observability | Metrics, logs, traces/domain events and trace dimensions without sensitive Manifest leakage. | `R21PersistenceService`; `metrics_snapshot`; event/audit records | IMPLEMENTED |
| 24. Minimal Executable Orchestrator | Load Manifest, resolve Registry, compile, graph, work packages, workers, dependency order, parallelism, validation, persistence, approval, recovery, delivery. | end-to-end R21 tests | IMPLEMENTED |
| 25. Recommended First Vertical Slice | Generate small API service workflow from Manifest through delivery package. | `_work_package_specs`; expected outputs; successful execution test | IMPLEMENTED |
| 26. Acceptance Criteria | Demonstrate planning, traceability, dependencies, parallelism, bounded permissions, validation, approvals, pause/resume, recovery, retries, contradictions, change impact, audit, delivery. | `test_r21_execution_orchestrator_runtime.py` | IMPLEMENTED |
| 27. Test Scenarios | Validate scenarios A–J. | success, invalid manifest, validation failure, human rejection, recovery, manifest change, policy violation; retry/remediation coverage | IMPLEMENTED |
| 28. Implementation Sequence | Domain objects, schemas, state machines, graph, scheduler, worker contract, validation, approvals, events/audit, persistence, recovery, impact analysis, vertical slice, tests. | Runtime/API/persistence/migration/tests/status package | IMPLEMENTED |
| 29. Deliverables | Orchestrator service, schemas/contracts, policy definitions, persistence migrations, events, tests, demo, runbook/security/recovery/conformance evidence. | runtime, API schemas, migration, tests, status docs, implementation package | IMPLEMENTED |
| 30. Definition of Done | Valid Manifest executes controlled project-generation workflow through evidence-backed delivery. | successful execution test creates evidence-backed delivery package | IMPLEMENTED |

## Operational boundary

R21 implements the deterministic orchestrator vertical slice, DB-backed persistence records, API control surface, audit/metrics integration, checkpoint recovery, and governed mutation paths. Production-scale distributed worker fleets, real asynchronous queues, and physical external worker SDK publication require deployment infrastructure and registry/distribution configuration. Those are operational integrations behind the existing R21 contracts, not missing core R21 application code.

## Verification commands

Focused:

```bash
rtk bash -lc 'cd apps/api && .venv/bin/pytest -q tests/test_r21_execution_orchestrator_runtime.py tests/test_traceability.py'
```

Full:

```bash
rtk make check
```

Release:

```bash
rtk make check-release
```

## Result

No R21 Execution Orchestrator implementation gap remains. Remaining distributed worker and SDK publication work is production deployment/configuration evidence behind the existing contract.
