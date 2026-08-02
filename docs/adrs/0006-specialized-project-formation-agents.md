# ADR-0006: Specialized Project Formation Agents

- Status: accepted
- Date: 2026-08-01
- Owners: enterprise-architecture
- Supersedes: none
- Exception expiry: none

## Context

Project creation should not depend on one monolithic assistant. P6 defines a formation workflow where
business analysis, architecture, planning, risk/compliance, and documentation are separate reviewed
responsibilities.

## Decision

Use a Project Orchestrator with specialized formation agents. Start with a small reliable group:
business analyst, solution architect, project planner, risk/compliance analyst, and documentation
agent. Add more specialists only after the formation workflow is stable.

## Alternatives considered

A single general assistant was rejected because it mixes responsibilities and makes validation
harder.

Starting with 50 to 100 agents was rejected because it adds coordination complexity before the core
project-formation product is proven.

## Consequences

Agent contracts, output schemas, validation gates, and human approval become first-class project
formation requirements.

## Constitutional principles affected

This decision strengthens specialization, reviewability, human control, and modular evolution.

## Migration and compatibility implications

Existing dashboard vision clarification and manifesto creation become the first intake surface for
the formation workflow.

## Security and privacy implications

Agents cannot approve their own work, change budget/scope without authority, or write final records
without validation.

## Observability and operational implications

Formation stages must be visible through history, artifacts, validation results, approval state, and
dashboard guidance.

## Verification and rollback

Tests must cover manifesto persistence, stage schemas, validation failures, and approval gates.
Rollback is an ADR supersession if the formation model changes.

## References

- [Project Formation Orchestration](../reference-architecture/17-project-formation-orchestration/README.md)
- [Agent Standard](../etra/agent-standard.md)
