# Production Readiness Evidence

Production readiness is an evidence decision, not a claim based on configuration templates. A
production release must have both real infrastructure decisions and current operational proof.

Current unresolved operational actions are tracked in
`docs/enterprise/production-readiness-remaining-actions.md`.

## Prepare the bundle

1. Copy `real-world-infrastructure-decisions.template.json` to
   `real-world-infrastructure-decisions.json` and replace every placeholder with the selected
   provider, owner, secret source, retention policy, and escalation route.
2. Copy `production-readiness-evidence.template.json` to
   `production-readiness-evidence.json`.
3. Run each production probe and record its timestamp, expiry, and durable evidence location.
4. Set a proof status to `passed` only after an operator has inspected the result.

The required proof areas are TLS, trusted proxy identity, server-secret rotation, database restore,
object-storage access, the model endpoint, Prometheus scraping, the Grafana dashboard, test-alert
routing, named production owners, pilot results, infrastructure credential references, and
production run artifacts. The backup entry must identify an isolated restored database; a backup
file alone is not restore proof.

## Verify and release

```bash
rtk make production-evidence-plan
rtk make production-readiness
rtk make release-gate-evidence-release
rtk make production-release-artifact
```

For a single fail-closed production release gate, run:

```bash
rtk make check-production-release
```

The evidence plan command writes `artifacts/production-evidence-plan.json`. It lists every proof
area, missing field, suggested owner, and validation command needed to collect real production
evidence. It does not approve production by itself; it fails closed until the same readiness rules
pass.

The readiness command writes `artifacts/production-readiness.json`. The production release artifact
reruns the same validation, records the production evidence plan, and fails closed if a proof is
missing, expired, pending, or not tied to real infrastructure decisions. Non-production release
artifacts do not pretend to carry production approval.

Evidence paths can be artifact paths, immutable object-storage locations, monitoring snapshots, or
ticket URLs. Do not place secret values in the bundle; record the secret-manager reference,
credential inventory reference, and rotation proof instead. Pilot proof must identify the bounded
pilot project and show that Manifest-to-project execution passed and feedback was reviewed. Run
artifact proof must link the production release artifact, captured gate evidence, and deployment
audit record.
