# Context Map

## Bounded Contexts

| Context | Owns | Depends On |
| --- | --- | --- |
| Project Lifecycle | projects, manifests, lifecycle status | requirements, architecture, work packages |
| Enterprise Kernel | resources, modules, schedules, organizational threads | organizations, audit |
| Organization Governance | organizations, roles, agents, authority | policy, audit |
| Agent Runtime | skills, tools, model sessions, output validation | organization governance, providers |
| Model and Prompt Governance | model deployments, routing policies, prompt registries, prompt versions | agent runtime, organization governance |
| Project Formation | project brief, solution proposal, delivery plan, quality review, approval pack | project lifecycle, dashboard, audit |
| Workflow Runtime | workflow instances, history, guards | jobs, audit, projects |
| Requirements Engineering | revisions, artifacts, approvals | projects, audit |
| Architecture Governance | architecture artifacts, approval gates, lineage | requirements, projects, audit |
| Work Decomposition | work-package plans, graphs, validation findings | architecture, repositories |
| Execution Runtime | isolated execution, events, tests, artifacts | work packages, repositories, workers |
| Review and Integration | patch reviews, checks, integration attempts | execution, git, approvals |
| Query Platform | read-only operating pictures, graph projections, freshness metadata | all authoritative contexts |
| Observability | metrics, health, dashboards, calibration signals | all runtime contexts |
| Knowledge and Evolution | learning candidates, improvements, blueprints | evidence, audits, telemetry |
| Migration and Handover | ownership transfer, release evidence, runbooks, client readiness | project lifecycle, deployment, operations |
| Analytics | economic proof, portfolio status, trend signals, reusable-template value | query platform, performance governance |

## Dependency Rule

Business lifecycle contexts may call application services and repositories through defined
interfaces. Domain logic must not depend on FastAPI, SQLAlchemy, CrewAI, or infrastructure details.

Read contexts may combine records from many owners, but they must not repair or mutate those
records. Problems discovered through a query become recommendations that route the operator to an
explicit command surface.
