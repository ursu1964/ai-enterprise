# R03-IR-01 — AI-Enterprise Registry Foundations and Executable Foundation Specification

Document ID: R03-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: P13 reconciliation  
Primary Dependencies: R1–R2

## Purpose

R03-IR-01 defines the first executable foundation for project registry records,
project lifecycle identity, and repository-backed foundation services.

It converts the R1/R2 concepts into implementation contracts that can be
stored, queried, validated, and reused by later architecture, AI, planning, and
generation modules.

This IR specification does not replace `1/r3.txt`; it records the implemented
R3 boundary for alignment and future extension.

## Constitutional requirements

- Foundation project records use stable project and organization identity.
- Registry records are deterministic and scoped.
- Core lifecycle state transitions are explicit.
- Duplicate registry concepts reuse existing records instead of creating
  parallel definitions.
- Foundation records expose API contracts and persistence evidence.
- Later modules consume the foundation registry instead of inventing alternate
  identities.

## Canonical domain model

The module owns these contracts:

- `FoundationProject`
- `FoundationProjectRecord`
- `RegistryEntry`
- `ProjectLifecycleState`
- `ProjectOwnership`
- `ProjectMetadata`
- `FoundationValidationResult`

## Commands

Required commands include:

- `CreateFoundationProject`
- `RegisterFoundationProject`
- `UpdateFoundationProjectMetadata`
- `ValidateFoundationProject`
- `RecordFoundationLifecycleTransition`
- `ResolveRegistryEntry`

Every mutating command includes actor, organization, project, expected revision,
idempotency key, reason, and correlation identifier.

## Events

Required events include:

- `FoundationProjectCreated`
- `FoundationProjectRegistered`
- `FoundationProjectValidated`
- `FoundationProjectLifecycleTransitioned`
- `RegistryEntryResolved`

## Security and governance

R03-IR-01 enforces organization/project isolation, ownership attribution,
registry write authority, idempotent creation, and auditability of lifecycle
changes. Registry reads are policy-filtered where project data is restricted.

## Repository implementation mapping

This IR specification is implemented as the existing R3 foundation layer:

- Runtime/domain: `apps/api/src/ai_enterprise/application/foundation_projects.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/foundation_projects.py`
- API schemas: `apps/api/src/ai_enterprise/api/foundation_project_schemas.py`
- Persistence: `migrations/versions/*project_formation*.py`
- Evidence package: `implementation/r03`
- Tests: `apps/api/tests/*foundation_project*.py`

## Acceptance criteria

R03-IR-01 is implementation-ready when:

- foundation project records can be created and queried;
- registry identity is stable and scoped;
- lifecycle transitions are explicit;
- API and persistence contracts exist;
- R4–R9 can reference foundation project identity without redefining it.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: complete through P13 and `implementation/r03`.
