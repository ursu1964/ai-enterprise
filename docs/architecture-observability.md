# Architecture observability specification

## Dashboard

The primary dashboard shows run throughput and status, attempt latency and outcomes, repair rate,
timeout rate, queue depth/age, active and expired leases, artifact persistence latency, review and
approval outcomes, recovery actions, and integrity findings. Filters are limited to bounded status,
action, severity, and worker-role values. Identifiers belong in traces and logs, never metric labels.

## Alerts

| Alert | Suggested condition | Severity |
| --- | --- | --- |
| ArchitectureRunFailureRateHigh | failures above 20% for 15 minutes | warning |
| ArchitectureExecutionTimeoutRateHigh | timeout rate above SLO for 15 minutes | warning |
| ArchitectureValidationFailureRateHigh | validation failure rate above SLO | warning |
| ArchitectureRepairRateHigh | repair rate above SLO | warning |
| ArchitectureWorkerNoHeartbeat | no heartbeat for 5 minutes | high |
| ArchitectureQueueBacklogHigh | oldest queued job above SLO for 10 minutes | high |
| ArchitectureReviewBacklogHigh | review age or count above SLO | warning |
| ArchitectureApprovalDenialSpike | denial rate above baseline | warning |
| ArchitectureAuditWriteFailure | any audit write failure | critical |
| ArchitectureRecoveryFailure | recovery cannot reconcile evidence | critical |

Logs contain event name, correlation and aggregate identifiers, bounded statuses, duration, actor
reference, and error class. They exclude prompts, raw model output, artifact/review/approval content,
credentials, tokens, and authorization headers. Required trace spans are `architecture.run`,
`architecture.attempt`, `architecture.validation`, `architecture.persist_artifact`,
`architecture.review`, `architecture.approval`, and `architecture.recovery`.

Integrity scanning is read-only, runs every 15 minutes, and emits findings without repairing state.
