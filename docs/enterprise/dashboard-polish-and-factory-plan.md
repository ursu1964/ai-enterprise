# Dashboard Polish and Factory Operating Plan

## Purpose

This plan turns the current AI Enterprise command center into a clearer business operating surface.
The goal is not to add more panels. The goal is to make every panel understandable, connected to a
known data source, and able to guide a human from manifesto to parallel project execution, proof,
recovery, reuse, and evolution.

## Current State

AI Enterprise now has a working API-hosted dashboard at `/dashboard`, a demo story at
`/dashboard/demo`, a graphify bridge at `/dashboard/graphify`, operator job APIs, project
intelligence, workflow relink/start APIs, project formation packs, raw Prometheus metrics, and the
Query Platform operating picture.

The strongest foundation is the Query Platform. It already combines projects, workflows, jobs,
workers, enterprise objects, performance metrics, learning proposals, knowledge, audit, and graph
nodes into a human-readable operating picture. The dashboard should increasingly treat this as the
primary source of business truth.

## Main Gaps

0. Correctness repairs from the first polish slice are complete.
   - Business Decision Board object shape is stable.
   - Movement graph SVG rendering and operating-picture surface nodes use separate containers.
   - Relinked workflow history returns `200`.
   - Empty graph endpoint responses are presented as setup states, not broken surfaces.
   - Acknowledged dead-letter jobs are historical evidence, not active project risk.

1. Some raw backend vocabulary still exists internally as API values, filters, and diagnostic
   details. Primary dashboard text must continue to translate these values into plain language.

2. Dashboard JavaScript still duplicates some interpretation that already belongs in backend read models. This
   creates risk that Overview, Problems, Metrics, and Projects disagree.

3. Project intelligence now separates current problems from acknowledged historical failures. The
   next improvement is richer explanation around the lesson learned and reusable guardrail created
   from each reviewed failure.

4. Data-source status is visible, but source contracts are informal. Every dashboard section should
   declare which endpoint feeds it, what stale data means, and what fallback message appears.

5. Factory creation can start one project or a manifesto batch, but the operator does not yet see a
   strong launch result contract: what started, what failed, what needs input, and which project graph
   should be opened first.

6. Graph panels now explain waiting, empty, available, and needs-attention states. The next
   improvement is richer node-level proof and blueprint reuse lineage.

7. Metrics mix raw runtime counters and governed performance. The dashboard should explain the
   difference: raw telemetry proves the system is alive; governed metrics prove quality, speed,
   reuse, and business effect.

8. Reusable blueprints are presented, but not yet promoted into an explicit template lifecycle:
   candidate, reviewed, reusable, deprecated, improved.

9. Default list behavior needs polish. Problems should open on current action, not all historical
   jobs. Metrics should open on business proof, not raw Prometheus names. Raw details should remain
   available under advanced or diagnostic sections.

10. Live data is sparse in several enterprise-maturity domains. Governed performance, enterprise
   resources, modules, schedules, organizational threads, maturity snapshots, learning proposals,
   and knowledge can be empty in local operation. Empty states must explain setup and value instead
   of looking like missing implementation.

## Product Principles

- One live picture: the dashboard reads from governed projections and does not invent competing
  truth.
- Human language first: every status has a business label, a short explanation, and a next action.
- Evidence is never hidden: old failures remain visible as history, but resolved history is not a
  current blocker.
- Graphs are controls: clicking a node must explain what it means and where the operator can act.
- Parallel work is supervised: batch launch must show portfolio state, capacity, risk, and proof.
- Reuse compounds value: every finished project should produce candidate patterns for future work.

## Phase 1 - Vocabulary and Meaning Layer

Create a shared backend vocabulary module for dashboard and query projections.

Tasks:

- Add human labels for project, workflow, job, worker, graph, metric, and source states.
- Add a short `meaning`, `operator_action`, and `severity` for every known state.
- Replace raw dashboard labels with translated labels while keeping raw status available in details.
- Add tests that assert no primary dashboard result box displays raw-only states.

Acceptance criteria:

- `dead_letter` appears as historical technical detail, not as the main user-facing status.
- `manual_intervention` appears as "Review before running" with a reason and next action.
- `work_package_approved` appears as "Plan approved, execution not started".
- Every card has at most two or three concise explanatory phrases.

## Phase 1A - Correctness Repairs Before Polish

Repair live dashboard/data-contract defects before visual changes.

Tasks:

- Fix workflow history for relinked projects by allowing a bootstrap transition state or storing an
  enum-compatible previous state with a separate `transition_kind`.
- Align project intelligence with operator job resolution rules so acknowledged failures are
  historical evidence, not active project problems.
- Fix the Business Decision Board object-shape bug.
- Fix the movement graph SVG/HTML container conflict.
- Change graph checks so `200` with zero nodes means "Empty graph: no records yet", not "available".

Acceptance criteria:

- `/api/v1/workflows/{workflow_id}/history` returns `200` for relinked workflows.
- Global operating picture and selected project dashboard agree on unresolved problem counts.
- Empty graph checks display a useful setup or data explanation.
- Business board renders without undefined values when operating picture is available.
- Movement graph remains an SVG and does not get overwritten by HTML surface nodes.

## Phase 2 - Dashboard Data Contracts

Make every dashboard section declare and validate its source.

Tasks:

- Define a dashboard read model endpoint, for example `/api/v1/query/dashboard-manager`, that
  composes the data currently fetched separately by dashboard JavaScript.
- Include `source`, `freshness`, `last_updated`, `available`, `empty_reason`, and `operator_action`
  for each section.
- Keep command endpoints separate: start workflow, relink workflow, acknowledge job, create project,
  create formation pack.
- Add tests for healthy, partial, stale, empty, and unauthorized source states.

Acceptance criteria:

- A failed source never leaves a blank panel.
- Empty graph states explain whether the graph has no records, needs context, or is unavailable.
- The dashboard can render from one manager read model plus explicit command calls.

## Phase 3 - Project Factory Launch Contract

Make manifesto intake and batch launch feel like a supervised production line.

Tasks:

- Add a launch preview step that validates project name, repository path, branch, project type,
  manifesto shape, and expected outcome before creating records.
- Return a structured launch result: created projects, formation packs, workflows started, workflows
  waiting, failures, and recommended first project to inspect.
- Add portfolio view for parallel manifestos with status, capacity, risk, and next action.
- Add retry-safe idempotency keys for dashboard project creation.

Acceptance criteria:

- After manifesto insertion, the dashboard says exactly what is ready and what is missing.
- After batch launch, the operator sees started, blocked, and next inspection target.
- Starting the same manifesto twice is detected and explained.

## Phase 4 - Project Execution Graph Polish

Turn project intelligence into a high-trust live project dashboard.

Tasks:

- Make each phase node show label, status, confidence, completed evidence, remaining work, owner
  crew, and next action.
- Separate current issues from acknowledged historical failures.
- Replace heuristic estimates with a visible confidence label until historical duration telemetry is
  available.
- Add phase detail sections for objectives, executed steps, remaining steps, artifacts, jobs, crew,
  calibration, economic proof, and reusable blueprint candidates.

Acceptance criteria:

- Clicking any phase explains what happened, what remains, what proof exists, and what to do next.
- Historical errors are marked "Reviewed history" and do not make the project look currently broken.
- Estimates say "early estimate" until calibrated data exists.

## Phase 5 - Problems, Recovery, and Improvement Loop

Convert the Problems dashboard from a failure list into a recovery and learning board.

Tasks:

- Group work by "Needs action", "Being retried", "Reviewed history", and "Healthy history".
- Add direct action buttons where safe: acknowledge, open attempts, open project, open workflow
  history, create recovery note.
- Add human root-cause categories for common errors.
- Add improvement proposals from repeated failure classes.

Acceptance criteria:

- The operator can see the problem, cause, next action, and reusable lesson in one listbox item.
- Acknowledging a historical failure updates the operating picture without deleting evidence.
- Repeated failures become proposed guardrails or templates.

## Phase 6 - Telemetry and Business Metrics

Separate live telemetry from business performance.

Tasks:

- Show raw metrics as "system pulse" with friendly metric names.
- Show governed performance as "business proof" with quality, speed, reuse, cost, and risk signals.
- Add calibration state: uncalibrated, learning, calibrated, stale.
- Connect project estimates to measured phase durations when enough history exists.

Acceptance criteria:

- The Metrics tab explains what each signal proves.
- Missing governed metrics produce a setup action, not a scary error.
- Project estimates improve when historical telemetry exists.

## Phase 7 - Graph Hub and Blueprint Lifecycle

Make graphs the central explanation and reuse interface.

Tasks:

- Normalize graph responses into nodes, edges, selected node detail, source, and empty reason.
- Show code graph, ecosystem graph, evidence graph, project graph, and blueprint graph as related
  views, not separate mysteries.
- Add blueprint candidate lifecycle: proposed, reviewed, reusable, deprecated, improved.
- Connect blueprint candidates to source project, phase, crew, artifact, and economic proof.

Acceptance criteria:

- Every graph panel opens with either a graph or a clear reason why there is no graph.
- Clicking a blueprint explains where it came from and how it can be reused.
- Reuse becomes visible as a measurable enterprise asset.

## Phase 8 - Quality Gates and Product Discipline

Protect dashboard quality with automated checks.

Tasks:

- Add contract tests for the dashboard manager read model.
- Add tests for human wording on key states.
- Add tests for source freshness and empty states.
- Add browser-level checks for `/dashboard`, `/dashboard/demo`, and graph interactions.
- Keep `pytest`, `ruff`, `mypy`, ETRA, Alembic single head, and `graphify update .` as the gate.

Acceptance criteria:

- No dashboard panel can regress to blank or cryptic output without failing tests.
- Every new dashboard feature updates this plan or the operator guide.
- Every implementation slice ends with live API verification.

## First Implementation Slice

Start with the highest leverage and lowest risk:

1. Fix workflow history for relinked workflows and add a regression test.
2. Align project intelligence problem counts with acknowledged dead-letter rules.
3. Fix the `businessBrief()` object-shape bug so the Business Decision Board always receives
   `health`, `value`, `risk`, `next`, and `online`.
4. Fix the `movementGraph` rendering conflict so SVG movement rendering cannot be overwritten by
   HTML surface nodes.
5. Treat empty graph endpoint responses as empty/setup states, not available graphs.
6. Add dashboard preflight validation before project creation. Missing project name, repository
   path, branch, or invalid manifesto shape must produce friendly guidance before API calls.
7. Add the shared vocabulary/meaning layer.
8. Apply it to Query Platform operating picture and project intelligence.
9. Update dashboard rendering to use translated labels for primary text.
10. Make Problems default to current action and move succeeded or acknowledged jobs into history.
11. Make Metrics business-first and keep raw metric names in an advanced section.
12. Add tests for workflow history, acknowledged historical failures, friendly labels, empty source
   messaging, graph empty states, and the Business Decision Board object shape.

This slice makes the dashboard more professional immediately and prepares the later manager read
model without destabilizing project creation.

## Implementation Log

### 2026-08-01 - Phase 1A Correctness Slice

Completed:

- Workflow history now accepts the relink bootstrap state `unlinked` and no longer returns HTTP 500
  for relinked workflows.
- Project intelligence now uses unresolved problem jobs for telemetry, calibration, and economic
  viability, so acknowledged historical failures do not appear as active project risk.
- Business Decision Board now receives a stable object shape when the operating picture is present:
  `health`, `value`, `risk`, `next`, and `online`.
- The SVG movement graph is no longer overwritten by operating-picture HTML surface nodes.
  Operating-picture cards now render into `operatingPictureSignals`.
- Authenticated graph checks now distinguish an empty graph from an available populated graph.

Verified:

- Full API test suite: 527 tests passed.
- Ruff: passed.
- Mypy: passed.
- Alembic: single head `c7f4a9d2e631`.
- ETRA: 642 checks, conformant.
- Live workflow history: all relinked workflows returned `200`.
- Live operating picture: `active`, zero unresolved problems, twelve acknowledged historical
  problem jobs.
- Live project intelligence: all current projects report nominal telemetry and viable state.

### 2026-08-01 - Phase 1B Operator Polish Slice

Completed:

- Factory launch now validates project name, repository path, default branch, and project summary
  before calling project creation APIs.
- Factory launch failures now show professional guidance instead of raw `422` or `500` style
  messages.
- Problems now default to current action and separate reviewed history from active work.
- Job rows show business meaning first and keep raw diagnostics under technical details.
- Metrics are business-first under "Business Telemetry"; raw runtime metric names are kept in an
  advanced section.
- Dashboard status labels now translate common project, workflow, job, worker, telemetry, and
  economic states into human language.

Verified:

- Focused dashboard/query/workflow tests passed.
- Full API test suite: 527 tests passed.
- Ruff: passed.
- Mypy: passed.
- Alembic: single head `c7f4a9d2e631`.
- ETRA: 642 checks, conformant.

### 2026-08-01 - Client Manifest Intake Slice

Completed:

- Added a downloadable client/service project manifest template at
  `/dashboard/client-manifest-template`.
- Added a Manifesto Launcher download action so the operator can send the intake document to a
  client or requesting service.
- Extended Manifesto Launcher ingestion to accept returned Markdown or text documents as well as
  JSON.
- The returned document now populates project name, project base directory, default branch, GitHub
  repository URL, and project summary when those fields are present.
- Added a GitHub repository URL field to the launcher so project records can retain the remote
  collaboration target.

Verified:

- Focused dashboard and project-formation tests passed.
- Ruff: passed.
- Mypy: passed.

### 2026-08-03 - Plan Refresh and Vocabulary Tightening

Completed:

- Updated this plan so already-repaired issues are recorded as complete instead of remaining
  dashboard defects.
- Kept raw backend state values available as filters and diagnostics, while confirming primary
  dashboard text translates them into human labels.
- Replaced the remaining visible recovery-group phrase that exposed backend worker vocabulary.

Verified:

- Focused dashboard tests passed.
- Dashboard source scan confirms primary empty-state and raw-count regressions are still covered by
  tests.

### 2026-08-03 - Business Board Read-Model Slice

Completed:

- Added a `business_board` contract to `/api/v1/query/dashboard-manager`.
- Moved Business State, Value in Motion, Risk and Attention, and Recommended Next Move messages
  into the manager read model.
- Updated the dashboard to prefer the manager business board while keeping the older local
  calculation as a fallback if the manager source is unavailable.

Verified:

- Focused dashboard tests passed.
- Focused query-platform tests passed.
