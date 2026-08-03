# AI Enterprise Documentation

This documentation describes the AI Enterprise platform as an enterprise operating system for
governed engineering work. It is organized as a book: read the first chapters for orientation, then
use the operator guides when starting or running the system.

## Chapter Map

1. Enterprise Overview
   - Purpose: controlled, auditable software-engineering orchestration.
   - Core idea: requirements, architecture, planning, implementation, review, integration,
     recovery, evidence, and learning execute above a governed kernel.
   - Start here: [Operator Startup Guide](operator-startup-guide.md).
   - Architecture knowledge base: [AI Enterprise Architecture](../architecture/README.md).
   - AEOS and Project Foundry foundation: [AEOS Master Specification](../aeos/README.md).

2. Local Startup and Operations
   - Docker Compose startup, database migrations, health checks, logs, and shutdown.
   - Dashboards and operator surfaces: `/docs`, `/metrics`, `/health/live`, `/health/ready`,
     graphify `graphify-out/graph.html`.
   - Guide: [Operator Startup Guide](operator-startup-guide.md).
   - Dashboard quality roadmap:
     [Dashboard Polish and Factory Operating Plan](dashboard-polish-and-factory-plan.md).
   - Current improvement roadmap:
     [AI Enterprise Application Improvement Plan](application-improvement-plan-2026-08-03.md).

3. Enterprise Preparation
   - Runtime directory bootstrap.
   - Local admin identity and development authority grants.
   - Local Git remote, signing/HMAC secrets, provider/model readiness, and seeded organization.
   - Existing reference: [Local Bootstrap](../local-bootstrap.md).

4. Enterprise Kernel
   - Managed enterprise resources.
   - Enterprise schedules.
   - Enterprise modules.
   - Organizational threads.
   - Operating maturity snapshots.
   - API root: `/api/v1/enterprise-kernel`.

5. Project Lifecycle
   - Project registration.
   - Direct project-state lookup.
   - Requirements runs and approval.
   - Architecture runs and approval.
   - Work-package planning and approval.
   - Execution requests and evidence.
   - Walkthrough: [Project Execution Walkthrough](project-execution-walkthrough.md).
   - Mock proof-of-life: [Mock Factory Proof-of-Life Runbook](mock-factory-proof-of-life-runbook.md).
   - Real project test: [Real Project Analysis And Approval Runbook](real-project-analysis-approval-runbook.md).

6. Requirements and Specification Engineering
   - Requirements revisions.
   - Specification creation, decisions, validation, generation, evidence graph, and drift.
   - Existing references:
     - [Specification Enforcement](../engineering/specification-enforcement.md)
     - [ETRA API Standard](../etra/api-standard.md)
     - [ETRA Documentation Standard](../etra/documentation-standard.md)

7. Architecture Governance and Operations
   - Architecture runs, artifacts, reviews, approvals, lineage, and work-package gates.
   - Architecture observability, integrity, recovery, and retention.
   - Existing references:
     - [Architecture Operations Runbook](../architecture-operations-runbook.md)
     - [Architecture Observability](../architecture-observability.md)

8. Work-Package Decomposition
   - Decomposition runs.
   - Decomposition artifacts.
   - Validation findings.
   - Decomposition review/revision.
   - Approved work packages.

9. Execution Runtime
   - Execution request, isolation, idempotency, events, test results, and artifacts.
   - Worker service: `worker`.
   - Evidence surfaces: execution events, test results, patch artifacts, logs.

10. Patch Review and Controlled Integration
    - Patch review runs, findings, checks, and events.
    - Integration eligibility, approval, attempts, and recovery integration.
    - Worker service: `integration-worker`.

11. Governed Change Management
    - Change proposals, change sets, transformation plans, impact assessments, validation plans,
      staged-release plans, rollback plans, decisions, observations, outcomes, and timeline.
    - Important rule: this API records governed change decisions and plans; activation authority is
      deliberately not exposed.

12. Agent Runtime and Crew Governance
    - Skill registry.
    - Tool registry.
    - Model deployments and health.
    - Runtime sessions, context manifests, tool/model invocation lineage, output validation.
    - Existing reference: [Agent Runtime Operations](../runbooks/agent-runtime-operations.md).

13. Organizational Governance
    - Organizations, units, roles, role versions, agents, assignments, workflow guard,
      authority evaluation, and crew composition.
    - API root: `/api/v1/organizations`, plus related role/agent routes.

14. Knowledge and Learning
    - Knowledge extraction.
    - Candidate review.
    - Supersession, withdrawal, contradiction resolution.
    - Retrieval with scoped context.
    - Existing references:
      - [Governed Enterprise Intelligence](../engineering/governed-enterprise-intelligence.md)
      - [Strategic Intelligence Runbook](../runbooks/strategic-intelligence.md)

15. Resilience, Recovery, and Continuity
    - Service objectives, dependencies, continuity activation, backup manifests, restore
      verification, disaster-recovery plans/runs.
    - Recovery incidents, assessments, approvals, attempts.
    - Worker service: `recovery-worker`.
    - Existing references:
      - [Service Operations Runbook](../runbooks/service-operations.md)
      - [Engineering Verification Runbook](../runbooks/engineering-verification.md)

16. Federation and Ecosystem
    - Governed ecosystem entities/assets/approvals/invocations/edges/graph.
    - Federated boundaries and external collaboration.
    - Existing references:
      - [Governed Federation](../engineering/governed-federation.md)
      - [Federation Operations](../runbooks/federation-operations.md)

17. Enterprise Evolution and Performance Governance
    - Enterprise improvements, artifacts, decisions, transitions.
    - Performance evidence, metrics, recommendations, certifications, learning proposals.
    - Existing references:
      - [Governed Enterprise Evolution](../engineering/governed-enterprise-evolution.md)
      - [Enterprise Evolution Runbook](../runbooks/enterprise-evolution.md)

18. Observability and Audit
    - Health endpoints.
    - Metrics endpoint.
    - Audit events and lifecycle queries.
    - Architecture health endpoints.
    - Graphify architecture view.

19. Operational Discipline
    - Use `rtk` for repo commands in this workspace.
    - Keep Alembic linear: `alembic heads` must report one head.
    - Run `graphify update .` after code changes.
    - Use bounded changes, tests, and commits per slice.
    - Existing reference: [P9 Codex Prompt Chain](../engineering/p9-codex-prompt-chain.md).

20. Troubleshooting
    - Compose/service status.
    - Database readiness.
    - Migration failures.
    - Missing actor headers.
    - Provider readiness versus live LLM inference.
    - Worker queues and logs.

## Current Runtime Shape

The repository currently provides a FastAPI backend and worker services. There is no separate
frontend application package in this repo. Operator interaction is primarily through the API-hosted
central manager and the API console:

- Enterprise command center: `http://localhost:8000/dashboard`
- Demo story: `http://localhost:8000/dashboard/demo`
- Swagger UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health/live`
- Readiness: `http://localhost:8000/health/ready`
- Metrics: `http://localhost:8000/metrics`
- Architecture graph: `http://localhost:8000/dashboard/graphify`
- PostgreSQL via `make db-shell`

## One-Command Enterprise Launch

Use the manifest launcher for normal local operation:

```bash
rtk python scripts/enterprise_autostart.py --manifest docs/enterprise/enterprise-manifest.example.json
```

It starts Compose, runs bootstrap, waits for readiness, creates all manifest projects, and starts
their workflows concurrently. Add more `--manifest` flags to launch multiple manifestos together.

## Project Factory

The command center includes a Factory tab for interactive project creation. Select one of the
enterprise project types, attach a manifesto JSON, and start either one project or the full manifesto
batch. The Projects tab then acts as a scrollable switchboard: click any project to open its
execution graph with phase status, crew activity, jobs/problems, reusable artifacts, estimates, and
remaining work.

The Overview tab is graph-first. Its Enterprise Movement Graph connects manifesto intake, factory
launch, active projects, agent crews, telemetry, calibration, error follow-up, economic proof,
blueprints, and evolution. Each node is clickable and opens the relevant manager surface so the
operator can move from the whole enterprise picture to the exact control panel.

The command center also shows data-source freshness above the dashboard. API readiness, jobs,
workers, projects, and metrics are marked fresh or unavailable so operators know whether the current
picture is reliable.

The Business Decision Board translates live state into business language: current health, value in
motion, delivery risk, and the recommended next move. It is designed to help an operator leave the
dashboard with one clear action instead of scanning raw technical records.

The Guided Route gives step-by-step orientation from idea or manifesto to project launch, execution
graph, proof checks, and demo story. It updates after each major operator action.

The Factory tab includes a Vision Clarifier. It accepts imperfect client input and proposes
practical, growth, and visionary versions with objective, production route, proof of value, and
market message before the project is launched.

The demo story page explains the same idea for a non-operator audience. It shows how a rough idea
becomes a supervised project, how crews work, how quality is checked, and how proof supports a
marketing platform story.

The Overview tab includes a Living Enterprise Pulse. It summarizes factory activity, work in motion,
crew capacity, and telemetry in plain language before the operator opens detailed dashboards.

The Enterprise Ecosystem Modules panel proposes optional growth paths such as listening/clarifying,
vision presentation, ISO/compliance, verification/debug, production route, and blueprint marketplace.
Modules are recommendations, not forced workflow.

The graph hub separates public code graph navigation from authenticated enterprise graphs.
Ecosystem and evidence graphs require operator headers and context IDs, so the dashboard asks for
`organization_id` and, for evidence, `project_id` before checking availability.

The other manager tabs also expose graph-style control panels:

- Factory Creation Graph: manifesto, project type, project registration, parallel batch launch, and
  execution dashboard handoff.
- Problem Resolution Graph: queued work, running work, followed errors, worker topology, and
  improvement/solution flow.
- Telemetry Pulse Graph: request flow, dashboard activity, worker health, problem pressure, and
  calibration feed.
- Blueprint Graph Hub: code graph, ecosystem graph, evidence graph, project blueprints, and future
  template evolution.

Every project graph also exposes the operating loop: always-active telemetry, calibration gates,
followed errors, improvement proposals, reusable template metadata, and the specialist-agent crew
that cooperates on the project.

## Recommended Reading Order

1. [Operator Startup Guide](operator-startup-guide.md)
2. [Project Execution Walkthrough](project-execution-walkthrough.md)
3. [Mock Factory Proof-of-Life Runbook](mock-factory-proof-of-life-runbook.md)
4. [Real Project Analysis And Approval Runbook](real-project-analysis-approval-runbook.md)
5. [AI Enterprise Working Method](working-method.md)
6. [Documentation Command Center](documentation-command-center.md)
7. [Local Bootstrap](../local-bootstrap.md)
8. [Service Operations Runbook](../runbooks/service-operations.md)
9. Domain chapters from the map above as needed.

## Documentation Maintenance

Keep this documentation synchronized with every operator-facing change. Update these files whenever
startup commands, dashboard routes, project workflow steps, manifest fields, metrics, graph links,
or approval procedures change:

- [README](README.md)
- [Operator Startup Guide](operator-startup-guide.md)
- [Project Execution Walkthrough](project-execution-walkthrough.md)
- [Mock Factory Proof-of-Life Runbook](mock-factory-proof-of-life-runbook.md)
- [Real Project Analysis And Approval Runbook](real-project-analysis-approval-runbook.md)
- [AI Enterprise Working Method](working-method.md)
- [Documentation Command Center](documentation-command-center.md)
- [Enterprise Manifest Example](enterprise-manifest.example.json)
- [Mock Enterprise Factory Manifest](mock-enterprise-factory-manifest.json)
