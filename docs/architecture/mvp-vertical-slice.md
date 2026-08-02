# MVP Vertical Slice

## Purpose

The MVP vertical slice proves that AI Enterprise is executable, not only conceptual. The platform
must accept a manifesto, persist a project, generate controlled requirements and architecture
artifacts, pause for approval, and preserve every important decision.

## Current Implementation Mapping

| P2 Capability | Current Repo Surface |
| --- | --- |
| FastAPI control plane | `apps/api/src/ai_enterprise/main.py` and versioned `/api/v1` routes |
| PostgreSQL state | SQLAlchemy models and Alembic migrations |
| Project creation | `/api/v1/projects` |
| Direct project lookup | `/api/v1/projects/{project_id}` |
| Requirements run | `/api/v1/projects/{project_id}/requirements-runs` |
| Architecture run | `/api/v1/projects/{project_id}/architecture-runs` |
| Artifact storage | Project artifact routes and immutable content hashes |
| Human approval pause | Requirements, architecture, decomposition, integration, and recovery approvals |
| Audit history | Audit event models and project audit surfaces |
| Docker local run | Compose stack plus operator startup guide |
| Repository preparation | Server-side Git initialization and initial `HEAD` creation |
| Dashboard telemetry summary | Runtime job/project state plus governed performance metrics when organization context exists |

## Control Plane Rule

API routes accept commands and return state. Long-running work belongs to workers, services, and
workflow orchestration, not inside the request-response lifecycle.

## Execution Plane Rule

Crew and agent execution may create proposals, artifacts, findings, and summaries. Authoritative
project state, approval state, retry state, and audit state remain owned by the application platform.

## Persistence Plane Rule

PostgreSQL is the system of record. Framework checkpoints are useful, but projects, approvals,
artifacts, audit records, workflow history, and decisions must remain independently queryable.

## Operator Context Rule

Local dashboards may load development context to make graph and telemetry checks usable. Production
authority still depends on trusted identity assertions and durable grants.

## Verification

The slice is valid when tests prove project creation, direct lookup, artifact hashing, approval
contracts, migrations, worker queue behavior, and dashboard visibility.

## References

- [Project Execution Walkthrough](../enterprise/project-execution-walkthrough.md)
- [Workflow Catalog](workflow-catalog.md)
- [Reference: MVP Vertical Slice](../reference-architecture/14-mvp-vertical-slice/README.md)
