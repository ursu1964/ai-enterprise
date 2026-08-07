# Production readiness remaining actions

Generated from the current production-readiness gates on 2026-08-07.

Status: BLOCKED on external operational evidence.

The application code, release gates, and production-readiness validators are in place. Production launch is intentionally blocked until the following placeholder values are replaced with real reviewed infrastructure choices and durable proof references.

## Current validation commands

Run these from the repository root:

```bash
rtk make production-readiness-contracts
rtk make production-evidence-plan
rtk make production-evidence-status
rtk make production-readiness
rtk make check-production-release
```

Expected current behavior:

- `production-readiness-contracts` passes structural schema validation.
- `production-evidence-plan`, `production-evidence-status`, `production-readiness`, and `check-production-release` fail closed until real evidence is supplied.

## Infrastructure choices to replace

File: `docs/enterprise/real-world-infrastructure-decisions.json`

| Section | Required action |
|---|---|
| `domain_tls` | Replace placeholder domain and renewal proof with the real production domain and certificate-renewal evidence. |
| `identity_proxy` | Replace placeholder HMAC secret source with a real secret-manager reference. |
| `github_access` | Replace placeholder organization and secret source with the real repository organization and credential reference. |
| `database` | Replace placeholder connection secret with a real secret-manager reference. |
| `kubernetes` | Replace placeholder registry with the real image registry or explicitly reviewed disabled path. |
| `backup_restore` | Replace placeholder restore drill date and evidence with real isolated restore proof. |
| `notification` | Replace placeholder escalation policy with the real on-call/escalation reference. |

Already structurally acceptable in the current file:

- `model_service`
- `object_storage`

These still need real operator review before production use.

## Production proof to attach

File: `docs/enterprise/production-readiness-evidence.json`

Every proof item must be changed from placeholder/pending values to:

- `status: "passed"`
- real `checked_at` ISO-8601 timestamp
- real `valid_until` ISO-8601 timestamp after the release date
- durable evidence reference
- required item-specific fields

Required proof areas:

| Proof | Required evidence |
|---|---|
| `tls` | Certificate check output for the production endpoint, including expiry. |
| `proxy_identity` | Signed-request verification proving trusted identity headers cannot be forged. |
| `server_secrets` | Secret-manager audit/rotation proof; no raw secret values. |
| `backup_restore` | Isolated database restore drill output, not just a backup file. |
| `object_storage` | Read/write/delete probe against the production artifact bucket. |
| `model_endpoint` | Model endpoint probe using the production model/provider configuration. |
| `prometheus` | Scrape target proof for the production API/service. |
| `grafana` | Dashboard proof or screenshot/reference for the production dashboard. |
| `alert_routing` | Test alert ticket/reference proving the on-call route works. |
| `production_owners` | Product, technical, operations, and security owner approvals. |
| `pilot_results` | Bounded pilot evidence showing Manifest-to-project execution passed and feedback was reviewed. |
| `infrastructure_credentials` | Credential inventory and secret-manager references, with proof raw secrets are absent. |
| `production_run_artifacts` | Production release artifact, gate evidence, and deployment audit reference. |
| `r16_graph_backend` | Graph backend deployment, connectivity, credential reference, restore/export proof, and owner approval. |

## Non-negotiable rules

- Do not fabricate credentials, pilot results, owners, approval records, deployment artifacts, or backup/restore proof.
- Do not store raw secrets in JSON, Markdown, logs, artifacts, or screenshots.
- Do not mark a proof `passed` until an operator has inspected the real evidence.
- Do not bypass `check-production-release`; it is the production approval gate.
- Commit only templates, runbooks, and tooling. Environment-specific production evidence may remain ignored unless the organization explicitly decides to store sanitized evidence references in Git.

## Closure condition

Production readiness is closed only when:

```bash
rtk make check-production-release
```

passes with:

- clean Git provenance,
- valid production-readiness contracts,
- semantic production readiness allowed,
- all release gates passed,
- production release artifact verified,
- production evidence bundle complete.
