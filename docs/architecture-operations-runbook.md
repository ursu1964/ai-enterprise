# Architecture workflow operations runbook

This runbook covers the durable architecture workflow. Operators must use the application service
or its CLI/API adapter; direct SQL state changes are prohibited.

## Triage

1. Identify the run by correlation ID and inspect its run, latest attempt, artifact, lease, and job.
2. Check worker liveness and readiness separately. Readiness requires database, queue, lease store,
   and the worker accepting new work.
3. Run the read-only integrity scan. Treat checksum, lineage, multiple-success, or multiple-artifact
   findings as integrity incidents; do not retry them automatically.
4. Use the deterministic recovery inspection result. Allowed actions are reconstructing a missing
   artifact from a successful attempt, completing a run whose artifact is durable, or enqueueing a
   bounded retry. A no-op is successful and idempotent.

## Common incidents

- **Succeeded attempt, missing artifact:** reconstruct from the stored validated output, verify its
  checksum, persist once, then complete the run.
- **Artifact persisted, run still running:** verify checksum and complete the run idempotently.
- **Expired lease and failed/timed-out attempt:** release the lease and enqueue only if the repair
  budget remains. Never create a third attempt when the maximum is two.
- **Completed run without artifact, multiple artifacts/successes, checksum or audit failure:** stop
  automation, preserve evidence, page the integrity owner, and investigate.
- **Queue unavailable:** make workers unready, preserve current leases, and resume after queue and
  lease reconciliation.

Cancellation prevents new attempts but does not erase attempts, artifacts, reviews, approvals, or
audit evidence. Recovery callbacks must be application services and must retain actor and reason.

## Verification and escalation

After recovery, rerun integrity checks and verify run/attempt status, artifact checksum, revision
lineage, approval evidence, and audit-chain continuity. Escalate critical integrity findings
immediately. Escalate queue lag, failure rate, timeout rate, or recovery activity after alert
thresholds remain breached for the configured window.

## Backup and restore

Back up architecture runs, attempts, artifacts, reviews, revision requests, approvals, audit events,
jobs, project manifests, requirements artifacts, and approval records together. A restore is not
complete until artifact/review/approval/evidence checksums, revision lineage, and audit chain pass.
Keep artifacts, reviews, approvals, revision requests, attempt metadata, and audit events
indefinitely. Raw successful output defaults to 365 days, failure output and operational logs to 90
days, traces to 30 days, and metrics to 450 days; deletion requires retained evidence and an audit.
