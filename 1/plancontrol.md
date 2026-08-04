# AI Enterprise Plan Control

Status date: 2026-08-04

## Non-negotiable execution discipline

1. Execute phases in numeric order.
2. Do not start a later phase while the active phase has an unresolved blocker.
3. A warning, failed check, dirty release tree, missing proof, or unclassified runtime failure keeps
   the active gate closed.
4. Preserve failure evidence. Never delete, bulk-acknowledge, or cosmetically reclassify failures
   to make a gate green.
5. Parallel specialists may analyse or implement independent work, but their results must converge
   through the same active exit gate.
6. Every completed step requires code, focused tests, full applicable gates, operator-visible
   evidence, and an update to this ledger.
7. Production, connected, and local-demo proof must remain explicitly separated.

## Gate ledger

| Phase | State | Current blockers | Advance rule |
| --- | --- | --- | --- |
| 0 — Reproducible baseline | **BLOCKED / ACTIVE** | Dirty tree; release provenance does not fail closed; deterministic demo lifecycle absent; blueprint tenant isolation incomplete; baseline artifacts absent | All Phase 0 exit criteria pass from a clean checkout |
| 1 — Execution infrastructure | **BLOCKED** | Phase 0 is open; existing permission, executor, provider, lease, transition, and result-contract failures | Phase 0 complete |
| 2 — Truthful readiness | **BLOCKED** | Phase 1 not proven | Phase 1 complete |
| 3 — Full execution canary | **BLOCKED** | Phase 2 not proven | Phase 2 complete |
| 4 — Structural concentration | **BLOCKED** | Phase 3 not proven | Phase 3 complete |
| 5 — Business observability | **BLOCKED** | Phase 4 not proven | Phase 4 complete |
| 6 — Security/production | **BLOCKED** | Phase 5 not proven | Phase 5 complete |
| 7 — Customer proof | **BLOCKED** | Phase 6 not proven | Phase 6 complete |

## Active Phase 0 checklist

- [x] Controlling plan is no longer ignored and is included in the pending release change set.
- [x] Current changes are reviewed for authorization, migration, compatibility, and evidence risks.
- [x] Release evidence fails closed for dirty, unknown, mismatched, or tampered source state.
- [x] Deterministic demo preview/reset command is non-destructive and blocks on unresolved errors.
- [x] Dead-letter and performance baselines are stored as hashed local evidence.
- [x] Blueprint lifecycle is organization-scoped and persistence-focused endpoint behavior is tested.
- [x] Changes are separated into coherent commits.
- [ ] Fresh checkout uses locked dependencies and passes the complete release gate.
- [ ] Release artifact identifies the exact commit, Git tree, and migration head.
- [ ] Final working tree is clean.

## Phase 0 execution log

- 2026-08-04: Three parallel specialist audits agreed that Phase 0 was blocked.
- 2026-08-04: Added fail-closed commit/tree/evidence/log provenance checks to release tooling.
- 2026-08-04: Added a local-only, non-destructive demo lifecycle gate that refuses to start while
  unresolved jobs or unhealthy canonical workflows exist.
- 2026-08-04: Captured `artifacts/runtime-baseline.json` with 17 current problem jobs, 15 failure
  patterns, the source commit/tree, manager timing, response size, and route metrics. The artifact
  correctly records that the source tree is still dirty.

## Active blockers observed

- Runtime snapshot, integration work, review output, and artifact paths have permission failures.
- Execution provider and model provider connectivity have produced dead letters.
- Lease expiry, illegal workflow transitions, missing result artifacts, and result-contract drift
  remain unresolved historical evidence.
- These runtime failures belong to Phase 1, but Phase 0 must first produce a trustworthy baseline
  that preserves and measures them.

---

# Deep assessment

  AI Enterprise has a strong governed foundation and unusually good verification discipline. Its weakest point is currently real execution
  reliability: the interface and governance model are ahead of the worker runtime.

  Current live state:

   Signal                               Result
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━
   Projects                                 12
  ───────────────────────────  ────────────────
   Completed tasks                          96
  ───────────────────────────  ────────────────
   Unresolved problem tasks                 17
  ───────────────────────────  ────────────────
   Active tasks                              0
  ───────────────────────────  ────────────────
   Standby tasks                             6
  ───────────────────────────  ────────────────
   Tracked jobs                            133
  ───────────────────────────  ────────────────
   Online workers                            3
  ───────────────────────────  ────────────────
   Governed business metrics                 0
  ───────────────────────────  ────────────────
   Test suite                      743 passing
  ───────────────────────────  ────────────────
   Production infrastructure    Not configured

  ## Strong points

  1. Governance is substantive

  The application has real approval, audit, recovery, blueprint, evolution, authority, and evidence concepts. These are enforced through domain
  services and tests rather than existing only as dashboard terminology.

  Notable strengths include:

  - Human approval boundaries.
  - Read-only query projections.
  - Immutable evidence and hashes.
  - Recovery history.
  - Controlled Git integration.
  - Blueprint lifecycle governance.
  - Cross-organization authority checks.
  - Reversible database migrations.

  2. Verification is excellent for the project’s maturity

  The repository currently passes:

  - 743 tests.
  - Ruff.
  - MyPy across 405 files.
  - Live Chromium journeys.
  - Tooling invariants.
  - 39 reversible migrations.

  The browser verification also protects request counts, compact payloads, polling behavior, recovery grouping, empty panels, and console
  errors.

  3. The dashboard tells the truth

  The dashboard correctly reports attention_required. It does not disguise unresolved execution failures as healthy autonomy. That honesty is
  important for an enterprise product.

  4. Security architecture is thoughtful

  Positive controls include:

  - Localhost-only API and database ports.
  - Read-only containers where practical.
  - Capability-based authorization.
  - Human/service actor separation.
  - Dropped Linux capabilities on sensitive services.
  - Protected repository boundaries.
  - No-privilege-escalation settings.
  - Trusted-proxy design for production.

  5. Architectural breadth without import cycles

  Graphify reports 6,679 nodes, 21,430 relationships, 289 communities, and no detected import cycles. The system covers formation, workflow,
  execution, review, integration, recovery, resilience, knowledge, federation, governance, and performance.

  ## Weak points

  ### P0 — Worker runtime is not operationally aligned

  Most current failures are infrastructure or configuration failures, not intelligent recovery decisions:

  - Permission denied under /app/runtime-data/snapshots.
  - Permission denied under /integration-work.
  - Read-only artifact paths.
  - Missing Docker execution connection.
  - Model-provider connection failure.
  - Worker leases expiring.
  - Missing result.json.
  - Illegal workflow transitions.
  - A review result contract mismatch.
  - Push and executable-policy failures.

  The root problem is that worker expectations do not match their container mounts and available services.

  For example, docker-compose.yml:105 gives the general worker broad writable mounts but no Docker execution endpoint, while specialized workers
  use restrictive mounts that conflict with some output behavior.

  This is the most important weakness because it prevents the application from proving its central claim: reliable governed software execution.

  ### P0 — Readiness language is too optimistic

  /dashboard/server-readiness reports ready, but its meaning is effectively “templates exist and checks are ready to run.” Meanwhile
  infrastructure choices report needs_setup.

  These should be distinct states:

  - local_demo_ready
  - connected_execution_blocked
  - production_blocked
  - production_ready

  “Ready” should never be displayed without specifying the proof level.

  ### P0 — Current work is not captured in a clean release unit

  The working tree contains a large set of modified and untracked implementation files, including migrations, blueprint lifecycle code,
  performance tooling, browser verification, and production-readiness tooling.

  Until these are reviewed and committed atomically, the verified local result is not reproducible from the current repository commit.

  ### P1 — Code concentration is becoming risky

  Several files are too large:

   File                Lines
  ━━━━━━━━━━━━━━━━━━  ━━━━━━━
   Dashboard route     5,691
  ──────────────────  ───────
   Query platform      1,841
  ──────────────────  ───────
   Dashboard test      1,488
  ──────────────────  ───────
   Project workflow    1,443
  ──────────────────  ───────
   Projects route      1,416
  ──────────────────  ───────
   Database models     1,383
  ──────────────────  ───────
   Workflow service    1,041

  The dashboard is an embedded HTML/CSS/JavaScript application inside a Python route. This makes UI behavior harder to type-check, unit-test,
  cache, and maintain.

  Graphify also identifies highly connected nodes:

  - Actor: 207 relationships.
  - Base: 205.
  - AuditWriter: 143.
  - Settings: 94.
  - ProjectModel: 84.

  Some centrality is intentional, but changes to these abstractions have a wide regression radius.

  ### P1 — Tests prove contracts better than real autonomy

  The 743 tests are a strong asset, but most use controlled sessions, mocks, and contract assertions.

  The CI browser stack starts the API, but it does not prove a complete worker execution pipeline involving:

  - Model availability.
  - Repository snapshot.
  - Execution container.
  - Artifact result contract.
  - Review.
  - Integration.
  - Recovery.

  This explains how CI can be green while the live database contains many infrastructure dead letters.

  ### P1 — Observability lacks durable business performance

  Runtime counters exist, but:

  - Governed metric count is currently zero.
  - Metrics are process-local and reset on restart.
  - There are no demonstrated SLOs.
  - No phase-duration or recovery-time calibration is active.
  - No cost-per-project evidence exists.
  - Production Prometheus/Grafana proof is not connected.

  The system can explain its current state, but cannot yet prove that it is improving delivery speed, quality, or cost.

  ### P1 — Demo history overwhelms current decision-making

  The database contains 12 projects, 133 jobs, 25 dead-letter records in the bounded job projection, and 76 historical worker signals.

  The UI now groups repeated recovery patterns, but the underlying demo environment still needs:

  - Explicit demo runs.
  - Reset/archive functionality.
  - Current-run versus historical-run filters.
  - Project-specific failure counts.
  - A clean known-good reference run.

  ### P2 — Security hardening is inconsistent

  The API and specialized workers are constrained, but the general worker is materially less hardened:

  - No read_only.
  - No cap_drop.
  - No explicit no-new-privileges.
  - No CPU, memory, or PID limits.
  - Source code is mounted writable.
  - The entire /home/user/projects tree is mounted.

  The execution design needs a deliberate choice between an isolated external executor and narrowly controlled local execution. Simply mounting
  the Docker socket would create a severe host-escape risk.

  ### P2 — Supply-chain gates are incomplete

  CI has strong internal conformance checks but no visible:

  - Dependency vulnerability scan.
  - Container image scan.
  - SBOM generation.
  - License policy.
  - Coverage threshold.
  - Migration performance budget.

  ### P2 — Real commercial proof is still missing

  The application has strong local proof, but not yet:

  - A completed real repository improvement.
  - A connected GitHub branch/PR proof.
  - Production TLS and identity proof.
  - Restore-drill evidence.
  - Alert-routing evidence.
  - Measured before/after customer value.

  # Recommended implementation plan

  ## Phase 0 — Establish a reproducible baseline

  Duration: 1–2 days.

  - Review and commit the accumulated implementation in logical commits.
  - Generate a release evidence artifact.
  - Record current dead-letter and performance baselines.
  - Add a repeatable demo reset/seed command.
  - Preserve existing failures as historical evidence.

  Exit gate:

  - Clean working tree.
  - Fresh clone passes all 743+ tests.
  - One command starts a deterministic demo environment.
  - Release artifact identifies the exact commit and migration head.

  ## Phase 1 — Repair execution infrastructure

  Duration: 3–5 days.

  - Add an initialization service that creates runtime directories with the correct UID/GID.
  - Separate writable worker output from read-only input artifacts.
  - Correct ownership for named integration and recovery volumes.
  - Choose an execution provider:
      - Prefer a restricted external/rootless execution service.
      - Do not expose an unrestricted Docker socket.

  - Add model-provider readiness before jobs can be queued.
  - Validate repository, executor, model, output directory, and result contract at startup.
  - Refuse incompatible work with a setup blocker instead of consuming retries.
  - Repair the workflow transition and ReviewCheckResult contract defects.
  - Add lease heartbeat and graceful cancellation evidence.

  Exit gate:

  - Ten consecutive small projects complete without infrastructure dead letters.
  - Zero permission errors.
  - Zero missing-executor errors.
  - Zero model-connectivity retries when the model is unavailable; work remains blocked before dispatch.
  - Every worker produces a valid result artifact or a classified, actionable failure.

  ## Phase 2 — Make readiness truthful

  Duration: 1–2 days.

  Create an explicit proof-level model:

  local_demo → connected_execution → controlled_integration → production

  Each level must have required evidence and blockers. Replace generic ready with level-specific language.

  Exit gate:

  - A local demo cannot be confused with production readiness.
  - Infrastructure templates never produce a green production state.
  - Dashboard and release artifacts report the same readiness decision.

  ## Phase 3 — Prove one full execution journey

  Duration: 3–5 days.

  Add an end-to-end canary project that performs:

  1. Manifest intake.
  2. Requirements.
  3. Architecture.
  4. Work-package planning.
  5. Execution.
  6. Artifact validation.
  7. Review.
  8. Approved integration.
  9. Recovery simulation.
  10. Evidence publication.

  Run it locally and in CI with deterministic providers.

  Exit gate:

  - One full journey passes without manual database intervention.
  - Every transition has audit evidence.
  - Recovery is demonstrated deliberately, not inferred from old failures.
  - The dashboard links every state to its proof.

  ## Phase 4 — Reduce structural concentration

  Duration: 1–2 weeks, incremental.

  - Extract dashboard HTML, CSS, and JavaScript into versioned static modules.
  - Introduce typed frontend read-model contracts.
  - Split query_platform.py into manager, project, recovery, telemetry, and graph projections.
  - Split projects.py into CRUD, intelligence, artifacts, and work packages.
  - Split database models by bounded context.
  - Break the dashboard contract test into focused suites.
  - Add architecture-boundary tests for imports and service ownership.

  Exit gate:

  - No primary route module exceeds approximately 1,000 lines.
  - Dashboard JavaScript can be syntax-checked independently.
  - Read models have explicit schemas and compatibility tests.

  ## Phase 5 — Add business-grade observability

  Duration: 3–5 days.

  Track:

  - Phase duration.
  - Queue time.
  - Retry rate.
  - Dead-letter rate.
  - Recovery time.
  - Successful first-attempt rate.
  - Blueprint reuse.
  - Cost per completed project.
  - Human approval wait time.

  Add SLOs and persistent Prometheus/Grafana evidence.

  Exit gate:

  - Governed metric count is non-zero.
  - Every project shows calibrated or explicitly uncalibrated estimates.
  - Alerts exist for queue stagnation, lease expiry, dead-letter growth, and executor/model unavailability.

  ## Phase 6 — Security and production hardening

  Duration: 1–2 weeks.

  - Harden the general worker.
  - Narrow repository mounts to project-specific workspaces.
  - Add dependency and image scanning.
  - Generate an SBOM.
  - Test secret rotation and trusted-proxy identity.
  - Complete a database restore drill.
  - Verify object storage, TLS, monitoring, and alert routing.
  - Add abuse, quota, and concurrency boundaries.

  Exit gate:

  - Production-readiness evidence passes without placeholders.
  - Restore and alert drills have current immutable proof.
  - No worker has broader host access than its assigned project requires.

  ## Phase 7 — Real customer proof

  Duration: after Phases 1–6.

  Use one small real repository improvement and record:

  - Baseline effort.
  - Generated plan.
  - Human approvals.
  - Patch.
  - Tests.
  - Review evidence.
  - Rollback.
  - Delivery time.
  - Cost and quality difference.

  Exit gate:

  - One externally understandable case study.
  - Connected GitHub proof.
  - No inflated autonomy claims.
  - Demonstrated economic or delivery improvement.

  ## Priority order

  The controlled implementation order is:

  1. Clean, reproducible release baseline.
  2. Execution filesystem and provider readiness.
  3. Truthful readiness levels.
  4. Deterministic end-to-end canary.
  5. Module decomposition.
  6. Durable business observability.
  7. Production infrastructure and customer proof.

  Further dashboard polish should pause until the execution path can complete repeated projects reliably.
