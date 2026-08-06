# R20 Runtime Kernel status

R20 is implemented as a deterministic runtime kernel contract for coordinating the
platform lifecycle around validated manifests, knowledge graphs, execution plans,
generator execution results, and project memory.

Implemented:

- lifecycle manager with forward-only phase transitions
- service registry for compiler, graph, planner, generator, memory, validation,
  deployment, and monitoring interfaces
- append-only event stream with chained event hashes
- versioned runtime state snapshots
- scheduler projection from R17 execution plans without semantic mutation
- task-state tracking including created, completed, failed, retry, and recovery flow
- policy decisions for manifest, graph, plan, artifact traceability, and memory
- resource allocation, health, recovery, and observability snapshots
- filesystem persistence for runtime kernel snapshots
- API endpoints for contract, boot, transition, validate, recover, status, and events
- focused tests covering contract, invariants, lifecycle, scheduler, recovery,
  persistence, and OpenAPI exposure

Production boundary:

The runtime kernel is deterministic and single-node/filesystem backed. A real
distributed runtime deployment still requires operational backend integration for
cluster coordination, durable external event streaming, distributed worker leases,
and production infrastructure credentials. The application-level contract and
fail-closed validation path are now explicit.
