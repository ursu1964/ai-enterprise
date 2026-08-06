# Production Deployment Verification Runbook

Owner: release manager. This runbook is fail-closed. A blocked result means the
system refused to approve production without real evidence; it is not a reason
to bypass the gate.

## Preconditions

1. Work from the repository root.
2. Use a clean committed tree for release evidence. The release artifact rejects
   dirty or unknown Git state.
3. Do not put raw secrets into evidence files. Record secret-manager references,
   ticket IDs, immutable artifact paths, or external proof URLs.
4. Do not mark any proof `passed` until the real command output, ticket,
   approval, or external audit record exists.

## Exact verification sequence

### 1. Verify local code and migration health

Run:

```bash
rtk bash -lc 'cd /home/user/projects/ai-enterprise/apps/api && uv run ruff check ../../tools/bk_roadmap_audit.py tests/test_bk_r11_evidence_audit_contracts.py && uv run pytest -p no:cacheprovider tests/test_bk_r11_evidence_audit_contracts.py tests/test_bk_roadmap_audit_tool.py tests/test_bk_r11_evidence_audit_runtime.py tests/test_bk_r11_evidence_audit_persistence.py -q && uv run alembic check'
```

Expected result:

- Ruff passes.
- Focused BK/R11 tests pass.
- Alembic reports no new upgrade operations.

Correction rule:

- Fix code, schemas, tests, or migrations before continuing.

### 2. Generate the production evidence collection plan

Run:

```bash
rtk make production-evidence-plan
```

Expected result before real production setup:

- `artifacts/production-evidence-plan.json` is written.
- The command may exit non-zero while evidence is missing.
- `production_allowed` remains `false`.
- Each proof and infrastructure section includes `blocked` and
  `validation_findings`, so operators can distinguish missing fields from
  present-but-invalid placeholders or pending proof.

Correction rule:

- Treat every listed missing proof as an operator assignment.
- Do not edit the plan to force readiness.

For a compact release-manager view, run:

```bash
rtk make production-evidence-status
```

This writes `artifacts/production-evidence-status.json` with blocked proof
counts, blocked infrastructure choice counts, owner hints, findings, and next
commands. It also writes `artifacts/production-evidence-status.md`, a human
checklist suitable for release review or operator assignment.

### 3. Create infrastructure choices from the template

Preferred initialization command:

```bash
rtk make production-evidence-init
```

This creates both working input files from templates when they do not already
exist and writes `artifacts/production-evidence-init.json`. It does not approve
production and leaves every proof pending until a real operator fills it.
The generated JSON input files are intentionally ignored by Git; commit the
templates and runbooks, not environment-specific production evidence.
The input file structure is published under
`schemas/production-readiness/*.schema.json`; these schemas validate shape only,
while the readiness tools enforce real values, timestamps, owner proof, and
placeholder rejection.

Fast structural validation:

```bash
rtk make production-readiness-contracts
```

This writes `artifacts/production-readiness-contracts.json` and should pass
before semantic readiness validation.

The aggregate release command enforces the same order:

```bash
rtk make check-production-release
```

Order: evidence plan, structural contracts, semantic readiness, release gate
evidence, production release artifact, JSON/Markdown artifact verification.

Manual equivalent:

Run:

```bash
cp docs/enterprise/real-world-infrastructure-decisions.template.json docs/enterprise/real-world-infrastructure-decisions.json
```

Fill every required field with real reviewed production values:

- domain and TLS provider
- trusted identity/proxy provider and signed headers
- model service provider, endpoint, model, and verification command
- GitHub/repository access mode and secret source
- database mode, connection secret reference, backup policy, restore cadence
- object storage provider, bucket, region, encryption, retention policy
- Kubernetes/registry/namespace/ingress/storage/worker choices
- backup/restore schedule and drill evidence
- alert channel, on-call owner, escalation policy

Then run:

```bash
rtk make infrastructure-choices-verify
```

Expected result:

- The command passes only when placeholders are replaced by real values.

Correction rule:

- Replace placeholders with real values or references.
- Do not store inline credentials.

### 4. Create production readiness evidence from the template

If `rtk make production-evidence-init` was already used, edit the generated
`docs/enterprise/production-readiness-evidence.json`. Otherwise, use the manual
copy command below.

Run:

```bash
cp docs/enterprise/production-readiness-evidence.template.json docs/enterprise/production-readiness-evidence.json
```

For every proof item, set:

- `status`: `passed`
- `checked_at`: ISO-8601 timestamp when the evidence was checked
- `valid_until`: ISO-8601 timestamp after the release date
- `evidence`: durable proof reference
- every required item-specific field

Required proof categories:

- TLS certificate
- proxy identity
- server secrets and rotation
- backup restore drill
- object storage read/write/delete probe
- model endpoint probe
- Prometheus scrape target
- Grafana dashboard
- alert routing test
- production owners
- pilot results
- infrastructure credential inventory
- production run artifacts
- R16 graph backend deployment/connectivity/credential/restore/approval proof

Then run:

```bash
rtk make production-readiness
```

Expected result:

- `artifacts/production-readiness.json` is written.
- `production_allowed` is `true` only when every proof is valid and current.

Correction rule:

- Fix the underlying production setup or evidence reference.
- Do not fabricate owners, credentials, pilot results, or deployment artifacts.

### 5. Capture release gate evidence

Run:

```bash
rtk make release-gate-evidence-release
```

Expected result:

- `artifacts/gate-evidence.json` is written.
- Per-gate logs are written under `artifacts/release-gates/`.
- The command passes only when every release gate passes and Git provenance is
  clean/stable.

Correction rule:

- Fix the failing gate.
- Commit the intended release state.
- Rerun gate evidence after corrections.

### 6. Generate the production release artifact

Run:

```bash
rtk make production-release-artifact
```

Expected result:

- `artifacts/production-release-verification.json` is written.
- `artifacts/production-release-verification.md` is written as a human audit
  summary.
- The artifact status is `passed` only when:
  - structural production readiness contracts are valid,
  - production readiness is allowed,
  - migration verification is conformant,
  - required release gate evidence exists,
  - gate log hashes match,
  - gate evidence Git commit/tree match the current clean tree.

Correction rule:

- If the artifact fails, correct the specific failing gate/evidence/provenance
  problem and regenerate it. Do not hand-edit the artifact to pass.
- Direct `rtk make production-release-artifact` usage still records and enforces
  the structural contract report; the aggregate target is not the only defense.
- Treat JSON as the source of truth and Markdown as the review summary.
- Release artifact schemas are published under `schemas/release-artifacts/`.
- Verify JSON/Markdown consistency before archive:

  ```bash
  rtk make production-release-artifact-verify
  ```

  This writes `artifacts/production-release-verification-check.json`; archive it
  with the release JSON and Markdown summary.

- Build the BK/R11 handoff manifest:

  ```bash
  rtk make production-release-evidence-bundle
  ```

  This writes `artifacts/production-release-evidence-bundle.json`, including the
  required release/readiness artifacts, each artifact hash, content type, and
  schema reference when one exists. The target fails closed when any required
  artifact is missing.

### 7. Archive evidence with BK/R11

After the production release artifact passes, publish the release evidence using
the BK/R11 archive flow:

1. Build or select the accepted evidence package from
   `artifacts/production-release-evidence-bundle.json`.
2. Export/sign the package if signatures are required.
3. Publish to the configured archive backend.
4. Verify the publication.
5. Persist the publication and verification records.

Minimum API sequence:

```text
POST /api/v1/bk/r11-evidence-audit/archive-readiness
POST /api/v1/bk/r11-evidence-audit/packages/export-signed
POST /api/v1/bk/r11-evidence-audit/packages/publish-archive
POST /api/v1/bk/r11-evidence-audit/packages/verify-publication
GET  /api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-summary
```

Expected result:

- Archive readiness is `ready`.
- Publication status is `published`.
- Verification status is `verified` for filesystem archives, or
  `remote_reference_verified` for command-backed remote probes that do not
  download and hash the object.

Correction rule:

- Fix archive backend credentials/configuration/connectivity.
- Do not claim remote content-hash verification unless the object was physically
  downloaded and hashed.

## Current local result interpretation

If production gates currently report:

- missing `docs/enterprise/real-world-infrastructure-decisions.json`
- missing `docs/enterprise/production-readiness-evidence.json`
- missing `artifacts/gate-evidence.json`
- dirty Git tree

then the correct state is `blocked`, not `ready`. Complete the real operational
inputs, run the exact sequence again, and only deploy after the final production
release artifact passes.
