# R19 Production Memory Backend Runbook

R19 defaults to filesystem-backed deterministic memory snapshots and deterministic semantic indexing.
Production backends are fail-closed until their operational references are configured.

## Backend settings

```bash
R19_MEMORY_BACKEND=filesystem|postgres|vector|custom
R19_MEMORY_SEMANTIC_INDEX_BACKEND=deterministic|pgvector|opensearch|custom
R19_MEMORY_ENDPOINT_REF=...
R19_MEMORY_DATABASE_REF=...
R19_MEMORY_INDEX_REF=...
R19_MEMORY_CREDENTIALS_REF=...
R19_MEMORY_DEPLOYMENT_EVIDENCE_REF=...
R19_MEMORY_CONNECTIVITY_EVIDENCE_REF=...
R19_MEMORY_ENCRYPTION_REQUIRED=true
R19_MEMORY_KMS_KEY_REF=...
R19_MEMORY_RBAC_POLICY_REF=...
R19_MEMORY_RETENTION_POLICY_REF=...
```

Do not put raw secrets in these values. Use secret-manager references, IAM roles, mounted secret
paths, or deployment evidence references.

## Readiness checks

Use:

```text
POST /api/v1/r19/memory/readiness
GET  /api/v1/r19/memory/production-validate
GET  /api/v1/r19/memory/semantic-index
```

External backends require:

- endpoint reference,
- credentials reference,
- deployment evidence,
- connectivity evidence.

External semantic indexes require:

- semantic index reference.

Confidential memory with encryption required also requires:

- KMS key reference.

## Authorization model

R19 denies by default. Supported API roles:

- `platform-admin`: all actions.
- `memory-admin`: all memory actions.
- `memory-writer`: write/read non-confidential memory.
- `memory-reader`: read non-confidential memory.
- `memory-service`: service write/read non-confidential memory.
- `compliance-officer`: read/export confidential memory.

Confidential records require a confidential-capable role. Export requires `platform-admin`,
`memory-admin`, or `compliance-officer`.

## Boundary

The R19 runtime validates backend readiness and produces deterministic semantic index reports. It
does not create external Postgres/vector/KMS infrastructure. Production deployment must provide the
actual backend and evidence references.
