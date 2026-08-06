# AI Enterprise Application Improvement Plan

Date: 2026-08-03

## Purpose

This plan records the current status of AI Enterprise and the next practical improvement methods.
The goal is to move from a strong local proof-of-life into a repeatable, demonstrable, production
ready operating system for governed software delivery.

## Current Status

### Working Foundation

- The repository has a FastAPI backend, worker services, PostgreSQL migrations, API-hosted
  dashboard pages, command-line verification tools, and governed project/factory workflows.
- The central dashboard is available at `/dashboard`, with demo, documentation, graph, factory,
  project, problems, metrics, and execution surfaces.
- The client-facing R1 portal is available at `/client-portal`; it imports AEPM v0.1 manifests,
  guides review of the canonical model, records approval, and downloads the traceable project
  blueprint.
- R1 import and review APIs accept governed `aepm-interpretation-output-0.1` model output, validate
  the structure, bind it to the source manifest, and expose it through clarification/audit evidence.
- R1 imports and reviews persist canonical source manifest bytes through the configured artifact
  store and include the content-addressed source locator in traceability and audit evidence.
- R1 imports append AEIR model versions, source metadata, object projections, relationships, and
  hash-linked change events to PostgreSQL; review only appends a new AEIR version when the client
  submits a corrected manifest.
- R1 responses include a compact `r1-manifest-to-blueprint-proof-0.1` proof object covering source,
  validation, clarification, AEIR persistence, artifact bundle, and traceability evidence.
- The Query Platform and dashboard-manager read models now provide a strong source of business
  truth for projects, workflows, jobs, telemetry, graphs, and guidance.
- Project Foundry workspace generation exists and can create governed project skeletons under the
  configured repository root.
- Recovery, relink, graph setup, release artifact evidence, and guided dashboard language have
  improved substantially.
- Latest GitHub Actions on `main` are green:
  - Engineering Verification: success.
  - ETRA Conformance: success.
- Current local test inventory:
  - 82 API test files.
  - 635 discovered test functions by source scan.

### Known Local Caveat

- The Windows clone has an unrelated dirty `P1.txt` caused by the case-collision between `P1.txt`
  and `p1.txt`. Do not commit it from this machine unless the repository is first repaired for
  Windows case-sensitive checkout behavior.
- Local `engineering_verify.py --static` can report generated-artifact drift on Windows checkout.
  GitHub Ubuntu verification is the authoritative current CI signal.

## Main Gaps

1. Browser-level verification is still lighter than API verification.
   - The dashboard has many API and HTML contract tests, but no strong browser journey suite for
     `/dashboard`, `/dashboard/demo`, `/dashboard/documentation-hub`, graph setup, and factory
     launch.

2. Production readiness still depends on real infrastructure decisions.
   - TLS, trusted proxy identity, server secrets, backup restore drills, object storage, model
     endpoint proof, Prometheus/Grafana, and alert routing must be verified on the target server.

3. Blueprint reuse is visible but not yet a complete lifecycle.
   - Candidate blueprints and reuse proof are shown, but reviewed, reusable, deprecated, improved,
     and marketplace-ready states need a stronger domain model and operator workflow.

4. Release evidence is improving but should become harder to regress.
   - Recent CI failures came from tool lint and executable-bit drift. The repo needs a cheap
     preflight that catches these before pushing.

5. Dashboard manager still has room to absorb browser-side business logic.
   - The trend is good: more decisions now come from backend read models. Continue moving primary
     business meaning out of JavaScript and into tested read models.

6. Real project autonomy proof needs tighter levels.
   - The current local factory proves controlled orchestration. Production claims should stay
     separated into local proof, connected proof, and production proof.

## Improvement Principles

- Prefer one governed read model over repeated browser-side interpretation.
- Every dashboard state must have meaning, proof, and next action.
- Every release must produce evidence, not just a green check.
- Every repeated failure should become a guardrail, test, runbook entry, or reusable template.
- Production movement requires explicit identity, backup, rollback, and monitoring proof.
- Do not hide raw diagnostics; move them behind advanced/detail surfaces.

## Priority Plan

### Phase 1 - CI and Developer Guardrails

Objective: stop repeated workflow failures before GitHub Actions.

Tasks:

- Add a local preflight script or Make target that runs:
  - `python -m ruff check tools`
  - shebang/executable-bit scan for `tools/*.py`
  - workflow action-version scan
  - `python -m compileall -q tools`
- Add a focused test for the shebang/executable invariant.
- Pin or record the Ruff version used by CI so local and CI results do not diverge silently.
- Document the Windows `P1.txt`/`p1.txt` case-collision risk.

Acceptance:

- A new shebang tool that is not executable fails before push.
- Tool import formatting is checked with the same Ruff behavior as CI.
- The Node runtime warning for GitHub actions does not return.

Status: implemented on 2026-08-04.

Evidence:

- `tools/check_tooling_invariants.py` rejects shebang Python tools without executable bits and
  outdated known GitHub action majors.
- `make tooling-invariants` checks Ruff, repository invariants, and Python compilation locally.
- Ruff is pinned to the lockfile version in development and CI.
- Focused regression tests cover valid tooling, executable-bit drift, and outdated actions.
- On case-insensitive Windows filesystems, use a case-sensitive clone or worktree because `P1.txt`
  and `p1.txt` are distinct tracked files. Do not commit either file from a collapsed checkout.

### Phase 2 - Browser Journey Verification

Objective: protect the dashboard as a real operator interface, not only an API contract.

Tasks:

- Add Playwright or equivalent browser checks for:
  - `/dashboard`
  - `/dashboard/demo`
  - `/dashboard/documentation-hub`
  - `/dashboard/graphify` missing/available states
  - Factory preview/start flow
  - Project inspector and Execution tab
  - Problems and Metrics tabs
- Test loading, empty, partial, unavailable, and successful source states.
- Add screenshot or text assertions for primary business language.

Acceptance:

- A blank dashboard panel fails CI.
- A cryptic raw backend state in primary UI fails CI.
- The demo story can be opened and followed without API console knowledge.

Status: implemented on 2026-08-04.

Evidence:

- `tools/dashboard_browser_verify.py` drives Chromium through every primary dashboard tab, mock
  factory preview, project inspection, demo story, documentation hub, and Graphify route.
- Active views fail when an operator panel is blank, and browser console errors fail the journey.
- Failure screenshots are written under `artifacts/browser/` for diagnosis.
- Use `make dashboard-browser-install` once, then `make dashboard-browser-verify` against the live
  stack. The existing HTTP verifier remains the fast release contract check.

### Phase 3 - Production Readiness Evidence

Objective: convert server deployment from instructions into auditable proof.

Tasks:

- Create a production readiness evidence bundle covering:
  - TLS and reverse proxy configuration.
  - Trusted proxy HMAC signing.
  - Server secrets generation and rotation plan.
  - Managed Postgres or server Postgres backup restore drill.
  - Object storage provider decision and access test.
  - Model endpoint verification.
  - Prometheus scrape and Grafana dashboard availability.
  - Alert escalation route.
- Extend `release_artifact.py` so production-required evidence is explicit when a production release
  is requested.

Acceptance:

- A production deployment cannot be called ready without backup restore proof.
- Missing identity or monitoring configuration produces a clear blocker.
- The operator has one command or document bundle that states ready/not ready.

Status: implemented on 2026-08-04.

Evidence:

- `tools/production_readiness.py` validates real infrastructure choices and nine current,
  category-specific operational proofs.
- Backup readiness requires isolated database restore evidence; the existence of a dump is not
  accepted as production proof.
- Every proof has a check timestamp, expiry, durable evidence reference, and required details.
- `make production-readiness` writes the auditable aggregate report.
- `make production-release-artifact` fails closed when production evidence is missing, pending, or
  expired, while normal release artifacts remain explicitly non-production.

### Phase 4 - Blueprint Lifecycle

Objective: turn reusable ideas into governed enterprise assets.

Tasks:

- Add blueprint lifecycle states:
  - proposed
  - reviewed
  - reusable
  - deprecated
  - improved
- Link each blueprint to source project, phase, artifact, evidence, economic proof, and review
  decision.
- Add dashboard controls to inspect blueprint origin and recommended reuse.
- Add tests that repeated problem classes create improvement proposals or blueprint candidates.

Acceptance:

- A finished project can produce reusable, reviewable patterns.
- Operators can see why a blueprint is trustworthy.
- Deprecated patterns remain visible as history but are not recommended.

Status: implemented on 2026-08-04.

Evidence:

- Governed blueprint assets persist source project, phase, artifact, pattern, evidence, economic
  proof, recommended use, version, supersession, and reuse count.
- Lifecycle decisions persist reviewer, rationale, evidence, previous state, and target state.
- The enforced lifecycle is proposed, reviewed, reusable, improved, and deprecated; direct
  unreviewed promotion to reusable is rejected.
- Deprecated assets remain queryable with `include_deprecated=true` but are excluded from default
  catalog recommendations.
- The Blueprint Graph Hub reads the governed catalog and displays origin, lifecycle, recommended
  use, and reuse history alongside inferred learning candidates.

### Phase 5 - Real Project Controlled Integration

Objective: prove value on a real repository without unsafe production effects.

Tasks:

- Define proof levels:
  - Local proof: no external writes.
  - Connected proof: GitHub issue/branch/PR creation with explicit approval.
  - Production proof: deployment or production data movement only after release gates.
- Add a runbook for the first small real project improvement.
- Ensure GitHub integration requires scoped credentials and human approval.
- Record before/after evidence, tests, rollback, and release notes.

Acceptance:

- The platform can complete one small verified improvement on a real repository.
- No production action can happen silently.
- The dashboard shows proof, risk, rollback, and next action.

### Phase 6 - Observability and Business Metrics

Objective: make telemetry useful for decisions, not only health checks.

Tasks:

- Separate raw runtime pulse from governed business performance.
- Add calibration labels:
  - uncalibrated
  - learning
  - calibrated
  - stale
- Track phase duration, retry rate, recovery time, reuse count, and cost/risk signals.
- Show why an estimate is early, learned, or stale.

Acceptance:

- Metrics explain what changed and why it matters.
- Project estimates improve after enough history exists.
- Missing governed metrics show setup guidance, not a failure-looking state.

Status: in progress; runtime performance slice implemented on 2026-08-04.

Evidence:

- Dashboard telemetry uses database aggregate queries for project/job counts instead of loading
  every project and job record into application memory every refresh.
- Every HTTP route now records count, cumulative latency, and maximum latency without adding a
  metrics dependency.
- Responses expose `Server-Timing` so browser and operator tools can inspect application latency.
- The existing Prometheus endpoint exports the new route performance signals for dashboarding and
  alert thresholds.
- Composite project/time indexes now support dashboard-manager and project-intelligence history
  reads for jobs, crew runs, and work packages as those tables grow.
- Large dashboard and JSON responses use gzip compression, reducing first-load transfer cost while
  preserving the API-hosted dashboard architecture.
- Dashboard refresh no longer requests the overlapping operating-picture projection. Business
  status, source contracts, and graph signals reuse the authoritative dashboard-manager response,
  removing a multi-query read model from every 15-second browser refresh.
- Runtime and governed telemetry summaries now reuse rows already loaded by dashboard-manager,
  removing the separate telemetry-summary request and its aggregate/metric queries from refresh.
- Interactive project, problem-job, and worker-capacity records are now bounded projections inside
  dashboard-manager, removing three more duplicate list requests while keeping command endpoints
  separate.
- Timed refresh pauses while the browser tab is hidden, resumes immediately when visible, and
  coalesces concurrent refresh calls so slow networks cannot create overlapping manager queries.
- Dashboard refresh requests the compact manager representation, avoiding a second serialization
  of every project summary while the default compatibility representation remains available to
  existing API clients.
- Stable local actor and organization context is loaded once per dashboard session and reused on
  later refreshes, removing one HTTP round trip and two database reads from every polling cycle.
- Project Intelligence groups repeated job failures by recovery pattern instead of repeating the
  same instruction per job; affected-job counts, identifiers, and diagnostics remain available as
  proof while the Problems view retains individual recovery actions.

### Phase 7 - Operator Documentation and Training

Objective: make the system teachable to another person.

Tasks:

- Create a short operator training path:
  - Start locally.
  - Open demo story.
  - Launch mock factory.
  - Inspect execution graph.
  - Review problems.
  - Generate Foundry workspace.
  - Produce release evidence.
- Add a one-page "What to show a client" guide.
- Keep every dashboard change tied to updated documentation.

Acceptance:

- A new operator can run the demo in under 30 minutes.
- The operator can explain local proof versus production proof.
- Documentation Hub contains the current route to every important surface.

## Recommended First Slice

Start with Phase 1 because it prevents repeated CI friction:

1. Add `tools/check_tooling_invariants.py`.
2. Add a Make target `tooling-invariants`.
3. Verify all `tools/*.py` shebang files are executable.
4. Verify workflow actions use current Node 24-compatible versions.
5. Add a focused test or CI step for the invariant.
6. Document the Windows case-collision caveat.

This is low risk, directly addresses recent repeated errors, and makes later development faster.

## Status Table

| Area | Current status | Next improvement |
| --- | --- | --- |
| CI | Green on latest `main` | Add local invariant preflight |
| Dashboard | Strong API-hosted operator surface | Add browser journey tests |
| Project Foundry | Workspace runtime implemented | Add more real-project proof |
| Recovery | Guided recovery language improved | Convert repeats into guardrails/templates |
| Graphs | Local demo graph proof exists | Add richer node-level lineage |
| Release evidence | Release/gate tools exist | Enforce production evidence bundles |
| Production | Documented path exists | Execute real server proof |
| Blueprints | Candidates visible | Add lifecycle and review workflow |

## Verification Commands

Use these after each improvement slice:

```bash
python tools/engineering_verify.py --static --json
python tools/evolution_verify.py --json
python tools/federation_verify.py --json
python tools/intelligence_verify.py --json
python tools/etra_conformance.py --root . --json
python tools/engineering_verify.py --full --json
```

For production-readiness work, also run:

```bash
make migration-verify
make server-readiness
make infrastructure-choices-verify
make backup-verify
make deployment-blueprint
make release-gate-evidence-ci
make release-artifact
```

## Success Definition

The application is ready for the next maturity level when:

- CI catches tool, workflow, and dashboard regressions before merge.
- A browser test proves the dashboard journey.
- A real project can be improved with local/connected/production proof clearly separated.
- A release artifact explains what was checked, what remains, and whether production is allowed.
- Reusable blueprints become reviewed enterprise assets, not only dashboard suggestions.
