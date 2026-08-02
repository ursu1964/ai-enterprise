# Real Project Analysis And Approval Runbook

Status: operator procedure drafted on 2026-08-01.

This document explains how to run a real test where AI Enterprise analyses an existing project,
proposes a debugging and improvement plan, waits for human approval, and only then proceeds toward
execution.

The intended operating contract is:

```text
existing repository
-> project registration
-> manifesto describing debug/improvement intent
-> workflow start
-> requirements analysis
-> human approval
-> architecture/improvement plan
-> human approval
-> bounded work package
-> human approval
-> execution request
-> evidence, events, telemetry, dashboard graph
```

## 1. Safety Rule

For a real project, do not enable full autonomous approval at the beginning. The human approves the
generated plan before implementation starts.

Use this mode:

```text
human-in-the-loop improvement mode
```

Do not use the mock autonomy policy for client or production repositories unless the repository
owner explicitly accepts that policy.

## 2. Choose The Target Repository

The repository must be under the configured allowed root:

```text
/home/user/projects
```

Example target:

```text
/home/user/projects/my-existing-application
```

Before registering the project, verify the repository exists:

```bash
cd /home/user/projects/my-existing-application
git status --short
git rev-parse --verify HEAD
```

Recommended before the first AI Enterprise run:

```bash
git status --short
git branch --show-current
```

If there are uncommitted changes, decide intentionally:

- Commit them if they are part of the baseline.
- Stash them if they are personal/local work.
- Stop if you do not know what they are.

## 3. Start The Application

From the AI Enterprise repository:

```bash
cd /home/user/projects/ai-enterprise
docker compose up -d api worker integration-worker recovery-worker
```

Verify the API:

```bash
curl -fsS http://localhost:8000/health/ready
```

Expected:

```json
{"status":"ok","service":"AI Enterprise","version":"0.1.0","database":"reachable"}
```

Open the central dashboard:

```text
http://localhost:8000/dashboard
```

## 4. Create The Real Project From Dashboard

1. Open `http://localhost:8000/dashboard`.
2. Open the Factory tab.
3. Select a project type. For debugging and improvement, choose one of:
   - Automated Testing
   - Monitoring & Observability
   - Scalability & Performance
   - AI Software Development
4. Fill these fields:
   - Project name: clear product name.
   - Project base directory: the existing repo path.
   - GitHub URL: optional at this stage.
   - Branch: usually `main`.
   - Manifesto summary: describe the problem, goal, constraints, and expected proof.
5. Click `Start Process`.
6. Open Execution and select the project node.

Recommended manifesto summary:

```text
Analyze this existing application for defects, brittle behavior, missing tests, unclear structure,
performance risks, and improvement opportunities. Produce a professional debugging and improvement
plan. Do not implement changes until a human approves the proposed requirements, architecture, and
bounded work package. Every proposed action must include expected benefit, risk, files likely
affected, verification commands, and rollback considerations.
```

## 5. Create The Real Project From API

Set variables:

```bash
PROJECT_NAME="Existing Application Improvement Test"
PROJECT_PATH="/home/user/projects/my-existing-application"
PROJECT_BRANCH="main"
```

Create/register the project:

```bash
curl -fsS -X POST http://localhost:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d "{
    \"name\": \"${PROJECT_NAME}\",
    \"description\": \"Analyze this existing application for defects, missing tests, performance risks, and improvement opportunities. Produce a debugging and improvement plan. Do not implement changes until human approval.\",
    \"repository_path\": \"${PROJECT_PATH}\",
    \"repository_url\": null,
    \"default_branch\": \"${PROJECT_BRANCH}\",
    \"project_type\": \"automated_testing\",
    \"manifest\": {
      \"source\": \"real_project_analysis_test\",
      \"mode\": \"human_in_the_loop_improvement\",
      \"objective\": \"Analyze, debug, improve, and verify after approval.\",
      \"human_approval_required\": true,
      \"approval_gates\": [\"requirements\", \"architecture\", \"work_package\", \"execution\"],
      \"success_proof\": [
        \"clear problem analysis\",
        \"bounded improvement plan\",
        \"human-approved work package\",
        \"test evidence before integration\"
      ]
    }
  }" > /tmp/real-project.json
```

Extract the project ID:

```bash
python - <<'PY'
import json
payload = json.load(open("/tmp/real-project.json"))
print(payload["id"])
PY
```

Save it:

```bash
PROJECT_ID="<paste-project-id-here>"
```

Start the workflow:

```bash
curl -fsS -X POST "http://localhost:8000/api/v1/projects/${PROJECT_ID}/workflow" \
  -H 'Content-Type: application/json' \
  -d '{"actor_id":"real-project-operator"}'
```

## 6. Watch The Analysis Start

Open:

```text
http://localhost:8000/dashboard?project=<project-id>
```

Also verify by API:

```bash
curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/intelligence"
```

What you should see:

```text
workflow linked
requirements phase started or waiting for requirements approval
crew/job events visible
telemetry signal nominal or attention_required
```

## 7. Inspect Generated Requirements

List artifacts:

```bash
curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/artifacts" \
  > /tmp/real-project-artifacts.json
```

Find the latest requirements artifact:

```bash
python - <<'PY'
import json
artifacts = json.load(open("/tmp/real-project-artifacts.json"))
for item in artifacts:
    if item["artifact_type"] == "requirements_specification":
        print(item["id"])
PY
```

Before approval, read the artifact content in the API response and check that it answers:

- What problems are suspected?
- What behavior needs verification?
- What risks exist?
- What tests or evidence are required?
- What must not be changed?

Approve only if the analysis is useful and bounded:

```bash
REQUIREMENTS_ARTIFACT_ID="<paste-requirements-artifact-id-here>"

curl -fsS -X POST \
  "http://localhost:8000/api/v1/projects/${PROJECT_ID}/artifacts/${REQUIREMENTS_ARTIFACT_ID}/approval" \
  -H 'Content-Type: application/json' \
  -d '{
    "decision": "approved",
    "reviewer": "human-operator",
    "comment": "Requirements analysis is approved. Continue to architecture and improvement planning."
  }'
```

Reject if the plan is vague:

```bash
curl -fsS -X POST \
  "http://localhost:8000/api/v1/projects/${PROJECT_ID}/artifacts/${REQUIREMENTS_ARTIFACT_ID}/approval" \
  -H 'Content-Type: application/json' \
  -d '{
    "decision": "rejected",
    "reviewer": "human-operator",
    "comment": "The analysis is too broad. Regenerate with specific defects, files, tests, risks, and expected business effect."
  }'
```

## 8. Inspect Architecture And Improvement Plan

After requirements approval, the workflow queues architecture.

List artifacts again:

```bash
curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/artifacts" \
  > /tmp/real-project-artifacts.json
```

Find the architecture artifact:

```bash
python - <<'PY'
import json
artifacts = json.load(open("/tmp/real-project-artifacts.json"))
for item in artifacts:
    if item["artifact_type"] == "architecture_specification":
        print(item["id"])
PY
```

The architecture/improvement plan should explain:

- Current system understanding.
- Main suspected weak areas.
- Debugging strategy.
- Improvement strategy.
- Proposed boundaries.
- Risks and rollback.
- Verification commands.
- Expected measurable effect.

Approve architecture:

```bash
ARCHITECTURE_ARTIFACT_ID="<paste-architecture-artifact-id-here>"

curl -fsS -X POST \
  "http://localhost:8000/api/v1/projects/${PROJECT_ID}/architecture-artifacts/${ARCHITECTURE_ARTIFACT_ID}/approval" \
  -H 'Content-Type: application/json' \
  -d '{
    "decision": "approved",
    "reviewer": "human-operator",
    "comment": "Architecture and improvement direction approved. Continue to bounded work-package planning."
  }'
```

## 9. Inspect The Bounded Work Package

After architecture approval, the workflow queues work-package planning.

List work packages:

```bash
curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/work-packages" \
  > /tmp/real-project-work-packages.json
```

Find the proposed work package:

```bash
python - <<'PY'
import json
packages = json.load(open("/tmp/real-project-work-packages.json"))
for item in packages:
    print(item["id"], item["title"], item["status"])
PY
```

The work package must be small enough to trust. Approve only if it has:

- Clear objective.
- Limited files or directories.
- Explicit forbidden actions.
- Test commands.
- Resource limits.
- Traceability to requirements and architecture.
- A clear rollback or safe stop condition.

Approve work package:

```bash
WORK_PACKAGE_ID="<paste-work-package-id-here>"

curl -fsS -X POST \
  "http://localhost:8000/api/v1/projects/${PROJECT_ID}/work-packages/${WORK_PACKAGE_ID}/approval" \
  -H 'Content-Type: application/json' \
  -d '{
    "decision": "approved",
    "reviewer": "human-operator",
    "comment": "Bounded work package approved for execution."
  }'
```

At this point AI Enterprise may request execution and create execution evidence. Do not approve
integration or production release until tests, patch review, and rollback evidence are clear.

## 10. Verify Execution Evidence

List executions:

```bash
curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/executions"
```

For a specific execution:

```bash
EXECUTION_ID="<paste-execution-id-here>"

curl -fsS "http://localhost:8000/api/v1/projects/${PROJECT_ID}/executions/${EXECUTION_ID}/events"
```

Evidence to inspect:

- Execution status.
- Changed files.
- Test commands.
- Test results.
- Logs.
- Patch artifact.
- Failure message, if any.

## 11. Verify In The Dashboard

Open:

```text
http://localhost:8000/dashboard?project=<project-id>
```

Check:

- Project graph phase.
- Task counters.
- Crew signals.
- Recent events.
- Errors.
- Improvements and solutions.
- Reuse/template output.
- Economic proof estimates.

The project should be understandable without reading raw logs. If the dashboard shows cryptic
technical text, record it as a dashboard polish issue.

## 12. What Counts As Success

The real-project test is successful when:

- The existing repository is registered without leaving the allowed root.
- The workflow starts and is visible in the dashboard.
- Requirements analysis is generated and human reviewed.
- Architecture/improvement plan is generated and human reviewed.
- Bounded work package is generated and human reviewed.
- Execution starts only after approval.
- Evidence exists for jobs, events, artifacts, and telemetry.
- The dashboard explains current state in human language.
- No hidden action modifies GitHub or production without explicit approval.

## 13. What To Do If The Plan Is Poor

Reject the artifact and write a precise reason:

```text
The plan is too broad. Focus on one defect class, name the suspected files, define the expected
test command, explain the measurable effect, and limit the first work package to a small change.
```

Then regenerate or revise in the next planning slice. Do not approve vague work.

## 14. GitHub And Market Path

For a real market-facing product, GitHub should be connected only after the first local proof:

1. Local analysis completed.
2. Human-approved plan exists.
3. Work package is bounded.
4. Execution evidence exists.
5. Patch review is accepted.
6. Operator approves GitHub integration.

Recommended GitHub publication command after the repository owner approves:

```bash
git -C /home/user/projects/my-existing-application remote add origin \
  git@github.com:<your-org>/<repo-name>.git

git -C /home/user/projects/my-existing-application push -u origin main
```

Future dashboard improvement: add a GitHub preparation panel that checks remote existence,
credentials, branch protection, and push readiness before any integration attempt.

## 15. First Real Test Recommendation

Use a small existing application first. The first real test should target one measurable outcome:

```text
Improve reliability by adding or fixing tests around one important workflow.
```

Better first objective:

```text
Analyze the project and propose one bounded debugging/improvement work package that improves
test confidence without changing production behavior.
```

Avoid this first:

```text
Refactor the whole application.
```

The enterprise should earn trust through a small verified improvement before it attempts larger
autonomous work.
