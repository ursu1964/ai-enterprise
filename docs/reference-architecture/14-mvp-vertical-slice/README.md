# MVP Vertical Slice

## Purpose

The MVP vertical slice proves the enterprise operating model with one narrow but complete path:
manifesto intake, project persistence, requirements generation, architecture generation, artifact
storage, approval pause, decision recording, and audit history.

## Responsibilities

This chapter owns the minimum executable product boundary for P2. It defines which surfaces must be
present before the platform can be called a working AI engineering enterprise.

## Scope

The slice includes FastAPI control plane routes, PostgreSQL models, artifact storage, durable
workflow state, worker execution, human approval operations, audit records, Docker Compose startup,
and operator verification.

## Non-Scope

It does not require full autonomous implementation, production deployment, every future module, or a
separate frontend package. Those capabilities build on top of this vertical path.

## Viewpoints

Business: a client idea becomes a controlled project with visible proof. Architecture: control,
execution, and persistence planes are separate. Implementation: routes call services and workers,
not long-running crews directly. Operational: Docker and health checks prove the system starts
locally. Evolution: later implementation, review, integration, and marketplace modules reuse this
vertical path.

## Data Model

Minimum records are project, workflow run or instance, artifact, approval, audit event, job, and
execution metadata. Artifacts keep content hashes, type, version, storage reference, producer, and
lineage links.

## Interfaces

Core interfaces include project create/read, requirements runs, architecture runs, artifacts,
approval decisions, run/workflow inspection, audit timeline, health, readiness, dashboard, and
metrics.

## Dependencies

The slice depends on PostgreSQL, Alembic migrations, FastAPI, SQLAlchemy models, job dispatch,
artifact hashing, local configuration, Docker Compose, and operator actor context for governed APIs.

## Internal Components

Important components are project routes, project workflow service, job repository, database models,
workflow models, artifact models, audit records, worker dispatchers, and dashboard project
intelligence. Repository preparation is a server-side component shared by dashboard/API-created
projects so workflows do not start against repositories without a valid Git `HEAD`.

## Workflow

The required path is project created -> intake -> requirements queued -> requirements artifact
stored -> requirements approval -> architecture queued -> architecture artifact stored ->
architecture approval -> next planning phase.

## Implementation Plan

Keep the slice small and complete. First prove creation and direct lookup, then artifact integrity,
then approval gates, then worker progress, then dashboard visibility, then documentation and
conformance.

## Testing

Tests must prove direct project lookup, canonical manifesto serialization, approval rejection for
missing records, artifact hash stability, migration linearity, worker queue behavior, dashboard
presence, and accurate project phase reporting.

## Security

The MVP does not grant production trust. Sensitive operations still need actor context, repository
boundary checks, immutable audit events, and approval records.

## Observability

Operators need health, readiness, metrics, workflow history, job state, audit timeline, project
intelligence, data-source freshness, graph context status, telemetry summary, and clear dashboard
language.

## Future Evolution

The slice expands into implementation execution, review, integration, recovery, blueprint
marketplace promotion, tenant-aware security, and richer project-specific dashboards.

## References

- [MVP Vertical Slice](../../architecture/mvp-vertical-slice.md)
- [Project Execution Walkthrough](../../enterprise/project-execution-walkthrough.md)
