# Architecture Views

## Business View

AI Enterprise turns a manifesto or imperfect client idea into a governed delivery path. The business
value is faster analysis, clearer project shaping, reusable blueprints, measurable execution proof,
and lower delivery risk through supervised agent crews.

## Logical View

The platform is organized around project lifecycle, enterprise kernel, organizations, workflows,
agents, crews, requirements, architecture, work packages, execution, review, integration,
observability, recovery, learning, and federation.

## Runtime View

FastAPI exposes operator, automation, command, and query APIs. Workers process durable jobs.
PostgreSQL is the system of record. Dashboards read the Query Platform operating picture plus API,
telemetry, job, worker, project, and graph signals.

## Deployment View

Local operation runs with Docker Compose. The stack includes API, database, migrations, and worker
services. Runtime configuration comes from `.env` and bootstrap records.

## Operational View

Operators use `/dashboard`, `/docs`, health endpoints, metrics, project graphs, audit timelines,
workflow histories, and worker/job surfaces to guide the enterprise from idea to proof.

## Evolution View

The system evolves module by module. New capabilities should become reusable templates, standards,
or ADR-backed decisions before they are treated as general enterprise behavior.
