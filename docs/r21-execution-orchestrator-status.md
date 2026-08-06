# R21 Execution Orchestrator status

R21 is implemented as a deterministic execution orchestrator vertical slice that
converts a valid Manifest into a governed, resumable, auditable project
generation workflow.

Implemented:

- Manifest compilation through the existing R15 compiler and R16/R17 graph-plan
  chain
- R21 project compilation model
- deterministic execution plan with work packages, phases, dependency edges,
  parallel groups, approval gates, and idempotency keys
- bounded worker request contracts with least-privilege tool permissions
- work-package state machine projection
- deterministic scheduler with dependency and approval gating
- generated artifacts with traceability and provenance hashes
- validation records and evidence records before package completion
- human release approval bound to reviewed artifact hashes
- pause/resume behavior
- checkpoint creation and recovery summary
- filesystem-backed compilation, execution-plan, and execution persistence
- DB-backed append-only R21 persistence models and migration for compilations,
  plans, executions, checkpoints, work-package projections, approval gates,
  approval decisions, events, evidence, and idempotency records
- retry records for validation failure
- runtime-owned retry, remediation, work-package cancellation, and execution
  cancellation mutations with events, transitions, checkpoints, and recomputed
  hashes
- platform audit writer integration for R21 compile, plan, execution, mutation,
  and recovery operations
- R21 metrics integration for compile, plan, execution, retry, policy, recovery,
  and checkpoint counters
- contradiction detection for explicit blocked execution branches
- manifest change impact analysis
- final evidence-backed delivery package
- API endpoints for compile, plan, execute, pause, resume, approval decisions,
  work packages, evidence, provenance, traceability, recovery, and impact
  analysis
- repository bootstrap directories and orchestration contract schemas

Remaining non-core boundary:

The current orchestrator is deterministic and local-runtime backed. Production
deployment still requires applying the R21 migration to the production database,
plus event streaming, distributed worker leases, real worker fleet deployment,
secure capability-token issuance, artifact repository integration, and
operational credentials. These are backend and infrastructure integrations
behind the R21 contract, not fabricated inside the application runtime.
