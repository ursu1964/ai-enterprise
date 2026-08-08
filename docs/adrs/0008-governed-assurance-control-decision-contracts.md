# ADR-0008: Governed Assurance Control, Authority, and Decision Contracts

- Status: accepted
- Date: 2026-08-08
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

The R2-R22 baseline establishes the executable product-platform architecture and ADR-0007 governs
post-R22 roadmap expansion. New semantic material now needs to describe how the platform represents
controls, formal authority, and decisions without prematurely creating an R23 source module.

The gap is not another implementation phase. It is an architectural clarification of how existing
policy, obligation, evidence, identity, authority, risk, and execution concepts compose into an
evidence-backed assurance graph.

## Decision

Record the Control Contract Model, Authority extension semantics, and Decision Contract Model as an
ADR-backed architecture document:

- [Governed Assurance Control and Decision Contracts](../architecture/governed-assurance-control-decision-contracts.md)

This is an ADR-only governance change under ADR-0007. It does not authorize a new `1/r23.txt`, does
not change the R2-R22 baseline, and does not create a new implementation package.

The new architecture document defines:

- controls as governed mechanisms whose effectiveness must be evidence-backed;
- certification, attestation, quorum, independence, emergency, and AI authority extensions;
- decisions as reconstructible governed conclusions rather than approval flags;
- validation errors, invariants, query surfaces, and temporal reconstruction requirements.

## Consequences

Post-R22 architecture work can now discuss control effectiveness, authority validity, and decision
validity using stable terms without weakening the roadmap sequence gate.

Implementation remains future work unless separately authorized through a concrete implementation
plan, accepted ADR, or explicitly scoped change inside an existing R2-R22 module.

The document becomes a reference for future schema, API, persistence, policy, and assurance work.

## Alternatives considered

Creating `1/r23.txt` immediately was rejected because ADR-0007 requires a separate roadmap-module
authorization before any new R-series source specification is introduced.

Embedding this material only in application code was rejected because the current change defines
semantic contracts and invariants rather than an executable implementation slice.

Leaving the material uncommitted was rejected because future implementation planning needs stable,
reviewable references for control, authority, and decision semantics.

## Constitutional principles affected

This decision strengthens traceability, auditability, explicit authority, evidence-backed assurance,
non-duplication, and controlled evolution.

## Migration and compatibility implications

No database migration, public API change, runtime behavior change, or R2-R22 baseline mutation is
introduced by this ADR. Future implementation work must define its own migration and compatibility
plan before adding schemas, persistence, APIs, or generated artifacts.

## Security and privacy implications

The contracts add stronger semantics for control evidence, authority proof, decision provenance,
AI boundaries, emergency authority, attestation, and certification. Sensitive identity, authority,
and evidence data must remain subject to least-privilege disclosure when implemented.

## Observability and operational implications

Future implementation should expose control coverage, effectiveness freshness, decision validity,
authority validation, bypass detection, and reassessment events as governed operational signals.
This ADR does not change current production operation.

## Verification and rollback

Verification for this ADR is documentation-level:

- the roadmap sequence gate must continue to pass;
- no `1/r23.txt` or new R-series implementation package is introduced;
- the architecture index links to the new document.

Rollback requires superseding this ADR rather than deleting it.

## References

- [ADR-0007: Post-R22 Roadmap Governance](0007-post-r22-roadmap-governance.md)
- [Governed Assurance Control and Decision Contracts](../architecture/governed-assurance-control-decision-contracts.md)
- [R-INDEX](../R-INDEX.md)
- [Architecture Baseline v1.0](../ARCHITECTURE-BASELINE-v1.0.md)
