# Application and Workflow Kernel

## Purpose

The application kernel turns external intentions into valid state transitions. It prevents API
routes, workers, agents, and infrastructure adapters from mutating enterprise state independently.

## Command Pipeline

Every state-changing operation should pass through this conceptual route:

Request -> authentication -> authorization -> validation -> command -> idempotency check ->
aggregate or service load -> business rule enforcement -> state transition -> persistence -> domain
event -> outbox or worker dispatch.

## Command Rules

Commands express business intent: `StartRequirementsAnalysis`, `ApproveWorkflowStep`,
`CancelProjectExecution`, `RecordCrewExecutionResult`. Weak commands such as `SetStatus` or
`UpdateRow` should not become public behavior.

## Aggregate Rules

Aggregates and domain services protect invariants: terminal workflows cannot resume, approvals are
single-use, dependencies must complete before dependent steps run, and CrewAI does not own
authoritative state.

## Event Rules

Events describe completed facts in past tense. The command transaction records durable state and
event/outbox data together so asynchronous side effects do not create dual-write failures.

## Workflow Rules

Workflow instances and workflow steps must be durable. A step records dependencies, attempts,
approval requirements, lease/claim data, output references, error summaries, and version data.

## References

- [Workflow Catalog](workflow-catalog.md)
- [Context Map](context-map.md)
- [Reference: Application Kernel](../reference-architecture/15-application-kernel/README.md)
