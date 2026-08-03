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
