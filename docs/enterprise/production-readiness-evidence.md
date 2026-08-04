# Production Readiness Evidence

Production readiness is an evidence decision, not a claim based on configuration templates. A
production release must have both real infrastructure decisions and current operational proof.

## Prepare the bundle

1. Copy `real-world-infrastructure-decisions.template.json` to
   `real-world-infrastructure-decisions.json` and replace every placeholder with the selected
   provider, owner, secret source, retention policy, and escalation route.
2. Copy `production-readiness-evidence.template.json` to
   `production-readiness-evidence.json`.
3. Run each production probe and record its timestamp, expiry, and durable evidence location.
4. Set a proof status to `passed` only after an operator has inspected the result.

The required proof areas are TLS, trusted proxy identity, server-secret rotation, database restore,
object-storage access, the model endpoint, Prometheus scraping, the Grafana dashboard, and test-alert
routing. The backup entry must identify an isolated restored database; a backup file alone is not
restore proof.

## Verify and release

```bash
rtk make production-readiness
rtk make release-gate-evidence-release
rtk make production-release-artifact
```

The first command writes `artifacts/production-readiness.json`. The production release artifact
reruns the same validation and fails closed if a proof is missing, expired, pending, or not tied to
real infrastructure decisions. Non-production release artifacts do not pretend to carry production
approval.

Evidence paths can be artifact paths, immutable object-storage locations, monitoring snapshots, or
ticket URLs. Do not place secret values in the bundle; record the secret-manager reference and
rotation proof instead.
