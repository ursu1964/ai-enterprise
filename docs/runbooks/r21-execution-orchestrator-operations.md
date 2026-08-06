# R21 Execution Orchestrator operations

Minimum operational flow:

1. Submit a strict canonical Manifest to `/api/v1/r21/projects/{project_id}/compile`.
2. Create an execution plan from the compilation result.
3. Start execution from the plan.
4. Review pending approval gates and bind decisions to the exact artifact hashes.
5. Resume execution after all required approval roles have approved.
6. Recover from the latest checkpoint if the runtime process restarts.
7. Export evidence, provenance, and traceability before accepting the delivery
   package.

Production readiness checks:

- R21 database migration `d6e8f2a1c9b4` applied
- durable execution/event/checkpoint store configured
- platform audit stream accepts `r21:*` stream IDs
- worker identity and capability-token issuer configured
- artifact repository configured
- approval authority source configured
- telemetry sink configured without sensitive Manifest payload leakage
- retry and promotion policies reviewed
- recovery procedure tested from a checkpoint
