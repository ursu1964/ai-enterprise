# R02-IR-01 — AI-Enterprise Foundational Domain and Manifest Concepts Specification

Document ID: R02-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: P12 reconciliation  
Primary Dependencies: R1

## Purpose

R02-IR-01 defines the foundational project domain and manifest concepts that
make AI-Enterprise executable instead of narrative-only.

It establishes the canonical project formation boundary, manifest identity,
traceability primitives, clarification flow, source provenance, assumptions,
ambiguities, validation findings, and snapshot semantics used by later modules.

This IR specification does not replace `1/r2.txt`; it makes the implemented R2
contract explicit for audit, release evidence, and future P-series work.

## Constitutional requirements

- Every project intake and manifest object has stable identity.
- Manifest content is hashable, versioned, and traceable to its source inputs.
- Assumptions, ambiguities, clarifications, and validation findings are first
  class records, not informal notes.
- Snapshot state is deterministic and reconstructable from persisted records.
- Source provenance is preserved for every extracted or normalized concept.
- Core manifest records remain tenant/project scoped.
- Validation failures fail closed for activation paths that require canonical
  manifest integrity.

## Canonical domain model

The module owns these contracts:

- `ProjectFormationRequest`
- `ProjectIntake`
- `Manifest`
- `ManifestSnapshot`
- `ManifestSource`
- `ClarificationQuestion`
- `ClarificationAnswer`
- `Assumption`
- `Ambiguity`
- `ValidationFinding`
- `TraceabilityLink`

## Commands

Required commands include:

- `CreateProjectFormationRequest`
- `RecordProjectIntake`
- `CreateManifestDraft`
- `ValidateManifestDraft`
- `RecordClarificationQuestion`
- `RecordClarificationAnswer`
- `RecordAssumption`
- `RecordAmbiguity`
- `CreateManifestSnapshot`
- `ActivateManifestSnapshot`

Every mutating command includes authenticated actor, organization, project,
idempotency key, reason, expected revision, and correlation identifier.

## Events

Required events include:

- `ProjectFormationRequested`
- `ProjectIntakeRecorded`
- `ManifestDraftCreated`
- `ManifestValidationCompleted`
- `ClarificationQuestionRecorded`
- `ClarificationAnswerRecorded`
- `ManifestSnapshotCreated`
- `ManifestSnapshotActivated`

## Security and governance

R02-IR-01 enforces project scoping, source provenance, actor attribution,
secret-safe source handling, validation evidence, and immutable snapshot
history. Sensitive intake content must be classified before it is exposed to
AI-assisted extraction or downstream generation.

## Repository implementation mapping

This IR specification is implemented through the existing R2 repository
boundary instead of replacing it:

- Runtime/domain: `apps/api/src/ai_enterprise/application/project_formation_service.py`
- Runtime/domain: `apps/api/src/ai_enterprise/application/aeir.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/project_formation.py`
- Schemas: `specifications/*.schema.json`
- Migrations: `migrations/versions/*r2*.py`
- Evidence package: `implementation/r02`
- Tests: `apps/api/tests/*project_formation*.py`

## Acceptance criteria

R02-IR-01 is implementation-ready when:

- project intake can create a governed manifest draft;
- manifest snapshots are hashable and versioned;
- source, assumption, ambiguity, clarification, and validation records are
  persisted or represented in the canonical schema layer;
- activation requires successful validation;
- evidence links tie manifest state to source inputs;
- R3 and later modules can consume the manifest contract without redefining it.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: complete through P12 and `implementation/r02`.
