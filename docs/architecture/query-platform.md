# Query Platform

## Purpose

The Query Platform turns governed enterprise records into read-only operating pictures for humans,
dashboards, agents, and automation. It does not approve work, advance workflows, change state, or
repair data. Its job is to answer what exists, what is moving, what needs attention, and what action
is recommended next.

## Current Slice

The first implementation exposes `/api/v1/query/operating-picture` and
`/api/v1/query/projects/{project_id}/operating-picture`. These endpoints compose projects,
workflows, jobs, workers, enterprise kernel records, performance metrics, learning proposals,
knowledge items, artifacts, crew runs, and audit events into human-readable summaries, status
counts, freshness metadata, recommendations, and graph nodes.

## Read-Only Rule

Query routes are projections over authoritative records. They must not mutate aggregates, create
audit side effects, approve commands, retry jobs, change ownership, or bypass command authorization.
When a query discovers a problem, it returns a recommendation that points the operator to an
explicit command or dashboard action.

Dead-letter jobs remain immutable failure evidence. When an operator has reviewed an old failure and
recorded the recovery decision, the job can be acknowledged through the operator API. Acknowledged
dead letters stay visible in job history but no longer count as unresolved current health problems.

## Dashboard Contract

The central manager dashboard consumes the operating picture as its common source for business
state, movement graph data, recommendations, and source freshness. This reduces duplicated frontend
interpretation and keeps project, problem, telemetry, and graph panels aligned with one governed
read model.

## Future Work

Later P14 slices should add formal query objects, `QueryContext`, query dispatcher, named read-model
ownership, projection checkpoints, rebuild tooling, cache policy, full-text search, graph query
adapters, query telemetry, and freshness SLOs. Those pieces should be added only when the projection
contract is stable enough to support multiple dashboards and external clients.

## References

- [Platform Architecture](../reference-architecture/08-platform/README.md)
- [Product Architecture](../reference-architecture/02-product/README.md)
- [Operator Startup Guide](../enterprise/operator-startup-guide.md)
