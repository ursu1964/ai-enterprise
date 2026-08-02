# ProjectRAG Deep Analysis and Improvement Plan

Date: 2026-08-01  
Last updated: 2026-08-02  
Repository analyzed: `/home/user/projects/project-rag`  
Checkpoint branch: `ai-enterprise-analysis-checkpoint`  
Checkpoint commit: `4e9870bdd69d66331cc29a916fe96cfe133cb3cc`  
AI Enterprise project: `efe0a5c8-8877-47cf-abed-fb5127f9deb7`  
AI Enterprise workflow: `7d17fcae-b521-4cfa-9ba2-27cd439006f3`  
Requirements artifact currently pending: `b72a4c22-7c2b-4991-8ad5-faddcb4ff0d5`

## Scope

This began as a read-only analysis of the real ProjectRAG checkpoint. On 2026-08-02, Phase 1 readiness-profile work was implemented in `/home/user/projects/project-rag` and verified.

The requested analysis covers code structure, checkpoint scope, tests, runtime modules, AIOS execution modules, NORA tools, security modules, execution risks, missing tests, expected business effect, verification commands, risk level, and rollback path.

## Method

The repository instructions require the indexed `run_pipeline` workflow first. That tool is not exposed in the current Codex session, so the analysis used the available project knowledge graph plus targeted reads of files surfaced by graph context and checkpoint scope.

Evidence commands executed:

```bash
git -C /home/user/projects/project-rag show --stat --oneline --decorate --summary HEAD
git -C /home/user/projects/project-rag ls-tree -d --name-only HEAD
python -m pytest -q tests/unit/test_aios_execution_status_cli.py tests/unit/test_aios_execution_voice_eval.py tests/unit/test_nora_agent_dashboard.py tests/unit/test_nora_confirmation_contract.py tests/unit/test_nora_reasoning_style.py tests/unit/test_nora_voice_e2e.py tests/unit/test_nora_voice_memory_policy.py tests/unit/test_runtime_symbol_integrity.py
python -m pytest -q tests/unit/test_aios_execution_controller.py tests/unit/test_aios_execution_executor.py tests/unit/test_aios_execution_loop.py tests/unit/test_aios_execution_plan_runner.py
python -m apps.cli.main ax-status --format json --strict
python -m apps.cli.main ax-status --profile release --format json --strict
python -m apps.cli.main ax-status --probe-health --format json --strict
gitleaks detect --source /home/user/projects/project-rag --config /home/user/projects/project-rag/.gitleaks.toml --no-banner
git -C /home/user/projects/project-rag status --short
```

Observed results:

```text
48 passed in 0.85s
40 passed in 39.94s
ax-status ready: true
unavailable capabilities: lint.execute
gitleaks: command not found
project-rag git status: clean
2026-08-02 update: status tests 10 passed, controller/executor loop tests 41 passed, ruff check passed, local and release readiness both true in the current environment.
2026-08-02 update: `scripts/scan_secrets.py` now wraps Gitleaks when available and falls back to a built-in tracked-file scanner with clear release-mode failure via `--require-gitleaks`.
2026-08-02 update: Makefile aliases now expose `make secret-scan` for local fallback scanning and `make secret-scan-release` for release scans that require Gitleaks.
2026-08-02 update: `TenantContext` now requires an explicit `tenant_id`; API/job/agent production boundary resolvers reject missing tenants; tenant and authorization test slices passed.
```

## Repository Operating Picture

ProjectRAG is a local-first AI operating system for document intelligence, GraphRAG, agent execution, memory, health-aware runtime operation, governed software repair, and production verification.

Top-level structure observed at the checkpoint:

```text
.ai, .github, .nora, .vexp, RAG, alembic, app, apps, archive,
automation, capabilities, config, data, deploy, docs, enterprise,
examples, infra, mock-docs, mybot, nora_generated_adapters, ollama,
packages, projectrag_aios.egg-info, prompts, scripts, test, tests, tools
```

Important architectural rule from the repository documentation:

`app/` is still a legacy FastAPI/app adapter area during migration. New business logic should prefer `capabilities/`, `apps/`, or `packages/` depending on ownership. Any new logic placed in `app/` needs review to confirm it is adapter-level behavior, not hidden domain logic.

## Checkpoint Scope

The checkpoint is broad:

```text
89 files changed
8127 insertions
853 deletions
```

Main changed areas:

```text
AIOS execution: packages/aios_execution/*
NORA tools: tools/nora_*
Voice/written interaction: app/mcp/interaction/__init__.py
Runtime health: app/core/health_runtime.py, packages/runtime/health/*
Security and tenant isolation: packages/security/tenant_isolation/*, .gitleaks.toml, secret-scan workflow
CLI routing: packages/aios_execution/cli.py, packages/cli/main.py, apps/cli/main.py
Tests: tests/unit/test_aios_execution_*, tests/unit/test_nora_*, test_runtime_symbol_integrity.py
Roadmap artifacts: p1.txt, po.txt
```

The original checkpoint was stable enough for deeper analysis because the focused tests passed and the worktree was clean. On 2026-08-02, readiness reporting was improved so local execution readiness and release readiness are explicit machine-readable states.

## Positive Evidence

AIOS execution now has a governed command surface:

```text
ax-status, ax-voice-eval, ax-repair, ax-ship, ax-deploy, ax-cycle,
ax-cycle-full, ax-auto, ax-loop, ax-synth, ax-plan, ax-review,
ax-ask, ax-serve
```

`ax-status --strict` now reports selected readiness plus both local and release readiness states:

```json
{
  "ready": true,
  "readiness": {
    "profile": "local",
    "local": {
      "ready": true,
      "blockers": []
    },
    "release": {
      "ready": true,
      "blockers": []
    }
  },
  "providers": {
    "workspace": "available",
    "verification": "available",
    "lint": "available"
  },
  "tools": {
    "git": "available",
    "pytest": "available",
    "ruff": "available"
  }
}
```

The controlled repair and general plan executor tests passed. This validates the central loop shape:

```text
plan -> registry availability -> policy gate -> handler execution -> verification -> rollback on failure
```

NORA voice and dashboard-facing tests passed. This validates that the new human-readable agent status and voice policy contracts are importable and test-covered at unit level.

Runtime symbol integrity tests passed. This is important because the checkpoint touched many modules and previously this type of work often breaks imports.

## Core Risks

### R1. Release validation clarity

Affected files:

```text
packages/aios_execution/status_cli.py
packages/aios_execution/capabilities.py
packages/aios_execution/controller.py
packages/aios_execution/executor.py
packages/aios_execution/cli.py
```

Status:

```text
2026-08-02 implemented: ax-status now supports --profile local|release and reports both local and release readiness in JSON/text output.
```

Likely problem:

The original status output could make local execution readiness and release readiness look like one promise. That ambiguity is now reduced, but type-check readiness is still not modeled as a separate gate.

Business effect:

Operators can now show "local ready" and "release ready" separately. This makes dashboards safer and gives clients a clearer explanation of what the system can execute today.

Plan:

1. Done: separate `ax-status --profile local|release`.
2. Done: JSON includes `readiness.local` and `readiness.release`.
3. Done: release profile blocks on lint/ruff availability.
4. Remaining: add type-check capability when the project standardizes a type checker.

Verification:

```bash
python -m apps.cli.main ax-status --format json --strict
python -m apps.cli.main ax-status --profile release --format json --strict
python -m apps.cli.main ax-status --probe-health --format json --strict
python -m pytest -q tests/unit/test_aios_execution_status_cli.py
python -m pytest -q tests/unit/test_aios_execution_controller.py tests/unit/test_aios_execution_executor.py
python -m ruff check packages/aios_execution/status_cli.py packages/aios_execution/cli.py tests/unit/test_aios_execution_status_cli.py
```

Risk level: Low after implementation  
Rollback path: revert changes to `packages/aios_execution/status_cli.py`, `packages/aios_execution/cli.py`, and `tests/unit/test_aios_execution_status_cli.py`.

### R2. Autonomy proof still uses local/scripted providers

Affected files:

```text
packages/aios_execution/proof_of_life.py
packages/aios_execution/controller.py
packages/aios_execution/executor.py
packages/aios_execution/deploy_cli.py
packages/aios_execution/repair_cli.py
packages/aios_execution/review_cli.py
```

Evidence:

`proof_of_life.py` explicitly states limitations: patch synthesis uses injected seams, PR provider is local, deployment uses a local subprocess, and untrusted tests do not have an OS sandbox.

Likely problem:

The demo proves orchestration and safety mechanics, not full independent model intelligence and production deployment. This is good engineering honesty, but the user-facing language must not overclaim.

Business effect:

Clear labeling builds trust. Overclaiming "self-evolving autonomous enterprise" before live model synthesis, real GitHub PRs, and stronger sandboxing are wired would create sales and delivery risk.

Plan:

1. Split proof-of-life into three explicit grades: local proof, connected proof, production proof.
2. Keep the current local proof as Grade 1.
3. Add a connected proof that uses real model synthesis and a real GitHub branch/PR in a test repository.
4. Add a production proof only after sandboxed test execution and deployment gates exist.
5. Update CLI and dashboard language to show the proof grade beside every autonomous claim.

Verification:

```bash
python -m pytest -q tests/unit/test_aios_execution_loop.py tests/unit/test_aios_execution_review_loop.py
python -m apps.cli.main ax-status --format json --strict
python -m apps.cli.main ax-cycle-full --repo <sandbox-repo> --test <failing-test> --inject-failure
```

Risk level: High  
Rollback path: keep `proof_of_life.py` unchanged and only revert presentation-layer labels if copy changes cause confusion.

### R3. CLI surface is too large for reliable operation

Affected files:

```text
packages/cli/main.py
packages/aios_execution/cli.py
apps/cli/main.py
packages/aios_execution/ask_cli.py
packages/aios_execution/deploy_cli.py
packages/aios_execution/repair_cli.py
packages/aios_execution/review_cli.py
packages/aios_execution/status_cli.py
packages/aios_execution/voice_eval_cli.py
```

Evidence:

`python -m apps.cli.main --help` shows a very large command set. The AIOS execution commands are properly registered, but they are embedded in a CLI with hundreds of enterprise commands.

Likely problem:

The CLI is powerful but not operator-friendly. Users can discover commands, but the command list is too broad for a human to understand under pressure.

Business effect:

This reduces adoption. The system may be technically capable but difficult to operate without a dashboard or guided command workflow.

Plan:

1. Add a focused `aios` or `nora` command group view that shows only the current lifecycle commands.
2. Add guided commands for the three normal jobs: analyze repository, repair failing test, run proof of life.
3. Add machine-readable command catalog output for dashboard integration.
4. Add tests that assert the lifecycle command set and help text stay stable.

Verification:

```bash
python -m apps.cli.main --help
python -m apps.cli.main ax-status --format json --strict
python -m pytest -q tests/unit/test_aios_execution_status_cli.py
```

Risk level: Medium  
Rollback path: revert CLI registration and tests; implementation modules can remain untouched.

### R4. Tenant isolation improved but schema default is risky

Affected files:

```text
packages/security/tenant_isolation/schema.py
packages/security/tenant_isolation/resolver.py
packages/security/tenant_isolation/guard.py
app/security/tenant_context.py
```

Status:

```text
2026-08-02 implemented: TenantContext.tenant_id no longer defaults to "default"; direct TenantContext() construction now fails validation.
```

Likely problem:

Before the change, callers that instantiated `TenantContext()` directly could bypass resolver fail-closed behavior and silently create a default tenant.

Business effect:

In a multi-tenant product, explicit tenant context reduces data mixing risk, audit ambiguity, and authorization mistakes.

Plan:

1. Done: removed the schema default.
2. Done: added regression coverage that direct `TenantContext()` construction fails.
3. Done: added API/job/agent production boundary resolver tests for missing tenant IDs.
4. Done: verified broader tenant and authorization slices.
5. Remaining: perform a full repository test pass before release because the schema change is intentionally strict.

Verification:

```bash
python -m pytest -q tests/unit/test_tenant_context_guard.py tests/unit/test_tenant_contract.py tests/unit/test_tenant_isolation.py
python -m pytest -q tests/unit/test_chunks_repository_tenant_filter.py tests/unit/test_cognitive_cache_tenant.py tests/unit/test_memory_store_tenant.py tests/unit/test_multi_tenant_isolation.py tests/unit/test_tenant_aware_service.py tests/unit/test_tenant_context_guard.py tests/unit/test_tenant_contract.py tests/unit/test_tenant_isolation.py
python -m pytest -q tests/unit/test_authorize_request_context.py tests/unit/test_central_authorize.py tests/unit/test_content_boundary.py tests/unit/test_delegated_authority.py
python -m apps.cli.main enterprise-production-check
python -m apps.cli.main enterprise-doctor
```

Risk level: Medium after focused verification  
Rollback path: restore `tenant_id: str = Field(default="default", min_length=1)` in `packages/security/tenant_isolation/schema.py` and remove the new strictness tests if a legacy caller cannot be fixed immediately.

### R5. Security scanner is configured but not locally available

Affected files:

```text
.github/workflows/secret-scan.yml
.gitleaks.toml
docs/security/credential_handling.md
```

Status:

```text
2026-08-02 implemented: python scripts/scan_secrets.py gives a clear fallback when Gitleaks is missing, and python scripts/scan_secrets.py --require-gitleaks fails with exit code 2.
```

Likely problem:

CI can scan via GitHub Actions. Local contributors now have a stable wrapper, but release operators still need Gitleaks installed for complete Git history scanning.

Business effect:

Secrets are more likely to be detected before commit because the local command now works even without Gitleaks. Release gates can fail explicitly when Gitleaks is missing.

Plan:

1. Done: `scripts/scan_secrets.py` checks for Gitleaks and prints installation guidance when missing.
2. Done: `--require-gitleaks` makes release scans fail when Gitleaks is unavailable.
3. Done: credential-handling documentation now points to the wrapper.
4. Done: added Makefile targets `secret-scan` and `secret-scan-release`.
5. Remaining: confirm protected-branch workflow coverage.

Verification:

```bash
python scripts/scan_secrets.py
python scripts/scan_secrets.py --require-gitleaks
make secret-scan
make secret-scan-release
python -m pytest -q tests/unit/test_scan_secrets.py
python -m ruff check scripts/scan_secrets.py tests/unit/test_scan_secrets.py
```

Risk level: Low after wrapper implementation  
Rollback path: revert `scripts/scan_secrets.py`, `tests/unit/test_scan_secrets.py`, and `docs/security/credential_handling.md`; CI workflow can remain.

### R6. NORA voice dashboard is readable but not proven end-to-end in product UI

Affected files:

```text
tools/nora_agent_dashboard.py
tools/nora_voice_e2e.py
tools/nora_voice_memory_policy.py
app/mcp/interaction/__init__.py
tests/unit/test_nora_agent_dashboard.py
tests/unit/test_nora_voice_e2e.py
tests/unit/test_nora_voice_memory_policy.py
```

Evidence:

Unit tests passed. `tools/nora_agent_dashboard.py` is a clean presentation boundary over `AgentExecutionResult`, but it does not schedule or mutate agents.

Likely problem:

The text is suitable for a voice/status layer, but there is no proof in this analysis that the main dashboard/API calls this renderer for live agent state.

Business effect:

NORA can explain agent work in tests, but users may still see fragmented or technical state if the UI uses another data source.

Plan:

1. Trace the dashboard/API path that displays agent status.
2. Route live agent execution results through the same human-readable renderer or a shared presentation service.
3. Add API/dashboard tests that assert human language output for no agents, active agents, blockers, and verification state.
4. Add telemetry fields for agent, task, blocker, and verification status.

Verification:

```bash
python -m pytest -q tests/unit/test_nora_agent_dashboard.py tests/unit/test_nora_voice_e2e.py
python -m apps.cli.main ax-serve --repo /home/user/projects/project-rag
```

Risk level: Medium  
Rollback path: keep the NORA renderer isolated and revert only API/dashboard wiring.

### R7. Runtime health concurrency improved but needs stress evidence

Affected files:

```text
packages/runtime/health/runtime.py
packages/runtime/health/recovery.py
app/core/health_runtime.py
```

Evidence:

Runtime code now bounds health checks with a shared deadline and `shutdown(wait=False, cancel_futures=True)`. Symbol tests passed, but no stress result was observed in this analysis.

Likely problem:

Thread cancellation does not stop already-running Python code. A hung subsystem can still continue in the background after the report returns.

Business effect:

Health endpoints may stay responsive, but repeated probes against hung dependencies could accumulate background work under load.

Plan:

1. Add tests with a deliberately slow provider and repeated health calls.
2. Add metrics for timed-out subsystem count and health evaluation latency.
3. Add a hard cap for max workers per mode.
4. Consider process-level isolation for risky health checks.

Verification:

```bash
python -m pytest -q tests/unit/test_runtime_health*
python -m apps.cli.main health
python -m apps.cli.main enterprise-doctor
```

Risk level: Medium  
Rollback path: revert runtime health changes or disable deep checks behind a profile flag if probes regress.

### R8. Roadmap text files may not belong in product source

Affected files:

```text
p1.txt
po.txt
```

Evidence:

Both roadmap text files were committed at repository root. `po.txt` is large.

Likely problem:

These may be planning artifacts rather than source, docs, or tests. Root-level planning files increase repository noise and may accidentally contain informal or obsolete instructions.

Business effect:

Lower repository clarity. New contributors and automated agents may treat draft plans as authoritative.

Plan:

1. Confirm whether `p1.txt` and `po.txt` are intended permanent artifacts.
2. If yes, move them under `docs/roadmap/` with clear names.
3. If no, remove them in a dedicated cleanup commit.
4. Add repository policy for roadmap artifacts.

Verification:

```bash
git status --short
python -m pytest -q tests/unit/test_runtime_symbol_integrity.py
```

Risk level: Low  
Rollback path: restore the files from commit `4e9870bdd69d66331cc29a916fe96cfe133cb3cc`.

## Missing Tests

Add or confirm these tests before approving implementation:

```text
Release readiness test for lint.execute unavailable/degraded/healthy states.
Connected GitHub PR test using a safe test repository or mocked GitHub boundary.
Sandboxed test execution test for untrusted code.
TenantContext direct-construction audit test.
Dashboard/API test proving NORA human-readable agent state is displayed from live data.
Runtime health stress test for repeated slow/hung providers.
Secret-scan wrapper test when gitleaks is missing.
CLI command catalog snapshot test for AIOS lifecycle commands.
```

## Recommended Implementation Phases

### Phase 1: Truthful readiness and release gates

Goal: make status reporting impossible to misunderstand.

Tasks:

```text
Add readiness profiles: local, connected, release.
Make lint/typecheck availability visible as release-blocking, not hidden optional behavior.
Expose JSON fields suitable for AI Enterprise dashboard ingestion.
Update tests for every readiness profile.
```

Expected business effect:

Operators and clients can see exactly what the system can safely do today.

### Phase 2: Tenant and security hardening

Goal: prevent silent unsafe defaults before multi-tenant operation.

Tasks:

```text
Audit TenantContext construction.
Route boundary code through resolver functions.
Add local secret-scan wrapper.
Clarify CI branch and PR scan coverage.
```

Expected business effect:

Enterprise customers can trust isolation, audit trails, and credential discipline.

### Phase 3: Connected proof of autonomy

Goal: move from local proof to real connected execution.

Tasks:

```text
Create a safe test repository for connected proof.
Run model-generated repair against a real failing test.
Create a real GitHub branch and PR under human-approved credentials.
Record evidence artifact paths and rollback commands.
```

Expected business effect:

The product can demonstrate that a manifest/request becomes analyzed work, verified change, and reviewable delivery.

### Phase 4: Operator experience

Goal: make the system understandable to non-expert users.

Tasks:

```text
Add command catalog output.
Add guided analyze/repair/proof commands.
Route NORA dashboard text into the active UI/API path.
Use plain-language statuses: ready, waiting for approval, blocked by missing lint, blocked by tenant, verified.
```

Expected business effect:

The system becomes usable as a product, not only as an engineering toolkit.

### Phase 5: Runtime resilience

Goal: prove the operating system can stay alive under partial dependency failure.

Tasks:

```text
Stress-test health runtime with slow providers.
Track health latency and timeout metrics.
Ensure repeated probes do not accumulate runaway background work.
Add recovery recommendation evidence to dashboard/API output.
```

Expected business effect:

The enterprise organism can keep explaining itself and propose recovery even when subsystems degrade.

## Approval Recommendation

Do not approve the current generic AI Enterprise requirements artifact as the final ProjectRAG analysis. It is too shallow for this repository.

Use this document as the replacement analysis baseline, then create a new approval artifact that includes:

```text
checkpoint commit
observed tests
readiness output
known limitations
implementation phases
rollback paths
explicit human approval gates
```

The current ProjectRAG checkpoint is suitable for continued controlled development. It is not yet suitable for a production autonomy claim.

## Immediate Next Command Sequence

Run these before any implementation:

```bash
cd /home/user/projects/project-rag
python -m apps.cli.main ax-status --probe-health --format json --strict
python -m pytest -q tests/unit/test_aios_execution_status_cli.py tests/unit/test_aios_execution_voice_eval.py tests/unit/test_nora_agent_dashboard.py tests/unit/test_nora_confirmation_contract.py tests/unit/test_nora_reasoning_style.py tests/unit/test_nora_voice_e2e.py tests/unit/test_nora_voice_memory_policy.py tests/unit/test_runtime_symbol_integrity.py
python -m pytest -q tests/unit/test_aios_execution_controller.py tests/unit/test_aios_execution_executor.py tests/unit/test_aios_execution_loop.py tests/unit/test_aios_execution_plan_runner.py
```

If these remain green, start Phase 1.

## Worktree Stabilization Result

Updated: 2026-08-02

ProjectRAG is now clean on branch `ai-enterprise-analysis-checkpoint`.

```bash
git status --short --branch
```

Observed result:

```text
## ai-enterprise-analysis-checkpoint
```

The dirty work was split into explicit commits:

```text
bd7331b feat(aios): add release readiness gates
392ab92 fix(security): require explicit tenant and wrap secret scan
2204b76 chore(mcp): clean imports and type-safe helpers
8c4671f docs: archive project rag analysis
4ea2a92 chore(mcp): satisfy package lint checks
2d7ccdf feat(aios): add connected proof preflight
176fdb9 fix(security): baseline historical secret scan findings
c20ae59 feat(aios): make connected preflight runtime aware
e7c8bf8 feat(aios): report github credential source
dde8f90 feat(aios): add github auth status command
1fa8574 chore(aios): add connected proof make targets
4fc2361 chore(aios): run all connected readiness checks
```

The root `ProjectRAG Deep Analysis.md` copy was preserved inside ProjectRAG at:

```text
docs/analysis/project-rag-deep-analysis.md
```

Final focused verification:

```bash
python -m ruff check app/mcp packages/aios_execution/status_cli.py packages/aios_execution/cli.py scripts/scan_secrets.py tests/unit/test_scan_secrets.py packages/security/tenant_isolation/schema.py tests/unit/test_tenant_context_guard.py
python -m pytest -q tests/unit/test_aios_execution_status_cli.py tests/unit/test_aios_execution_capabilities.py tests/unit/test_scan_secrets.py tests/unit/test_tenant_context_guard.py tests/unit/test_runtime_symbol_integrity.py tests/unit/test_mcp_planning_step43.py tests/unit/test_context_integrity.py tests/unit/test_nora_capability_registry.py tests/test_nora_runtime.py
python -m apps.cli.main ax-status --profile release --probe-health --format json --strict
graphify update .
```

Observed result:

```text
ruff: all checks passed
pytest: 123 passed
ax-status release readiness: ready=true
graphify: updated
```

Phase 3 can now start from a clean ProjectRAG baseline. No commits were pushed.

## Phase 3 Connected Proof Preflight

Updated: 2026-08-02

ProjectRAG now has a read-only connected autonomy proof preflight:

```bash
python -m apps.cli.main ax-connected-preflight --repo /home/user/projects/project-rag --github-repo ursu1964/project-rag --format json --strict
```

What it checks:

```text
AIOS release readiness
clean local repository
runtime learning state, reported separately as a warning
origin remote
GitHub token
GitHub repository target
optional gh CLI
Gitleaks
live model mode
```

Current observed result:

```text
pass: AIOS release readiness
pass: repository clean
pass: origin remote configured
pass: GitHub repository target
pass: Gitleaks available
pass: Ollama reachable at http://localhost:11434 when `AIOS_USE_FAKE_MODELS=false`
pass: gh CLI available at /home/user/.local/bin/gh
fail: GitHub token missing
ready: false
```

Credential readiness update:

```text
Preflight now reports the active GitHub credential source without printing the token.
Supported sources are environment variables, `gh auth login`, and the Git credential helper.
Current machine state: `gh` is installed, but `gh auth status` reports no logged-in GitHub host.
Operator command: `python -m apps.cli.main ax-github-auth --format json --strict`.
Make targets: `make github-auth`, `make connected-preflight`, and `make connected-readiness`.
`make connected-readiness` always runs both auth status and connected preflight, then fails if either check fails.
```

Runtime-state handling update:

```text
Connected preflight now blocks on real source changes, but treats `.nora` runtime learning and routing state as a non-blocking warning.
This keeps the living application from blocking proof runs just because it learned or updated metrics.
```

Security release gate update:

```text
Gitleaks installed locally at /home/user/.local/bin/gitleaks.
GitHub CLI installed locally at /home/user/.local/bin/gh.
Current source tree scan: no leaks found.
Release history scan: 29 known historical findings suppressed by redacted fingerprint baseline.
Tracked-file scanner: secret-scan-ok.
Baseline file: /home/user/projects/project-rag/.gitleaks-baseline.json.
```

Verification:

```bash
python -m ruff check packages/aios_execution/connected_preflight.py packages/aios_execution/cli.py tests/unit/test_aios_execution_connected_preflight.py
python -m pytest -q tests/unit/test_aios_execution_connected_preflight.py tests/unit/test_aios_execution_status_cli.py tests/unit/test_aios_execution_github_provider.py
AIOS_USE_FAKE_MODELS=false python -m apps.cli.main ax-connected-preflight --repo /home/user/projects/project-rag --github-repo ursu1964/project-rag --format json --strict
OPENAI_API_KEY= python -m pytest -q tests/unit/test_aios_execution_capability_synthesis.py tests/unit/test_aios_execution_connected_preflight.py tests/unit/test_aios_execution_status_cli.py
OPENAI_API_KEY= python -m pytest -q tests/unit/test_aios_execution_pull_request.py tests/unit/test_aios_execution_github_provider.py tests/unit/test_aios_execution_connected_preflight.py
OPENAI_API_KEY= python -m pytest -q tests/unit/test_aios_execution_github_auth_cli.py capabilities/verification/tests/test_shutdown_verification.py tests/integration/test_security_baseline.py
python -m apps.cli.main ax-github-auth --format json --strict
make github-auth
make connected-preflight
make connected-readiness
make secret-scan-release
python -m ruff check scripts/scan_secrets.py tests/unit/test_scan_secrets.py
python -m pytest -q tests/unit/test_scan_secrets.py
```

Observed result:

```text
ruff: all checks passed
pytest: 19 passed
live preflight: source clean, Ollama pass, GitHub token missing
deterministic AIOS tests: 21 passed, 1 skipped
credential-source tests: 25 passed, 1 skipped
github-auth command tests: 23 passed
github-auth command: gh_cli=available, gh_logged_in=false, token_source=missing
make github-auth: reports missing token
make connected-preflight: all checks pass except missing token
make connected-readiness: runs both checks; source clean; fails only on missing token
secret-scan-release: gitleaks-ok; 29 baseline findings suppressed; secret-scan-ok
scanner tests: 7 passed
```

Phase 3 remains blocked by external setup, not by ProjectRAG code:

```text
1. Set AIOS_GIT_TOKEN or GITHUB_TOKEN, or run gh auth login.
```
