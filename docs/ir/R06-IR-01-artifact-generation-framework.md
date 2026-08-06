# R06-IR-01 — AI-Enterprise Universal Artifact Generation Framework Specification

Document ID: R06-IR-01  
Version: 1.0.0  
Status: IMPLEMENTATION READY  
Classification: Constitutional Platform Module  
Implementation Target: P16 reconciliation  
Primary Dependencies: R2–R5

## Purpose

R06-IR-01 defines the Universal Artifact Generation Framework for producing
governed artifacts from normalized manifest and transformation state.

It covers generator families, lifecycle, validation, publication records,
regeneration planning, production generator packs, and provider-aware
generation boundaries.

This IR specification does not replace `1/r6.txt`; it records the implemented
R6 generation framework boundary.

## Constitutional requirements

- Generators bind to exact manifest, transformation, template, provider, and
  configuration versions.
- Generated artifacts are deterministic or explicitly marked provider-derived.
- Validation gates are recorded before publication.
- Regeneration plans identify impacted artifacts and reasons.
- Publication paths are adapter-backed and fail closed when required
  credentials or remotes are absent.
- Generator packs are registered instead of hard-coded as untraceable behavior.

## Canonical domain model

The module owns these contracts:

- `GeneratorPack`
- `GeneratorDefinition`
- `GenerationRun`
- `GenerationArtifact`
- `GenerationValidation`
- `GenerationPublication`
- `RegenerationPlan`
- `ProviderGenerationConfig`

## Commands

Required commands include:

- `RegisterGeneratorPack`
- `CreateGenerationRun`
- `ExecuteGenerator`
- `ValidateGeneratedArtifact`
- `CreateRegenerationPlan`
- `PublishGeneratedArtifact`
- `RecordPublicationResult`

Every mutating command includes actor or agent identity, organization, project,
generator reference, source baseline, idempotency key, policy context, and
correlation identifier.

## Events

Required events include:

- `GeneratorPackRegistered`
- `GenerationRunCreated`
- `GeneratorExecuted`
- `GeneratedArtifactValidated`
- `GeneratedArtifactPublished`
- `PublicationFailed`
- `RegenerationPlanCreated`

## Security and governance

R06-IR-01 enforces provider credential validation, artifact classification,
secret-safe materialization, generator-pack trust, publication preflight, and
immutable generation evidence. Generated files cannot be treated as production
ready without validation and publication evidence.

## Repository implementation mapping

This IR specification is implemented through the existing R6 UAGF boundary:

- Runtime/domain: `apps/api/src/ai_enterprise/application/r6_uagf.py`
- API routes: `apps/api/src/ai_enterprise/api/routes/r6_uagf.py`
- API schemas: `apps/api/src/ai_enterprise/api/r6_uagf_schemas.py`
- Migrations: `migrations/versions/*r6*.py`
- Evidence package: `implementation/r06`
- Tests: `apps/api/tests/test_r6*.py`

## Acceptance criteria

R06-IR-01 is implementation-ready when:

- generator packs and generator runs are represented;
- artifacts are materialized or registered with traceability;
- validation and publication records are explicit;
- regeneration planning is API exposed;
- external publication adapters fail closed without required configuration.

## Readiness verdict

Overall status: IMPLEMENTATION READY.

Repository reconciliation: complete through P16 and `implementation/r06`.
