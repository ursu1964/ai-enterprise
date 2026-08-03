# Full-Stack Polish Problem Plan

## Verification Snapshot

Date: 2026-08-01

Live stack status:

- Compose services are running.
- API readiness is healthy and database is reachable.
- Dashboard loads at `/dashboard`.
- Client manifest download works at `/dashboard/client-manifest-template`.
- Project Foundry Core download works at `/dashboard/project-foundry-core`.
- Operating picture is `active`.
- Projects: 3.
- Workflows: 3.
- Unresolved problems: 0.
- Acknowledged historical problem jobs: 12.
- Workflow history returns `200` for relinked workflows.
- Project intelligence returns nominal telemetry and reusable blueprints for all current projects.
- Metrics are exposed at `/metrics`.

## Remaining Problems

1. Empty graph data can still feel like broken functionality.
   - Ecosystem graph returns 0 nodes and 0 edges.
   - Evidence graph returns 0 nodes and 0 edges.
   - Dashboard now labels empty graph checks, but the system still needs seeded examples or setup
     actions.

2. Generic empty copy remains in shared helpers.
   - `No records.` does not explain what the operator should do.
   - Empty states must say whether the source is empty, delayed, missing context, or unavailable.

3. Dashboard still creates too much business meaning in JavaScript.
   - This is acceptable for the current API-hosted dashboard, but the next stable architecture needs
     one authoritative dashboard manager read model.

4. Some live worker history looks noisy.
   - There are 2 online workers, 1 degraded worker, and 7 offline historical worker records.
   - The dashboard should default to current capacity and keep old workers under history.

5. Raw count phrases still appear in dashboard text.
   - Examples: `project(s)`, `worker(s)`, `problem(s)`.
   - These are accurate but less professional than sentence-style business text.

6. Project Foundry is documented and downloadable, but not yet a runtime module.
   - The core specification, schemas, prompt contracts, gates, and repository template now exist.
   - Later slices should create API-level validation and project workspace generation from the
     Foundry contracts.

## Implementation Order

### Slice 1 - Simple Dashboard Source Language

Goal: no blank or cryptic source panels.

Tasks:

- Replace generic `No records.` with context-aware empty states.
- Replace plural counter phrases with simple sentences where visible.
- Make graph empty states explain setup and next action.
- Keep raw diagnostics behind technical details.

Acceptance:

- Dashboard never shows a primary empty state that only says `No records.`
- Empty graph means "no records yet" and includes a next action.
- Current health text is readable by a non-engineer.

Status: implemented on 2026-08-01.

Evidence:

- Generic `No records.` dashboard output was removed.
- Dashboard sections now use context-specific empty messages.
- Worker rows use business capacity wording.
- Project phase details explain empty transitions, jobs, crews, errors, blueprints, and economic
  proof.
- Focused dashboard and AEOS artifact tests passed.

### Slice 1B - Graph Source Language

Goal: graph dashboards must never look unavailable when the connection works but records are not
linked yet.

Status: implemented on 2026-08-01.

Evidence:

- Ecosystem and evidence graph checks now explain empty maps as a normal "ready but empty" state.
- Visible dashboard copy no longer exposes operator-header language in the graph panel.
- The graph panel tells the operator to refresh context, select a project, or link governed records
  during execution.
- Focused dashboard and AEOS artifact tests passed.

### Slice 2 - Current Capacity View

Goal: worker history should not make live capacity look broken.

Tasks:

- Default worker list to online and degraded workers.
- Add an explicit history option for offline workers.
- Explain degraded workers in business language.

Acceptance:

- Current capacity board shows only current operational workers by default.
- Offline historical workers are still visible when requested.

Status: implemented on 2026-08-01.

Evidence:

- Worker panel was renamed to `Worker Capacity`.
- Default view shows online and degraded capacity only.
- Offline worker instances are available through the `Offline history` selector.
- Worker rows explain business meaning: ready capacity, reduced capacity, or historical signal.

### Slice 3 - Dashboard Manager Read Model

Goal: one backend projection feeds the dashboard.

Tasks:

- Add `/api/v1/query/dashboard-manager`.
- Return sections for overview, factory, projects, problems, telemetry, graphs, guidance, and
  source freshness.
- Move business labels and next actions from JavaScript into the backend projection.

Acceptance:

- Dashboard can render primary cards from one read model.
- API and UI cannot disagree on problem counts or graph source states.

Status: implemented on 2026-08-01.

Evidence:

- Added `/api/v1/query/dashboard-manager` as the execution-control read model.
- The projection returns project advancement, phase, task counts, active/standby/problem work,
  crew assignments, recent events, telemetry, guidance, and graph nodes/edges.
- Dashboard now has an `Execution` tab with a sensitive live graph for parallel project execution.
- Manifesto launch and batch launch now open Execution first, then the full project graph remains
  available from the inspector.
- Added `POST /api/v1/project-formation/mock-factory/start` and a Factory dashboard command named
  Launch Mock Factory Test. It creates or reuses the demo portfolio, prepares missing formation
  packs, starts workflows, and opens Execution for live verification.
- Query-platform and dashboard tests passed.

### Slice 4 - Project Foundry Runtime

Goal: make Project Foundry executable, not only documented.

Tasks:

- Validate uploaded intake against Project Intake Schema.
- Generate Foundry repository skeleton.
- Write `PROJECT.yaml`, `AGENTS.md`, governance files, intake files, and initial planning files.
- Link generated workspace to GitHub URL and local base directory.

Acceptance:

- A returned client manifest can create a Foundry-compliant project workspace.
- Missing required sections produce human correction messages.

Status: implemented on 2026-08-03.

Evidence:

- Added `POST /api/v1/project-formation/projects/{project_id}/foundry-workspace`.
- The runtime validates the AEOS project-intake sections before writing files.
- Valid intake generates `PROJECT.yaml`, `AGENTS.md`, governance files, intake files,
  requirements, traceability, architecture notes, and planning files.
- Generated workspaces are constrained to `REPOSITORY_ALLOWED_ROOT`.
- Existing files are reused unless overwrite is explicitly requested.
- The project record is linked to the generated workspace path and optional GitHub repository URL.
- Focused Project Formation tests passed.

### Slice 3B - Documentation Discipline and Hub

Goal: every dashboard and product change updates documentation after verification, and operators
have one place to find documents, graphs, images, commands, and evidence.

Status: implemented on 2026-08-01.

Evidence:

- Added `/dashboard/documentation-hub`.
- Added `docs/enterprise/working-method.md`.
- Added `docs/enterprise/documentation-command-center.md`.
- Updated documentation indexes and the ETRA documentation standard.
- The documented working method is now plan, execute, verify, then document.

### Slice 5 - Deep Dashboard Presentation Polish

Goal: enterprise-grade clarity and presentation.

Tasks:

- Review every tab as a business workflow.
- Replace remaining raw states with explanation, reason, next action, and measurable effect.
- Reduce dense technical tables.
- Improve first-click guidance and dashboard section ordering.

Acceptance:

- A new operator can understand status, risk, and next step in under one minute.
- A client-facing demo can be shown without exposing technical internals.

Status: in progress.

Evidence:

- Fixed Problem Resolution Graph surface-node layout so long text wraps inside each box.
- Added regression coverage for problem graph card wrapping rules.
- Replaced raw dashboard/read-model count phrases such as `project(s)`, `worker(s)`,
  `problem(s)`, `signal(s)`, and `item(s)` with sentence-style singular/plural wording.
- Added regression coverage so the main dashboard and query read model no longer preserve the raw
  count-marker style in primary operator text.
- Source freshness cards now show human meaning, next action, and proof path so operators know
  whether to continue, refresh, or open a recovery surface.
- Project intelligence phase evidence now says `1 workflow transition` or
  `N workflow transitions` instead of exposing raw `workflow transition(s)` wording.
- Broader verification also fixed Docker execution/review runtime imports so ruff and mypy pass
  cleanly in the Docker API test environment.
- The Problems tab now presents a `Guided Recovery Center` with decision/proof/risk language
  instead of the older `Recovery and Work History` queue label.
- Guided Recovery Center rows now expose clear recovery compartments: operator decision,
  current delivery risk, proof, and next action for blocked, retrying, running, reviewed, and
  completed work.
- Authenticated ecosystem/evidence graph checks now render a guided mini-map for waiting, empty,
  available, and needs-attention states, with next action and proof-path language.
- Shared empty table/listbox states now use the same human structure: status, next action, and
  expected result when governed factory data arrives.
