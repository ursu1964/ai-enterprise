# BK/R11 Evidence and Audit Engine specification

Status: derived implementation specification.

Source boundary: `1/bk.txt` names `R11-IR-01 — Evidence and Audit Engine`,
but does not include its body. This document records the explicit local
specification used for implementation until a canonical BK/R11 body is supplied.

## Purpose

BK/R11 preserves proof after BK/R10 verification. It makes evidence durable,
auditable, exportable, hash-verifiable, and safe to use for later governance
without allowing acceptance to depend on unverifiable claims.

## Required guarantees

- Evidence artifacts have stable identifiers, source URIs, content hashes,
  capture authority, classification, retention class, subject links, and a
  deterministic artifact hash.
- Audit records form append-only hash chains per stream.
- Every audit record that supports acceptance references at least one evidence
  artifact.
- Evidence coverage is evaluated per verification obligation and required
  evidence type.
- Acceptance is fail-closed when coverage is incomplete, audit chain integrity
  fails, or audit records reference missing evidence.
- Sensitive metadata keys are redacted before hashing or packaging.
- The package manifest hash covers baselines, evidence, audit records, coverage,
  integrity, acceptance status, and blockers.

## Current implementation

- Runtime: `apps/api/src/ai_enterprise/application/bk_r11_evidence_audit_runtime.py`
- Persistence service: `apps/api/src/ai_enterprise/application/bk_r11_persistence_service.py`
- API schemas: `apps/api/src/ai_enterprise/api/bk_r11_evidence_audit_schemas.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/bk_r11_evidence_audit.py`
- SQL models: `apps/api/src/ai_enterprise/infrastructure/bk_r11/models.py`
- Migration: `migrations/versions/a1d5e8f2b9c4_add_bk_r11_evidence_audit_records.py`
- Archive publication migration:
  `migrations/versions/b2e6f9a3c8d1_add_bk_r11_archive_publication_records.py`
- Published schemas: `schemas/evidence-audit/*.schema.json`
- Published registry: `registry/evidence-audit/bk-r11-default.json`
- Example package: `examples/evidence-audit/bk-r11-package.json`
- Tests: `apps/api/tests/test_bk_r11_evidence_audit_runtime.py`
- Persistence tests: `apps/api/tests/test_bk_r11_evidence_audit_persistence.py`
- Contract tests: `apps/api/tests/test_bk_r11_evidence_audit_contracts.py`

## Production backend contract

BK/R11 exposes archive/signature readiness without fabricating external systems.

- Supported archive backend identifiers: `filesystem`, `s3`, `gcs`,
  `azure_blob`, `minio`, `custom`.
- Supported signature provider identifiers: `disabled`, `mock`, `kms`,
  `custom`.
- Production/staging fails closed when external archive backends lack archive
  URI references, credential references, deployment evidence, or connectivity
  evidence.
- Encryption-required operation fails closed without a KMS key reference.
- Signature-required operation fails closed without a signer key reference.
- Mock archive/signature mode is forbidden for production/staging.
- KMS/custom signing returns an external signature request reference; the app
  can execute configured command adapters, and does not fabricate a signature
  when those adapters are unavailable.

API endpoints:

- `POST /api/v1/bk/r11-evidence-audit/archive-readiness`
- `POST /api/v1/bk/r11-evidence-audit/packages/export`
- `POST /api/v1/bk/r11-evidence-audit/packages/export-signed`
- `POST /api/v1/bk/r11-evidence-audit/packages/sign`
- `POST /api/v1/bk/r11-evidence-audit/packages/publish-archive`
- `POST /api/v1/bk/r11-evidence-audit/packages/verify-publication`
- `GET /api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-publications`
- `GET /api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-verifications`
- `GET /api/v1/bk/r11-evidence-audit/projects/{project_id}/archive-summary`

Signature providers:

- Mock signing is deterministic and limited to non-production use.
- AWS KMS signing is command-backed through `aws kms sign`.
- Custom signing is command-backed through a configured executable. The command
  receives `--key-ref` and `--digest-sha256` and must return JSON containing
  `signature` or `signature_reference`.

Physical publication:

- The filesystem archive backend is implemented and writes deterministic archive
  bytes plus publication metadata under the configured managed archive root.
- S3 publication is command-backed through `aws s3 cp`.
- GCS publication is command-backed through `gsutil cp` or `gcloud storage cp`.
- Azure Blob publication is command-backed through `az storage blob upload`.
- MinIO publication is command-backed through `mc cp`.
- Command-backed publication fails closed when the required executable is not
  installed or the destination URI does not match the backend.
- Filesystem publication verification recomputes the local archive SHA256 and
  validates the publication metadata sidecar.
- Remote publication verification probes the archive and metadata references via
  the configured CLI and reports `remote_reference_verified`; it does not claim
  content-hash verification unless the object is physically downloaded.
- Archive publication records and verification reports are persisted as
  append-only SQL projections and audit-chain events when requested through API
  persist flags.
- Persisted archive publications and verification reports are queryable by
  project and optional package id with a bounded result limit.
- Project-level archive summary reports publication count, verification count,
  failed verification count, latest records, derived status, and summary hash.

## Published external contracts

BK/R11 now publishes standalone contract artifacts for consumers outside the
FastAPI process:

- `schemas/evidence-audit/evidence-package.schema.json` validates package
  manifests, artifacts, audit records, coverage reports, and integrity reports.
- `schemas/evidence-audit/archive-backend.schema.json` defines supported archive
  and signature configuration fields.
- `schemas/evidence-audit/archive-publication.schema.json` validates archive
  publication records.
- `schemas/evidence-audit/archive-verification.schema.json` validates archive
  verification reports.
- `registry/evidence-audit/bk-r11-default.json` mirrors runtime evidence types,
  archive backends, signature providers, and fail-closed rules.
- `examples/evidence-audit/bk-r11-package.json` provides a canonical accepted
  package example.

The contract tests validate every schema as JSON Schema Draft 2020-12, validate
the example package, validate generated runtime packages against the published
schema, and ensure the registry matches the runtime/API contract.

## Deferred integration

- Native SDK adapters for S3/GCS/Azure/MinIO/custom archive backends.
- Native SDK KMS/custom signature provider clients.
