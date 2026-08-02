# Project Formation Orchestration

## Purpose

Project Formation Orchestration is the P6 planning product. It turns natural-language business
intent into a structured, reviewed, approved software project plan before code generation starts.

## Responsibilities

It owns project intake, clarification questions, project brief generation, solution proposal,
roadmap and backlog generation, risk/compliance review, documentation bundle creation, validation,
and manager approval.

## Scope

The first scope is define, plan, approve, and manage software projects. It does not start with
autonomous coding, deployment, finance, support, or dozens of agents.

## Non-Scope

The orchestrator does not replace implementation crews, security governance, workflow approval, or
human decision rights. It prepares the project plan that later workflows execute.

## Viewpoints

Business: a weak idea becomes a professional project definition. Architecture: specialist agents
produce separate structured outputs. Implementation: outputs are schemas, not unreviewed prose.
Operational: each stage has status, owner, validation, and approval state. Evolution: more agents
can be added by specialty without redesigning the formation workflow.

## Data Model

Managed objects are organization, workspace, project, project brief, requirements, architecture
proposal, roadmap, plan, epic, feature, story, task, subtask, risk, decision, document, conversation,
and approval. Each object carries title, description, status, owner, version, source, dependencies,
approval state, creation time, and modification history.

## Interfaces

Interfaces include dashboard idea intake, manifesto upload, vision clarification, project creation,
project intelligence, requirements artifacts, architecture artifacts, workflow history, audit
timeline, and project-formation APIs. The implemented endpoints are
`POST /api/v1/project-formation/packs` and
`POST /api/v1/project-formation/projects/{project_id}/packs`.

## Dependencies

Formation depends on identity/authority context, project factory, manifesto persistence, workflow
kernel, agent runtime, artifact storage, validation schemas, audit records, and dashboard guidance.

## Internal Components

Internal components are project orchestrator agent, business analyst agent, solution architect
agent, project planner agent, risk/compliance agent, documentation agent, validation layer, review
gate, and approval record.

## Workflow

The workflow is idea intake -> requirement discovery -> project definition -> solution proposal ->
delivery plan -> risk review -> documentation bundle -> manager approval -> active project.

## Implementation Plan

Start by documenting the contract and dashboard behavior. Persist the uploaded manifesto, then add
formation artifacts for project brief, solution proposal, roadmap, backlog, risk register, and
approval pack. The first slice persists `project_brief`, `solution_proposal`, `delivery_plan`,
`formation_quality_review`, and `formation_approval_pack`; later slices should add explicit
approval records and agent-backed formation crews.

## Testing

Tests must prove manifesto persistence, formation artifact schemas, validation failures, manager
approval requirement, agent contract boundaries, and dashboard guidance from idea to project graph.

## Security

Agents cannot approve their own work, change budget or scope without authority, deploy software, or
write final records without validation and approval.

## Observability

Formation needs stage history, agent execution records, validation results, clarification questions,
approval state, audit events, and dashboard next-action messages.

## Future Evolution

The workflow can add UX designer, technical lead, QA reviewer, DevOps, legal, finance, support, and
domain specialists after the four-agent formation path is reliable.

## References

- [Project Formation Orchestration](../../architecture/project-formation-orchestration.md)
- [Agent Catalog](../../architecture/agent-catalog.md)
