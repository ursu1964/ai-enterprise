# R07-IR-01 — AI-Enterprise Universal Execution and Runtime Model Specification

Document ID: R07-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: P17 reconciliation  
Primary Dependencies: R2–R6

## Purpose

R07-IR-01 defines the Universal Execution and Runtime Model for describing how
generated capabilities are published, reviewed, executed, observed, and
realized as runtime records.

This IR specification does not replace `1/r7.txt`; it records the implemented
R7 runtime model boundary.

## Constitutional requirements

- Runtime definitions bind to exact generated artifacts and source baselines.
- Publish/review lifecycle transitions are explicit.
- Runtime execution records preserve inputs, outputs, status, failure, and
  evidence references.
- Runtime locations and backend adapters are validated before production use.
- Observability records and runtime governance are represented.
- Operational backend configuration is validated instead of fabricated.

## Canonical domain model

The module owns these contracts:

- `RuntimeDefinition`
- `RuntimePublication`
- `RuntimeReview`
- `RuntimeExecution`
- `RuntimeOperation`
- `RuntimeLocation`
- `RuntimeObservation`
- `RuntimeRealization`

## Commands

Required commands include:

- `CreateRuntimeDefinition`
- `PublishRuntimeDefinition`
- `ReviewRuntimePublication`
- `StartRuntimeExecution`
- `RecordRuntimeOperation`
- `RecordRuntimeObservation`
- `RegisterRuntimeLocation`
- `ValidateRuntimeBackendConfiguration`

Every mutating command includes actor, organization, project, runtime reference,
source artifact baseline, idempotency key, reason, and correlation identifier.

## Events

Required events include:

- `RuntimeDefinitionCreated`
- `RuntimeDefinitionPublished`
- `RuntimePublicationReviewed`
- `RuntimeExecutionStarted`
- `RuntimeExecutionCompleted`
- `RuntimeExecutionFailed`
- `RuntimeObservationRecorded`
- `RuntimeLocationRegistered`

## Security and governance

R07-IR-01 enforces runtime authorization, backend configuration validation,
execution evidence, tenant isolation, operational redaction, and review
separation. Runtime adapters must fail closed when production endpoints,
credentials, or deployment references are missing.

## Repository implementation mapping

This IR specification is implemented through the existing R7 UERM boundary:

- Runtime/domain: `apps/api/src/ai_enterprise/application/r7_uerm.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/r7_uerm.py`
- API schemas: `apps/api/src/ai_enterprise/api/r7_uerm_schemas.py`
- Migrations: `migrations/versions/*r7*.py`
- Evidence package: `implementation/r07`
- Tests: `apps/api/tests/test_r7*.py`

## Acceptance criteria

R07-IR-01 is implementation-ready when:

- runtime definitions can be created and published;
- review lifecycle is represented;
- executions and operations produce evidence;
- runtime location/configuration validation exists;
- production backend gaps are explicit operational configuration boundaries.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: complete through P17 and `implementation/r07`.
