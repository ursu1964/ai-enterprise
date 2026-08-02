# Workflow Architecture

## Purpose

Workflow architecture gives the enterprise ordered movement. It turns project intent into phases,
gates, actions, evidence, and recovery paths.

## Responsibilities

It owns workflow states, task allocation, scheduling, parallel execution, approval gates, handoffs,
history, error paths, and operator recommendations.

## Data Model

Workflow instances, transitions, jobs, artifacts, approvals, execution events, and audit records
form the state trail.

## Workflow

The standard project workflow is project creation, intake, requirements run, requirements approval,
architecture run, architecture approval, work-package planning, work-package approval, execution,
review, integration, and blueprint promotion. A project should not appear to be in requirements work
until a workflow or job has actually started that phase.

## Testing

Workflow tests must verify allowed transitions, rejected transitions, idempotency, audit emission,
job queue behavior, and dashboard next-action language.

## Evolution

Future workflows should support richer parallel project execution, better schedule optimization,
client-specific gates, and automatic improvement loops.

## References

- [Workflow Catalog](../../architecture/workflow-catalog.md)
- [Workflow Standard](../../etra/workflow-standard.md)
