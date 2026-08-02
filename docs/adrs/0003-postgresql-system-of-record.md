# ADR-0003: PostgreSQL System of Record

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

The platform must preserve projects, manifestos, artifacts, approvals, workflows, jobs, audit
events, execution evidence, identities, and governance decisions. These records must survive worker
restarts and remain queryable outside any agent framework.

## Decision

Use PostgreSQL as the authoritative enterprise system of record. Framework checkpoints, object
storage, graph files, and caches may support execution, but they do not replace the database for
governed state.

## Alternatives considered

Framework-only persistence was rejected because it would make project state dependent on one
orchestration runtime.

Document-only storage was rejected because approval, audit, workflow, and tenant constraints need
transactional guarantees.

## Consequences

Migrations, models, repository behavior, transaction boundaries, and audit records become core
platform contracts.

## Constitutional principles affected

This decision strengthens auditability, recoverability, traceability, and operator confidence.

## Migration and compatibility implications

Schema changes require migrations and compatibility care. Artifact bodies may live outside the
database, but database rows keep hashes, URI references, versions, and lineage.

## Security and privacy implications

Tenant-owned records need tenant boundaries and future row-level security. Application runtime roles
must not own schema migration authority.

## Observability and operational implications

Health, readiness, migrations, queue pressure, audit queries, and dashboard state depend on database
availability.

## Verification and rollback

Migration linearity, integration tests, and conformance checks guard this decision. Rollback requires
a deliberate ADR because it changes the platform's authority model.

## References

- [MVP Vertical Slice](../reference-architecture/14-mvp-vertical-slice/README.md)
- [Database Standard](../etra/database-standard.md)
