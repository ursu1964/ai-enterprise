# Platform Architecture

## Purpose

The platform architecture defines the technical foundation that keeps enterprise behavior reliable,
auditable, and extensible.

## Responsibilities

It owns CQRS direction, event platform, query platform, persistence, PostgreSQL schema discipline,
metadata kernel, service boundaries, API contracts, and integration points.

## Data Model

PostgreSQL is the system of record for projects, artifacts, approvals, jobs, workflows, audit
events, organization records, runtime sessions, recovery records, and evolution data.

## Interfaces

FastAPI exposes versioned APIs under `/api/v1`. Workers consume durable jobs. Dashboards consume
operator and telemetry APIs. Graphify exposes code architecture navigation.

The first dedicated Query Platform surface is `/api/v1/query/operating-picture`. It provides a
read-only operating picture with human summaries, status counts, freshness metadata, recommended
next actions, and graph nodes for the central manager dashboard. Project-specific read models are
available at `/api/v1/query/projects/{project_id}/operating-picture`.

## Security

Platform services enforce boundaries through schema validation, actor headers, authority checks,
repository allowed roots, secret hygiene, and audit records.

## Evolution

The platform should remain modular-monolith-first until operational pressure proves that splitting a
service has more value than preserving local transactional clarity.

## References

- [Context Map](../../architecture/context-map.md)
- [Query Platform](../../architecture/query-platform.md)
- [Database Standard](../../etra/database-standard.md)
