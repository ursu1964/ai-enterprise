# ADR-0001: Architecture Knowledge Base First

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

AI Enterprise is growing into an operating system for governed software engineering. The roadmap is
too large for one narrative document, and crews need stable references for planning, implementation,
validation, and operations.

## Decision

Maintain the reference architecture as a structured knowledge base with stable chapter IDs,
authoritative owner paths, a shared chapter contract, cross-references, ADRs, and standards links.

## Alternatives considered

A single generated document was rejected because it would be difficult to review, easy to let drift,
and too large to maintain safely.

Scattered notes were rejected because they do not provide one authoritative location for each
enterprise concept.

## Consequences

Documentation becomes a governed product of the enterprise. Each implementation slice must update
the relevant operator guide, reference chapter, standard, or ADR when behavior changes.

## Constitutional principles affected

The decision strengthens documentation, review, traceability, and operational discipline.

## Migration and compatibility implications

Existing docs remain valid. New architecture material should link through `docs/README.md`,
`docs/architecture/README.md`, and `docs/reference-architecture/README.md`.

## Security and privacy implications

The knowledge base must not store secrets, private credentials, or unreviewed client-sensitive
material. Security rules remain governed by ETRA security and policy standards.

## Observability and operational implications

Operator-facing changes must update the relevant guide so dashboard signals, metrics, graph links,
workflow states, and recovery procedures remain understandable.

## Verification and rollback

ETRA conformance checks verify required architecture files, index links, ADR sections, and catalog
path integrity. Rollback is a normal documentation/code revert that preserves accepted ADR history
through superseding records when decisions change.

## References

- [Documentation Standard](../etra/documentation-standard.md)
- [ADR Process](../etra/adr-process.md)
- [Reference Architecture](../reference-architecture/README.md)
