# Mock Factory Proof-of-Life Runbook

Status: verified on 2026-08-01.

This document explains how to run and verify the AI Enterprise mock factory test. The goal is to
prove that the application can start from a manifesto-style decision, create governed projects,
coordinate specialist work, show live graph movement, record telemetry, and create local Git
repositories that can later be connected to GitHub.

## 1. What This Mock Proves

The mock test proves the living operating loop:

```text
manifesto authority
-> project records
-> formation packs
-> workflow instances
-> requirements crew
-> architecture crew
-> work-package planning crew
-> autonomous approval policy
-> execution phase
-> dashboard graph, jobs, events, telemetry, and reusable evidence
```

The human role in this mock is the manifesto ingestion decision. After that, controlled autonomy
can approve requirements, architecture, and work-package planning because the demo manifesto policy
explicitly enables it.

The mock does not yet publish to GitHub automatically. It creates local Git repositories first.
GitHub publication is a controlled integration step because it needs a selected remote repository
and credentials.

## 2. Dashboards To Use

Open the central manager:

```text
http://localhost:8000/dashboard
```

Use these dashboard areas:

- Factory: start the mock factory test.
- Execution: watch the live project graph.
- Projects: inspect one project in detail.
- Problems: review current and historical job failures.
- Metrics: confirm API and dashboard activity.
- Documentation Hub: find runbooks and operating documents.

Useful direct URLs:

```text
http://localhost:8000/dashboard
http://localhost:8000/dashboard/documentation-hub
http://localhost:8000/health/ready
http://localhost:8000/metrics
```

## 3. Mock Projects Created

The mock creates or reuses these four demo projects.

### AI Enterprise Product Factory Demo

Project ID:

```text
5363842f-2699-498f-aad4-b4f178db2afb
```

Local repository:

```text
/home/user/projects/mock-enterprise/ai-enterprise-product-factory
```

Dashboard link:

```text
http://localhost:8000/dashboard?project=5363842f-2699-498f-aad4-b4f178db2afb
```

Purpose: prove the central factory manager can turn manifesto intake into live project execution,
telemetry, graph movement, and reusable blueprints.

### ISO Certification Consulting Module Demo

Project ID:

```text
77fc3270-6f13-4a25-879b-6ffa9f58c0e5
```

Local repository:

```text
/home/user/projects/mock-enterprise/iso-certification-consulting-module
```

Dashboard link:

```text
http://localhost:8000/dashboard?project=77fc3270-6f13-4a25-879b-6ffa9f58c0e5
```

Purpose: prove the enterprise can package compliance, ISO-style gap analysis, corrective actions,
and audit evidence as a reusable consulting product.

### Application Verification Debug Module Demo

Project ID:

```text
f6986dcc-2170-48eb-819b-4f3ff6220272
```

Local repository:

```text
/home/user/projects/mock-enterprise/application-verification-debug-module
```

Dashboard link:

```text
http://localhost:8000/dashboard?project=f6986dcc-2170-48eb-819b-4f3ff6220272
```

Purpose: prove the enterprise can turn application failures into analysis, fixes, test proof, and
future quality patterns.

### Enterprise Blueprint Catalog Demo

Project ID:

```text
620c4410-9eb3-479a-861f-84d7c573af68
```

Local repository:

```text
/home/user/projects/mock-enterprise/enterprise-blueprint-catalog
```

Dashboard link:

```text
http://localhost:8000/dashboard?project=620c4410-9eb3-479a-861f-84d7c573af68
```

Purpose: prove that repeated delivery structures can become reusable templates, agent patterns,
and economic proof assets.

## 4. Start The Application

From the repository root:

```bash
cd /home/user/projects/ai-enterprise
docker compose up -d api worker integration-worker recovery-worker
```

Verify readiness:

```bash
curl -fsS http://localhost:8000/health/ready
```

Expected response:

```json
{"status":"ok","service":"AI Enterprise","version":"0.1.0","database":"reachable"}
```

## 5. Start The Mock From The Dashboard

1. Open `http://localhost:8000/dashboard`.
2. Click the Factory tab.
3. Click `Launch Mock Factory Test`.
4. The dashboard should say that four demo projects are ready.
5. The dashboard automatically opens the Execution graph.
6. Click any project node to inspect phase, tasks, crew signals, recent events, and telemetry.

Expected human result:

```text
Mock autonomy started.
Open Execution, select a mock project, and verify the graph begins to move.
```

## 6. Start The Mock From The API

Use this command when you want repeatable proof or when documenting a test run:

```bash
curl -fsS -X POST http://localhost:8000/api/v1/project-formation/mock-factory/start \
  -H 'Content-Type: application/json' \
  -H 'X-Actor-ID: local-dashboard-admin' \
  -H 'X-Actor-Type: human' \
  -H 'X-Actor-Role: platform-admin' \
  -d '{}'
```

Expected response shape:

```json
{
  "status": "started",
  "started_count": 4,
  "projects": [
    {
      "name": "AI Enterprise Product Factory Demo",
      "project_record": "created or reused",
      "formation_pack": "created or already prepared",
      "workflow": "started or reused and nudged"
    }
  ]
}
```

The endpoint is idempotent. Running it again should reuse the same demo projects and nudge their
workflows instead of creating duplicate demo projects. For routine demonstrations, use the guarded
lifecycle command instead of calling the start endpoint directly:

```bash
python tools/demo_lifecycle.py
```

Preview is the default and performs no mutation. It verifies that the API is a loopback development
instance, validates the exact four-project portfolio, and checks operator jobs and canonical
workflows. Start only after preview reports `ready`:

```bash
python tools/demo_lifecycle.py --execute
```

Execution is fail-closed. Any unresolved failed, abandoned, or dead-letter job—or an unhealthy
canonical workflow—stops the command before the factory start request. A blocker evidence document
is written under `artifacts/demo-runs/`. The command never deletes records, resets the database, or
bulk-acknowledges failures. Review and resolve the underlying cause through the normal operator
workflow first; historical failure and acknowledgement audit evidence remains intact.

## 7. Verify Repositories Were Created

Run:

```bash
find /home/user/projects/mock-enterprise -maxdepth 2 -name .ai-enterprise-initialized -print
```

Expected paths:

```text
/home/user/projects/mock-enterprise/ai-enterprise-product-factory/.ai-enterprise-initialized
/home/user/projects/mock-enterprise/iso-certification-consulting-module/.ai-enterprise-initialized
/home/user/projects/mock-enterprise/application-verification-debug-module/.ai-enterprise-initialized
/home/user/projects/mock-enterprise/enterprise-blueprint-catalog/.ai-enterprise-initialized
```

Verify each is a Git repository:

```bash
git -C /home/user/projects/mock-enterprise/ai-enterprise-product-factory status --short
git -C /home/user/projects/mock-enterprise/iso-certification-consulting-module status --short
git -C /home/user/projects/mock-enterprise/application-verification-debug-module status --short
git -C /home/user/projects/mock-enterprise/enterprise-blueprint-catalog status --short
```

Clean or empty output means the repository has no uncommitted local changes.

## 8. Verify The Live Execution Graph

Call the dashboard manager read model:

```bash
curl -fsS http://localhost:8000/api/v1/query/dashboard-manager \
  -H 'X-Actor-ID: local-dashboard-admin' \
  -H 'X-Actor-Type: human' \
  -H 'X-Actor-Role: platform-admin'
```

Current verified snapshot on 2026-08-01:

```text
7 projects, 56 done tasks, 0 active tasks, 5 standby tasks, 8 problem tasks.
```

Current verified demo project states:

```text
Enterprise Blueprint Catalog Demo | work_package_approved | execution | execution_running
Application Verification Debug Module Demo | work_package_approved | execution | execution_running
ISO Certification Consulting Module Demo | work_package_approved | execution | execution_running
AI Enterprise Product Factory Demo | work_package_approved | execution | execution_running
```

Human meaning:

```text
The mock portfolio moved through requirements, architecture, planning, work-package approval, and
entered the execution phase. The graph is reading the live backend projection, not static mock UI.
```

## 9. Verify Jobs And Crews

List operator jobs:

```bash
curl -fsS http://localhost:8000/api/v1/operator/jobs \
  -H 'X-Actor-ID: local-dashboard-admin' \
  -H 'X-Actor-Type: human' \
  -H 'X-Actor-Role: platform-admin'
```

For each demo project, look for successful jobs such as:

```text
advance_workflow succeeded
run_requirements_crew succeeded
run_architecture_crew succeeded
plan_work_package succeeded
```

The current database also contains historical dead-letter jobs from earlier debugging. Those are
preserved as evidence. When presenting the mock, explain the difference:

```text
Current proof: the latest workflow and crew jobs advanced the demo projects into execution.
Historical problem records: older failures remain visible so the system does not hide defects.
```

## 10. What To Look For In The Graph

In the Execution tab:

- Project node: shows the selected demo project.
- Workflow node: shows current workflow phase.
- Crew node: shows requirements, architecture, and planning crew signals.
- Telemetry node: shows event count and project signals.
- Task counters: show done, active, standby, and problem work.
- Inspector: explains the selected graph node in human language.

The graph proves life when counters increase and project phases change after pressing
`Launch Mock Factory Test` or calling the mock API.

## 11. What The Specialist Agents Analyse

The mock portfolio covers four different product directions:

- Product Factory: dashboard, manifesto intake, execution graph, telemetry, blueprint reuse.
- ISO Consulting: compliance analysis, audit evidence, corrective action workflows.
- Verification Debug: failure analysis, debugging, testing, improvement loops.
- Blueprint Catalog: reusable patterns, templates, crew knowledge, economic proof.

Each project uses the same governed operating loop, but the project type changes the business
meaning and future product package.

## 12. GitHub Publication Path

Today the mock creates local Git repositories. To publish one mock product to GitHub:

1. Create an empty GitHub repository, for example `ai-enterprise-product-factory-demo`.
2. Add it as the remote:

```bash
git -C /home/user/projects/mock-enterprise/ai-enterprise-product-factory remote add origin \
  git@github.com:<your-org>/ai-enterprise-product-factory-demo.git
```

3. Push the branch:

```bash
git -C /home/user/projects/mock-enterprise/ai-enterprise-product-factory push -u origin main
```

4. In future dashboard project creation, put the GitHub URL in the `GitHub repository URL`
   field before starting the project.

GitHub automation should be added as a dedicated integration module with credential handling,
remote verification, rollback evidence, and operator-visible status. Do not hide GitHub failures
inside the dashboard.

## 13. Mock Product For Market Demo

Recommended first market-facing mock product:

```text
AI Enterprise Product Factory Demo
```

Market message:

```text
An AI operating factory that turns a rough business manifesto into governed project execution,
live graphs, specialist agent work, telemetry, and reusable delivery blueprints.
```

Minimum market demo flow:

1. Show the central dashboard.
2. Press `Launch Mock Factory Test`.
3. Open Execution and click the Product Factory project.
4. Explain the graph: manifesto, project, workflow, crew, telemetry, proof, blueprint.
5. Open the repository path and show that a Git repository exists.
6. Open Problems and explain that failures are preserved as improvement inputs, not hidden.
7. Explain the GitHub path as the next integration step for a client-ready repository.

## 14. Clean Success Criteria

The mock proof-of-life is acceptable when:

- API readiness returns `status: ok`.
- Four mock project records exist.
- Four local Git repositories exist under `/home/user/projects/mock-enterprise`.
- Formation packs exist or are reported as already prepared.
- Workflows exist for all four mock projects.
- Dashboard manager reports phase movement after launch.
- Requirements, architecture, and work-package planning jobs have succeeded.
- The Execution tab shows project graph movement in human-readable form.
- Any remaining failure is visible in Problems with a clear cause and next action.

## 15. Current Known Follow-Up

The current run proves autonomous movement into execution. The remaining polish target is to make
historical problem records less dominant in the dashboard when the latest path is healthy. They
should stay visible, but the dashboard should label them as reviewed history instead of making the
current project look broken.

The next engineering slice should focus on:

- Separate current active problems from historical reviewed problems in project counters.
- Add a GitHub integration preparation panel to the Factory dashboard.
- Add a market-demo project template that creates a richer first repository structure.
- Add one-click export of the proof package: project IDs, paths, events, artifacts, and graph state.
