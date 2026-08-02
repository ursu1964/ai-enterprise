# ADR-0004: CrewAI Behind the Application Kernel

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

CrewAI crews and flows can perform valuable reasoning and task execution, but the enterprise must
not let an agent runtime own authoritative project, approval, workflow, or audit state.

## Decision

Place CrewAI behind the application and workflow kernel. The kernel owns commands, transitions,
approvals, retries, cancellations, accepted artifacts, terminal states, and audit events. CrewAI
produces proposals, artifacts, findings, and execution results through governed adapters.

## Alternatives considered

Letting CrewAI directly mutate database state was rejected because it would bypass policy,
idempotency, approval, and audit controls.

Treating CrewAI only as a chat assistant was rejected because the platform needs structured crew
execution, not just conversational output.

## Consequences

Workers and services dispatch crew work, validate results, store artifacts, and then request kernel
state transitions.

## Constitutional principles affected

This decision strengthens deterministic coordination, safety, auditability, and replay.

## Migration and compatibility implications

CrewAI versions or providers can change behind adapters as long as kernel contracts remain stable.

## Security and privacy implications

Agents receive scoped authority and context. They do not inherit unrestricted service credentials.

## Observability and operational implications

Crew execution must emit metadata, output validation, cost/token signals when available, failure
classification, and artifact references.

## Verification and rollback

Tests must prove that project and workflow state changes happen through platform services, not
directly through agent runtime code.

## References

- [Application Kernel](../reference-architecture/15-application-kernel/README.md)
- [Agent Architecture](../reference-architecture/05-agents/README.md)
