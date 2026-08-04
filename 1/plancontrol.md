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
| 0 — Reproducible baseline | **COMPLETE** | None | Reopen if source/evidence provenance becomes dirty, mismatched, or unverifiable |
| 1 — Execution infrastructure | **BLOCKED / ACTIVE** | Existing permission, executor, provider, lease, transition, and result-contract failures | Ten consecutive canary projects with zero infrastructure dead letters and classified result evidence |
| 2 — Truthful readiness | **BLOCKED** | Phase 1 not proven | Phase 1 complete |
| 3 — Full execution canary | **BLOCKED** | Phase 2 not proven | Phase 2 complete |
| 4 — Structural concentration | **BLOCKED** | Phase 3 not proven | Phase 3 complete |
| 5 — Business observability | **BLOCKED** | Phase 4 not proven | Phase 4 complete |
| 6 — Security/production | **BLOCKED** | Phase 5 not proven | Phase 5 complete |
| 7 — Customer proof | **BLOCKED** | Phase 6 not proven | Phase 6 complete |

## Phase 0 checklist

- [x] Controlling plan is no longer ignored and is included in the pending release change set.
- [x] Current changes are reviewed for authorization, migration, compatibility, and evidence risks.
- [x] Release evidence fails closed for dirty, unknown, mismatched, or tampered source state.
- [x] Deterministic demo preview/reset command is non-destructive and blocks on unresolved errors.
- [x] Dead-letter and performance baselines are stored as hashed local evidence.
- [x] Blueprint lifecycle is organization-scoped and persistence-focused endpoint behavior is tested.
- [x] Changes are separated into coherent commits.
- [x] Fresh detached checkout uses `uv sync --frozen` and passes the complete release gate.
- [x] Release artifact identifies the exact commit, Git tree, and migration head.
- [x] Final Phase 0 implementation tree is clean.

## Phase 0 execution log

- 2026-08-04: Three parallel specialist audits agreed that Phase 0 was blocked.
- 2026-08-04: Added fail-closed commit/tree/evidence/log provenance checks to release tooling.
- 2026-08-04: Added a local-only, non-destructive demo lifecycle gate that refuses to start while
  unresolved jobs or unhealthy canonical workflows exist.
- 2026-08-04: Captured `artifacts/runtime-baseline.json` with 17 current problem jobs, 15 failure
  patterns, the source commit/tree, manager timing, response size, and route metrics. The artifact
  correctly records that the source tree is still dirty.
- 2026-08-04: First clean release gate stopped on an unused lint suppression in the baseline tool;
  the defect was corrected before evidence was regenerated.
- 2026-08-04: All 15 release gates passed from both the primary checkout and a fresh detached
  checkout installed with `uv sync --frozen`. Evidence bound commit
  `e4b3af1bd53d76a49ca51de9cb8e6cee30b715d1`, tree
  `54580d49954c331cb6ae285de8e8861ca30c1296`, and migration head `f1b5c8d3e7a2`.

## Active Phase 1 checklist

- [x] Runtime directories are initialized with explicit host ownership before services start.
- [x] Integration and recovery scratch paths are writable without granting artifact mutation.
- [x] Executor and model capabilities are preflighted before affected jobs can be leased.
- [x] Setup blockers preserve queued status, attempt count, retry count, and prior failure evidence.
- [x] Worker readiness is operator-visible as `degraded` while required capabilities are absent.
- [x] Missing or invalid execution result artifacts have a stable, non-retryable classification.
- [x] Review output is structurally validated before it enters the workflow.
- [x] Lease timing is validated and heartbeat uncertainty fences execution output immediately.
- [x] Repeated setup warnings are emitted only on blocker state changes.
- [ ] An approved restricted container executor is connected and its pinned images pass preflight.
- [x] The configured model endpoint and required models pass preflight.
- [ ] Ten consecutive canary projects complete with zero infrastructure dead letters.

## Phase 1 execution log

- 2026-08-04: Parallel runtime, readiness, and workflow specialists implemented independent Phase 1
  slices, then converged through the same focused and full verification gates.
- 2026-08-04: Activated the one-shot runtime initializer locally. API readiness is healthy and all
  three worker profiles remain online; the general worker truthfully reports `degraded`.
- 2026-08-04: Live preflight classified `docker_runtime_unavailable` and
  `decomposition_provider_unavailable` before dispatch. No unrestricted Docker socket fallback was
  introduced.
- 2026-08-04: Found and corrected warning amplification during activation. Across repeated worker
  polls, each distinct blocker is now logged once when introduced and once when cleared.
- 2026-08-04: Preserved all 37 historical dead-letter records. The existing operator projection
  still identifies 17 records requiring recovery review; no queued jobs existed during this proof,
  so no runtime attempts or retries were consumed.
- 2026-08-04: Full local gate passed with 778 tests, Ruff, MyPy over 406 source files, tooling
  invariants, compose validation, and an updated code graph.
- 2026-08-04: The first clean release attempt stopped on two browser-visible HTTP 500 responses.
  Root cause was a historically edited blueprint migration: Alembic reported head while the
  physical table lacked organization ownership. Restored the historical revision to its original
  contract and added forward revision `f2c6a9e1b407` with fail-closed legacy ownership handling.
- 2026-08-04: Upgraded the local database to `f2c6a9e1b407`; all blueprint rows have non-null
  ownership, migration verification covers 40 reversible revisions, and the complete live Chromium
  journey passes without console errors.
- 2026-08-04: Confirmed the laptop already provides `gemma3:12b`, but Ollama is intentionally bound
  to host loopback. Added and activated an opt-in laptop worker overlay using host networking only
  for the hardened general worker. Model preflight now passes; no Docker socket or capability was
  granted, and `docker_runtime_unavailable` is the sole remaining general-worker setup blocker.
- 2026-08-04: Live activation exposed successful Ollama preflight traffic on every two-second poll.
  Added a bounded 30-second readiness cache with an injected monotonic clock, preserving fail-closed
  leasing while reducing idle provider traffic by approximately 93%.
- 2026-08-04: Three independent broker audits rejected a generic Docker API proxy because
  container-create authority still permits arbitrary host mounts and privilege escalation. Added
  the first narrow-broker foundation: a closed run schema, immutable image-ID policy, fixed resource
  profiles, kind/image binding, and bounded archive extraction that rejects traversal, links,
  devices, special entries, oversized input, and pre-existing destinations. Direct Docker leasing
  remains blocked until the broker service, archive client adapter, authentication, cleanup audit,
  and positive/negative live canaries pass.
- 2026-08-04: Added the authenticated snapshot-registration service boundary. Upload signatures
  bind method, path, worker, timestamp, nonce, and exact body hash; comparison is constant-time,
  clock skew is bounded, and a private SQLite nonce ledger burns authenticated nonces for at least
  15 minutes across broker restarts. Snapshot archives stream through a compressed-size limit into
  private atomic staging, and rejected archives leave no published snapshot. Liveness is separate
  from execution readiness; `/health/ready` remains 503 `engine_adapter_unconfigured` by design.
- 2026-08-04: Added an unactivated Docker engine adapter behind the broker policy. It verifies both
  immutable image IDs, constructs the hardened create request without caller option merging, uses
  three broker-owned Docker volumes instead of host bind paths, disables networking, fixes the
  non-root identity and resource ceilings, rechecks container image identity before start, bounds
  returned archives/logs, kills on monotonic timeout, and treats unproven cleanup as a terminal
  error. Activation remains prohibited until durable store immutability, the preparation/collection
  path, broker API integration, dedicated/rootless engine, and live zero-orphan canaries pass.
- 2026-08-04: Replaced transport-addressed snapshot directories with durable, owner-bound opaque
  registrations over a canonical content-addressed object store. Archive and tree identities are
  separated; equivalent archives deduplicate, executable intent remains part of identity, files are
  sealed read-only, metadata and content are fsynced before atomic no-replace publication, and every
  resolve revalidates the stored tree and its registration-bound manifest. Canonical paths reject
  traversal, links, non-NFC/control/backslash names, and case-fold collisions. Concurrent publish,
  restart, owner isolation, metadata/content tamper, database rebind, and mode behavior are covered.
  The broker remains intentionally unready: startup reconciliation/quarantine, dirfd-based root
  hardening, private runtime materialization, and a dedicated/rootless engine are still required.
- 2026-08-04: Added deterministic snapshot-store startup reconciliation under an exclusive
  publication lock. SQLite integrity and complete registration evidence are checked; every active
  object is rehashed; interrupted staging, valid or corrupt orphan publications, and corrupt
  referenced objects move through a crash-recoverable quarantine intent journal; lost registration
  databases fail closed; and a durable reconciliation report is exposed through broker readiness.
  Named crash checkpoints plus a real SIGKILL-after-publication test prove recovery on both sides of
  the object/registration commit boundary. The engine now binds the resolved snapshot reference and
  canonical input hash before creating resources, uses retry-unique names, and prepares fresh named
  volumes in a fixed, networkless, capability-minimal materializer before the non-root runtime sees
  workspace RW, input RO, and output RW. This remains unactivated pending trusted-root dirfd leases,
  real Docker UID/mode canaries, durable terminal-evidence volume retention, and dedicated images.
- 2026-08-04: The first real Docker broker canary correctly failed even though mocked tests passed:
  Docker tokenized the materializer shell program because it was supplied as a string, so only the
  first `find` command ran and both non-root agents were denied their input. The command is now one
  fixed argv element and ends with ownership/mode attestations. A repeatable canary against both
  local immutable image IDs proves UID 10001 execution and UID 10002 review can read but not modify
  governed input, can write private workspace/output volumes, leave the immutable source unchanged,
  produce a valid result contract, and leave zero labeled containers or volumes. Activation remains
  blocked until captured results survive broker crashes and cleanup through a durable handoff.
- 2026-08-04: Added terminal-evidence-aware broker volume retention. Once a workload reaches the
  terminal evidence capture point, the broker now returns the retained workspace/output volume names,
  preserves those volumes through container cleanup, verifies they still exist, and removes only
  transient input/setup material. Setup failures and timeouts still clean all volumes. The local
  canary now proves retained terminal evidence before explicitly removing it after handoff. Activation
  remains blocked until the broker API persists this retained-evidence manifest durably and recovery
  can replay cleanup/handoff after process or host failure.

## Active blockers observed

- Runtime path ownership and result-contract protections are implemented and locally verified, but
  the historical failures remain preserved as recovery evidence.
- No approved restricted container execution provider is connected, so execution and review jobs
  remain capability-blocked before leasing.
- The snapshot store now publishes durable immutable objects, but activation remains blocked on
  trusted-root dirfd operations and store-lifetime resolver leases. Startup reconciliation and
  private named-volume materialization are implemented and pass real Docker UID/mode/hash canaries.
  Terminal-evidence-aware volume retention is implemented inside the inactive engine path, but
  activation still requires durable broker API persistence and recovery replay for the retained
  evidence manifest.
- Current execution/review Dockerfiles are adequate for a local canary but are not production-
  reproducible yet: base images, apt packages, and pip bootstrap inputs still need immutable pins.
- The required ten consecutive end-to-end canary projects cannot begin until the remaining executor
  capability is connected. The model capability is now connected. Phase 2 remains closed.

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
