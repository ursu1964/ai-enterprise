# ADR-0002: Modular Monolith First

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

AI Enterprise has many domains: projects, workflows, approvals, artifacts, agents, crews, security,
operations, recovery, and evolution. Splitting these too early would make transactions, testing,
and local operation harder before the core behavior is stable.

## Decision

Build as a modular monolith first. Keep domain, application, infrastructure, API, and worker
boundaries explicit inside one deployable repo. Extract services later only when operational
pressure and ownership boundaries justify the cost.

## Alternatives considered

Microservices first was rejected because it would increase network coupling, distributed
transactions, deployment complexity, and observability burden before product behavior is mature.

A single unstructured application was rejected because it would hide boundaries and make future
service extraction unsafe.

## Consequences

The repo must preserve clear module boundaries, route/service separation, inward dependency rules,
and test coverage around domain invariants.

## Constitutional principles affected

This decision strengthens simplicity, testability, local operability, and controlled evolution.

## Migration and compatibility implications

Future service extraction must preserve API contracts, database ownership, event semantics, and
operator behavior.

## Security and privacy implications

Security controls remain centralized enough for consistent policy enforcement while modules mature.

## Observability and operational implications

Local Compose operation remains practical. Observability can focus first on clear lifecycle,
worker, job, and audit signals.

## Verification and rollback

Conformance checks enforce repository layout and dependency discipline. Rollback is unnecessary
unless service extraction becomes required by scale or isolation.

## References

- [Platform Architecture](../reference-architecture/08-platform/README.md)
- [Application Kernel](../reference-architecture/15-application-kernel/README.md)
