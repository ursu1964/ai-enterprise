# Runtime Architecture

## Purpose

Runtime architecture explains how the enterprise runs continuously: API, workers, migrations,
database, providers, repositories, queues, telemetry, and recovery.

## Responsibilities

It owns worker services, scheduler behavior, sandbox execution, resource management, model/provider
readiness, Docker Compose startup, environment configuration, and runtime failure handling.

## Interfaces

Runtime operators use Compose commands, health endpoints, readiness, metrics, worker logs, job APIs,
execution events, and audit surfaces.

## Workflow

Startup creates configuration, runs migrations, starts services, verifies readiness, bootstraps local
authority, registers projects, and begins workflows when a manifest launch is requested.

## Observability

Required signals include health, readiness, request metrics, queue pressure, worker instances,
execution events, failed jobs, recovery attempts, and dashboard data-source freshness.

## Evolution

Runtime should grow toward stronger isolation providers, richer scheduling, provider calibration,
parallel manifesto execution, and long-running autonomous operation.

## References

- [Operator Startup Guide](../../enterprise/operator-startup-guide.md)
- [Service Operations Runbook](../../runbooks/service-operations.md)
