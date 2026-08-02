# Application and Workflow Kernel

## Purpose

The application kernel gives controlled behavior to the persistence layer. It translates outside
requests into valid commands, transitions, events, and asynchronous work.

## Responsibilities

It owns command definitions, command handlers, queries, query handlers, domain aggregates, domain
services, policies, workflow state machine, unit of work, idempotency, retry coordination, event
dispatch, and outbox publication.

## Scope

The kernel applies to project intake, manifesto submission, requirements analysis, architecture
generation, approval decisions, retries, cancellations, workflow resumes, CrewAI dispatch, and agent
execution result recording.

## Non-Scope

FastAPI routing, SQLAlchemy table mapping, CrewAI internals, Git providers, model providers, and
object storage are adapters. They must not own business invariants.

## Viewpoints

Business: callers request outcomes while the platform decides validity. Architecture: dependencies
point inward from adapters to application/domain rules. Implementation: one command normally commits
one transaction. Operational: failed commands produce stable errors and audit evidence. Evolution:
new workflows add commands and handlers instead of bypassing the kernel.

## Data Model

Kernel state uses workflow instances, steps, attempts, approvals, idempotency records, outbox events,
audit records, aggregate versions, leases, retries, and terminal-state markers. Events are facts and
use past-tense names.

## Interfaces

Interfaces include command bus, repository protocols, unit-of-work boundary, query handlers, domain
events, outbox claiming, workflow definitions, worker dispatch, and transport-specific adapters.

## Dependencies

The kernel depends on identity/authorization context, repositories, transaction management, durable
job/outbox storage, domain enums, workflow definitions, and audit persistence.

## Internal Components

Internal components include command DTOs, command handlers, aggregate methods, transition tables,
idempotency checks, retry policies, event records, outbox publishers, and error mappers.

## Workflow

The command pipeline is request -> authentication -> authorization -> validation -> command ->
idempotency -> aggregate load -> rule enforcement -> state transition -> persistence -> event ->
outbox -> worker execution.

## Implementation Plan

Introduce kernel behavior incrementally. Start by documenting command names and state machines,
then add tests for invalid transitions, then route state-changing APIs through handlers, then move
worker side effects behind outbox or durable job dispatch.

## Testing

Kernel tests must cover invalid transitions, terminal-state protection, approval single-use,
idempotency conflicts, dependency checks, retry limits, error mapping, and outbox idempotency.

## Security

The kernel must reject commands that lack actor context or authority. Agents and workers may request
state transitions only through scoped identities and validated command handlers.

## Observability

Every state-changing command should produce audit evidence, stable error codes, correlation IDs,
workflow history, and enough metadata for dashboards to explain the current state and next action.

## Future Evolution

The kernel should grow toward explicit command bus APIs, stronger value objects, event replay,
workflow definition versioning, richer outbox processing, and recovery workflows for terminal
failures.

## References

- [Application Kernel](../../architecture/application-kernel.md)
- [Workflow Standard](../../etra/workflow-standard.md)
