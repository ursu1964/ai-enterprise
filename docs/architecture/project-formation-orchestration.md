# Project Formation Orchestration

## Purpose

Project Formation turns a rough business idea into an approved software project plan before
implementation begins. It is the first useful product layer above the project factory.

The current implementation exposes `/api/v1/project-formation/packs` and the project-scoped alias
`/api/v1/project-formation/projects/{project_id}/packs`. The route creates a deterministic
formation pack before agent-backed formation crews are activated.

## Operating Model

The user starts with one simple question: what would you like to build? The orchestrator converts
the answer into structured work through specialist agents, validation, review, and human approval.

## First Agent Set

| Agent | Responsibility | Primary Output |
| --- | --- | --- |
| Project Orchestrator | Controls workflow, context, validation, and handoffs. | Formation history and next action. |
| Business Analyst | Understands business problem, users, goals, constraints, and missing facts. | Project brief and clarification questions. |
| Solution Architect | Proposes modules, integrations, data domains, and architecture options. | Solution proposal and architecture risks. |
| Project Planner | Converts scope into phases, epics, stories, dependencies, and estimates. | Roadmap and initial backlog. |
| Risk and Compliance Analyst | Identifies PII, audit, retention, security, and regulatory needs. | Risk register and compliance tasks. |
| Documentation Agent | Produces project charter, requirements, roadmap, and approval pack. | Documentation bundle. |

## Managed Objects

Organization -> workspace -> project -> brief -> requirements -> architecture proposal -> roadmap
-> plans -> epics -> features -> stories -> tasks -> subtasks.

Every object needs title, description, status, owner, version, source, dependencies, approval state,
created time, and modification history.

The first persisted formation artifacts are `project_brief`, `solution_proposal`, `delivery_plan`,
`formation_quality_review`, and `formation_approval_pack`. They are stored as hashed JSON artifacts
linked to the project and manifesto hash.

## Workflow

Idea intake -> clarification -> project definition -> solution proposal -> delivery plan -> risk
review -> documentation bundle -> manager approval -> active project.

## Validation

Generated outputs must pass schema validation, business-rule validation, quality review, and human
approval when required. A plan fails validation when requirements lack sources, epics lack business
objectives, stories lack acceptance criteria, milestones lack outcomes, or dependencies point to
undefined tasks.

The current formation pack marks missing expected outcome, target users, constraints, and known
systems as clarification items. A complete pack becomes `ready_for_approval`; an incomplete one
becomes `draft_needs_clarification`.

## References

- [Reference: Project Formation Orchestration](../reference-architecture/17-project-formation-orchestration/README.md)
- [Agent Catalog](agent-catalog.md)
- [Workflow Catalog](workflow-catalog.md)
