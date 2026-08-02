# Project Execution Walkthrough

This guide shows the normal local path from enterprise preparation to project execution. Use
Swagger at `http://localhost:8000/docs` for exact request schemas and responses while running the
commands.

## 1. Start and Prepare the Platform

Automatic manifest-driven launch:

```bash
rtk python scripts/enterprise_autostart.py --manifest docs/enterprise/enterprise-manifest.example.json
```

This starts the enterprise stack, bootstraps local operating records, creates the repositories from
the manifest if they do not exist, registers the projects, and starts project workflows in parallel.
Use repeated `--manifest` flags when you want multiple manifestos processed in one run.

Manual learning path:

```bash
rtk cp .env.example .env
rtk docker compose up --build -d
rtk docker compose --profile dev-bootstrap run --rm bootstrap
rtk curl -s http://localhost:8000/health/ready
```

## 2. Create or Select a Repository

For local development, keep target repositories under `REPOSITORY_ALLOWED_ROOT`, currently
`/home/user/projects` by default.

Example:

```bash
rtk mkdir -p /home/user/projects/example-enterprise-app
rtk git -C /home/user/projects/example-enterprise-app init --initial-branch=main
```

The execution/integration lanes are designed for governed repository operations. Do not point the
platform at arbitrary paths outside the allowed root.

## 3. Create a Project

```bash
rtk curl -s -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Enterprise App",
    "description": "A local development project used to exercise AI Enterprise workflows.",
    "repository_path": "/home/user/projects/example-enterprise-app",
    "repository_url": null,
    "default_branch": "main"
  }'
```

Save the returned `id`:

```bash
PROJECT_ID=<returned-project-id>
```

Confirm the authoritative project state at any time:

```bash
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID"
```

This is the direct lifecycle checkpoint. Use it after creation, requirements approval, architecture
approval, and execution work to verify the project status, repository location, and manifest hash.

## 4. Start a Requirements Run

```bash
rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/requirements-runs"
```

List artifacts:

```bash
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/artifacts"
```

Approve the requirements artifact when review is complete:

```bash
ARTIFACT_ID=<requirements-artifact-id>

rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/artifacts/$ARTIFACT_ID/approval" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "reviewer": "local-admin",
    "comment": "Approved for local workflow exercise."
  }'
```

## 5. Start an Architecture Run

```bash
rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/architecture-runs"
```

List artifacts again:

```bash
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/artifacts"
```

Approve the architecture artifact:

```bash
ARCH_ARTIFACT_ID=<architecture-artifact-id>

rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/architecture-artifacts/$ARCH_ARTIFACT_ID/approval" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "reviewer": "local-admin",
    "comment": "Approved for work-package planning."
  }'
```

## 6. Plan Work Packages

There are two supported surfaces.

Project workflow planning:

```bash
rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/work-package-runs"
```

Governed decomposition API:

```bash
rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/work-package-decompositions" \
  -H "Content-Type: application/json" \
  -H "X-Actor-ID: local-admin" \
  -H "X-Actor-Type: human" \
  -H "X-Actor-Role: enterprise_kernel_admin" \
  -d "{
    \"architecture_artifact_id\": \"$ARCH_ARTIFACT_ID\",
    \"repository_uri\": \"file:///home/user/projects/example-enterprise-app\",
    \"base_commit_sha\": \"<current-base-commit-sha>\"
  }"
```

After a decomposition run:

```bash
DECOMPOSITION_RUN_ID=<run-id>

rtk curl -s "http://localhost:8000/api/v1/work-package-decompositions/$DECOMPOSITION_RUN_ID"
rtk curl -s "http://localhost:8000/api/v1/work-package-decompositions/$DECOMPOSITION_RUN_ID/artifact"
rtk curl -s "http://localhost:8000/api/v1/work-package-decompositions/$DECOMPOSITION_RUN_ID/validation-findings"
rtk curl -s "http://localhost:8000/api/v1/work-package-decompositions/$DECOMPOSITION_RUN_ID/graph"
```

Approve the decomposition artifact before packages become executable:

```bash
DECOMPOSITION_ARTIFACT_ID=<artifact-id>
ARTIFACT_HASH=<artifact-content-hash>

rtk curl -s -X POST "http://localhost:8000/api/v1/work-package-decomposition-artifacts/$DECOMPOSITION_ARTIFACT_ID/reviews" \
  -H "Content-Type: application/json" \
  -H "X-Actor-ID: local-admin" \
  -H "X-Actor-Type: human" \
  -H "X-Actor-Role: enterprise_kernel_admin" \
  -d "{
    \"decision\": \"approved\",
    \"artifact_hash\": \"$ARTIFACT_HASH\",
    \"comments\": \"Approved for execution.\"
  }"
```

List approved work packages:

```bash
rtk curl -s "http://localhost:8000/api/v1/work-package-decomposition-artifacts/$DECOMPOSITION_ARTIFACT_ID/work-packages"
```

## 7. Approve a Work Package

Some project workflow packages use the project routes. Check Swagger for the exact response fields
and current status.

```bash
WORK_PACKAGE_ID=<work-package-id>

rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/work-packages/$WORK_PACKAGE_ID/approval" \
  -H "Content-Type: application/json" \
  -d '{
    "decision": "approved",
    "reviewer": "local-admin",
    "comment": "Approved for isolated execution."
  }'
```

## 8. Request Execution

```bash
rtk curl -s -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/work-packages/$WORK_PACKAGE_ID/executions" \
  -H "Content-Type: application/json" \
  -d '{
    "idempotency_key": "example-enterprise-app:wp-001:execution-001"
  }'
```

Watch execution state:

```bash
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/executions"

EXECUTION_ID=<execution-id>

rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/executions/$EXECUTION_ID"
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/executions/$EXECUTION_ID/events"
rtk curl -s "http://localhost:8000/api/v1/projects/$PROJECT_ID/executions/$EXECUTION_ID/test-results"
```

Worker logs:

```bash
rtk docker compose logs -f --tail=200 worker
```

## 9. Review and Integrate

Patch review endpoints live under project routes. Controlled integration endpoints manage approval
and integration attempts. Use `/docs` for the exact current schemas.

Useful operator checks:

```bash
rtk docker compose logs -f --tail=200 integration-worker
rtk docker compose logs -f --tail=200 recovery-worker
```

## 10. Register Enterprise Kernel Records

The Enterprise Kernel lets you register the enterprise objects that surround execution.

Actor headers:

```bash
ACTOR=(-H "X-Actor-ID: local-admin" -H "X-Actor-Type: human" -H "X-Actor-Role: enterprise_kernel_admin")
```

Register a resource:

```bash
ORG_ID=<organization-id>

rtk curl -s -X POST http://localhost:8000/api/v1/enterprise-kernel/resources \
  "${ACTOR[@]}" \
  -H "Content-Type: application/json" \
  -d "{
    \"organization_id\": \"$ORG_ID\",
    \"resource_type\": \"project\",
    \"resource_key\": \"project.example-enterprise-app\",
    \"display_name\": \"Example Enterprise App\",
    \"owner_id\": \"local-admin\",
    \"access_policy_ids\": [\"local-access\"],
    \"governance_policy_ids\": [\"local-governance\"],
    \"retention_policy_id\": \"local-retention\",
    \"provenance\": {\"source\": \"operator-walkthrough\"},
    \"semantic_relations\": [],
    \"evidence\": [{
      \"artifact_id\": \"00000000-0000-0000-0000-000000000001\",
      \"content_hash\": \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",
      \"evidence_type\": \"operator_record\"
    }],
    \"metadata\": {\"project_id\": \"$PROJECT_ID\"}
  }"
```

Enterprise-kernel route groups:

- `/api/v1/enterprise-kernel/resources`
- `/api/v1/enterprise-kernel/schedules`
- `/api/v1/enterprise-kernel/modules`
- `/api/v1/enterprise-kernel/threads`
- `/api/v1/enterprise-kernel/maturity-snapshots`

## 11. Where to Look While It Runs

- API docs: `http://localhost:8000/docs`
- Project artifacts: `GET /api/v1/projects/{project_id}/artifacts`
- Workflow history: `GET /api/v1/workflows/{workflow_id}/history`
- Execution events: `GET /api/v1/projects/{project_id}/executions/{execution_id}/events`
- Test results: `GET /api/v1/projects/{project_id}/executions/{execution_id}/test-results`
- Metrics: `http://localhost:8000/metrics`
- Logs: `rtk docker compose logs -f --tail=200 <service>`
- Graphify: `graphify-out/graph.html`

## 12. Important Operating Rules

- Do not bypass approvals to execute work packages.
- Do not execute work outside `REPOSITORY_ALLOWED_ROOT`.
- Use idempotency keys for execution requests.
- Treat artifacts, events, findings, and audit records as evidence.
- Keep migrations linear; one Alembic head only.
- If a worker fails, inspect events and logs before retrying.
